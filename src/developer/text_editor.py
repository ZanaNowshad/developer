"""Async text editor utilities mirroring the Rust implementation."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from .content import CallToolResult, Content, Role
from .errors import ToolError
from .gitignore import IgnoreMatcher
from . import lang
from .utils import normalize_line_endings

DEFAULT_MAX_UNDO_HISTORY = 10
MAX_WRITE_CHAR_COUNT = 400_000
MAX_FILE_SIZE_BYTES = 400 * 1024
MAX_CHAR_COUNT = 400_000
SNIPPET_LINES = 4


class TextEditor:
    """Provides file manipulation helpers with undo support."""

    def __init__(self, max_history: int = DEFAULT_MAX_UNDO_HISTORY) -> None:
        self._history: Dict[Path, List[str]] = defaultdict(list)
        self._history_lock = asyncio.Lock()
        self._ignore: Optional[IgnoreMatcher] = None
        self._max_history = max_history

    def with_ignore_patterns(self, matcher: IgnoreMatcher) -> "TextEditor":
        self._ignore = matcher
        return self

    async def view(self, path: Path) -> CallToolResult:
        self._check_ignore(path)
        if not path.is_file():
            raise ToolError.invalid_params(
                f"The path '{path}' does not exist or is not a file."
            )

        stat = await asyncio.to_thread(path.stat)
        if stat.st_size > MAX_FILE_SIZE_BYTES:
            raise ToolError.invalid_params(
                (
                    f"File '{path}' is too large ({stat.st_size / 1024:.2f}KB)."
                    " Maximum size is 400KB to prevent memory issues."
                )
            )

        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        except UnicodeDecodeError as exc:  # pragma: no cover - rare scenario
            raise ToolError.internal_error(f"Failed to read file as UTF-8: {exc}") from exc
        except OSError as exc:
            raise ToolError.internal_error(f"Failed to read file: {exc}") from exc

        if len(content) > MAX_CHAR_COUNT:
            raise ToolError.invalid_params(
                (
                    f"File '{path}' has too many characters ({len(content)})."
                    f" Maximum character count is {MAX_CHAR_COUNT}."
                )
            )

        language = lang.get_language_identifier(path)
        formatted = f"### {path}\n```{language}\n{content}\n```"
        return CallToolResult.success_result(
            [
                Content.text_content(formatted, audience=[Role.ASSISTANT]),
                Content.text_content(formatted, audience=[Role.USER], priority=0.0),
            ]
        )

    async def write(self, path: Path, file_text: str) -> CallToolResult:
        self._check_ignore(path)
        if path.exists() and path.is_dir():
            raise ToolError.invalid_params(
                f"The path '{path}' is an existing directory. The 'write' command can only target files."
            )

        if len(file_text) > MAX_WRITE_CHAR_COUNT:
            raise ToolError.invalid_params(
                (
                    f"Input content for '{path}' has too many characters ({len(file_text)})."
                    f" Maximum allowed is {MAX_WRITE_CHAR_COUNT}."
                )
            )

        await self._save_file_history(path)

        normalized = normalize_line_endings(file_text)
        if path.parent and not path.parent.exists():
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(path.write_text, normalized, encoding="utf-8")
        except OSError as exc:
            raise ToolError.internal_error(f"Failed to write file: {exc}") from exc

        language = lang.get_language_identifier(path)
        formatted_output = f"### {path}\n```{language}\n{file_text}\n```"
        success_message = f"Successfully wrote to {path}"
        return CallToolResult.success_result(
            [
                Content.text_content(success_message, audience=[Role.ASSISTANT]),
                Content.text_content(formatted_output, audience=[Role.USER], priority=0.2),
            ]
        )

    async def str_replace(self, path: Path, old_str: str, new_str: str) -> CallToolResult:
        self._check_ignore(path)
        if not path.exists():
            raise ToolError.invalid_params(
                (
                    f"File '{path}' does not exist, you can write a new file with the `write` command"
                )
            )

        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        except UnicodeDecodeError as exc:  # pragma: no cover - rare scenario
            raise ToolError.internal_error(f"Failed to read file: {exc}") from exc
        except OSError as exc:
            raise ToolError.internal_error(f"Failed to read file: {exc}") from exc

        occurrences = content.count(old_str)
        if occurrences > 1:
            raise ToolError.invalid_params("'old_str' must appear exactly once in the file, but it appears multiple times")
        if occurrences == 0:
            raise ToolError.invalid_params(
                "'old_str' must appear exactly once in the file, but it does not appear in the file."
                " Make sure the string exactly matches existing file content, including whitespace!"
            )

        await self._save_file_history(path)

        new_content = content.replace(old_str, new_str)
        normalized_content = normalize_line_endings(new_content)
        try:
            await asyncio.to_thread(path.write_text, normalized_content, encoding="utf-8")
        except OSError as exc:
            raise ToolError.internal_error(f"Failed to write file: {exc}") from exc

        language = lang.get_language_identifier(path)
        lines = new_content.splitlines()
        replacement_line = content.split(old_str, 1)[0].count("\n")
        start_line = max(replacement_line - SNIPPET_LINES, 0)
        end_line = min(replacement_line + SNIPPET_LINES + new_str.count("\n"), len(lines) - 1)
        snippet = "\n".join(lines[start_line : end_line + 1])
        output = f"```{language}\n{snippet}\n```"
        success_message = (
            f"The file {path} has been edited, and the section now reads:\n{output}\n"
            "Review the changes above for errors. Undo and edit the file again if necessary!"
        )
        return CallToolResult.success_result(
            [
                Content.text_content(success_message, audience=[Role.ASSISTANT]),
                Content.text_content(output, audience=[Role.USER], priority=0.2),
            ]
        )

    async def undo_edit(self, path: Path) -> CallToolResult:
        self._check_ignore(path)
        resolved = path.resolve()
        async with self._history_lock:
            history = self._history.get(resolved)
            if not history:
                raise ToolError.invalid_params("No edit history available to undo")
            previous_content = history.pop()
        try:
            await asyncio.to_thread(path.write_text, previous_content, encoding="utf-8")
        except OSError as exc:
            raise ToolError.internal_error(f"Failed to write file: {exc}") from exc
        return CallToolResult.success_result([Content.text_content("Undid the last edit")])

    def _check_ignore(self, path: Path) -> None:
        if self._ignore and self._ignore.is_ignored(path):
            raise ToolError.invalid_request(
                f"The file '{path}' is restricted by ignore patterns"
            )

    async def _save_file_history(self, path: Path) -> None:
        async with self._history_lock:
            resolved = path.resolve()
            if path.exists() and path.is_file():
                try:
                    previous_content = await asyncio.to_thread(path.read_text, encoding="utf-8")
                except UnicodeDecodeError:
                    previous_content = ""
                except OSError:
                    previous_content = ""
            else:
                previous_content = ""
            history = self._history[resolved]
            history.append(previous_content)
            if self._max_history > 0 and len(history) > self._max_history:
                del history[: len(history) - self._max_history]
