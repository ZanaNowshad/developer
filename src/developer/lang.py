"""Language detection helpers for syntax highlighting."""

from __future__ import annotations

from pathlib import Path

_LANGUAGE_MAP = {
    "rs": "rust",
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "json": "json",
    "toml": "toml",
    "yaml": "yaml",
    "yml": "yaml",
    "sh": "bash",
    "ps1": "powershell",
    "bat": "batch",
    "cmd": "batch",
    "vbs": "vbscript",
    "go": "go",
    "md": "markdown",
    "html": "html",
    "css": "css",
    "sql": "sql",
    "java": "java",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c": "c",
    "h": "cpp",
    "hpp": "cpp",
    "rb": "ruby",
    "php": "php",
    "swift": "swift",
    "kt": "kotlin",
    "kts": "kotlin",
    "scala": "scala",
    "r": "r",
    "m": "matlab",
    "pl": "perl",
    "dockerfile": "dockerfile",
}


def get_language_identifier(path: Path) -> str:
    """Return a Markdown language identifier for the supplied path."""

    ext = path.suffix.lstrip(".").lower()
    if not ext:
        # Handle files like "Dockerfile"
        name = path.name.lower()
        return _LANGUAGE_MAP.get(name, "")
    return _LANGUAGE_MAP.get(ext, "")
