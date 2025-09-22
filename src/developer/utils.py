"""Cross-platform utility helpers."""

from __future__ import annotations

import os
import re
from pathlib import Path


_WINDOWS_ENV_RE = re.compile(r"%([^%]+)%")


def expand_path(path_str: str) -> str:
    """Expand a user-provided path string."""

    if os.name == "nt":
        # Expand %VAR% style environment variables first
        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            return os.environ.get(key, "")

        expanded = _WINDOWS_ENV_RE.sub(replacer, path_str)
        return os.path.expanduser(expanded)
    return os.path.expandvars(os.path.expanduser(path_str))


def is_absolute_path(path_str: str) -> bool:
    """Determine if a path is absolute on the current platform."""

    return Path(path_str).expanduser().is_absolute()


def normalize_line_endings(text: str) -> str:
    """Normalize line endings for the current operating system."""

    if os.name == "nt":
        # Replace all CRLF with LF then convert back to CRLF to avoid duplication
        text = text.replace("\r\n", "\n")
        return text.replace("\n", "\r\n")
    return text.replace("\r\n", "\n")
