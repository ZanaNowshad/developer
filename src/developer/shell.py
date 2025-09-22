"""Cross-platform shell execution utilities."""

from __future__ import annotations

import asyncio
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .content import CallToolResult, Content, Role
from .errors import ToolError
from .gitignore import IgnoreMatcher
from .utils import normalize_line_endings

MAX_OUTPUT_CHAR_COUNT = 400_000


@dataclass(slots=True)
class ShellConfig:
    executable: str
    arg: str
    redirect_syntax: str

    @classmethod
    def for_platform(cls) -> "ShellConfig":
        if os.name == "nt":
            return cls(
                executable="powershell.exe",
                arg="-NoProfile -NonInteractive -Command",
                redirect_syntax="2>&1",
            )
        shell = os.environ.get("SHELL") or "bash"
        return cls(executable=shell, arg="-c", redirect_syntax="2>&1")


class Shell:
    def __init__(self, config: Optional[ShellConfig] = None) -> None:
        self._config = config or ShellConfig.for_platform()
        self._ignore: Optional[IgnoreMatcher] = None

    def with_ignore_patterns(self, matcher: IgnoreMatcher) -> "Shell":
        self._ignore = matcher
        return self

    @property
    def config(self) -> ShellConfig:
        return self._config

    def format_command_for_platform(self, command: str) -> str:
        if os.name == "nt":
            return f"{{ {command} }} {self._config.redirect_syntax}"
        return f"{command} {self._config.redirect_syntax}"

    def _check_ignore_patterns(self, command: str) -> None:
        if not self._ignore:
            return
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        for arg in parts[1:]:
            if arg.startswith("-"):
                continue
            candidate = Path(arg)
            if not candidate.exists():
                continue
            if self._ignore.is_ignored(candidate):
                raise ToolError.invalid_request(
                    f"The command attempts to access '{arg}' which is restricted by ignore patterns"
                )

    async def execute(self, command: str) -> CallToolResult:
        self._check_ignore_patterns(command)
        formatted = self.format_command_for_platform(command)
        try:
            process = await asyncio.create_subprocess_exec(
                self._config.executable,
                self._config.arg,
                formatted,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise ToolError.internal_error(f"Failed to spawn command: {exc}") from exc

        stdout, stderr = await process.communicate()
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        combined = stdout_str + stderr_str
        normalized = normalize_line_endings(combined)
        if len(normalized) > MAX_OUTPUT_CHAR_COUNT:
            raise ToolError.invalid_params(
                (
                    f"Shell output from command '{command}' has too many characters ({len(normalized)})."
                    f" Maximum character count is {MAX_OUTPUT_CHAR_COUNT}."
                )
            )
        return CallToolResult.success_result(
            [
                Content.text_content(normalized, audience=[Role.ASSISTANT]),
                Content.text_content(normalized, audience=[Role.USER], priority=0.0),
            ]
        )
