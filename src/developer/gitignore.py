"""Utilities for working with gitignore-style patterns."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from pathspec import PathSpec


@dataclass(slots=True)
class IgnoreMatcher:
    """Matches paths against gitignore-style rules."""

    root: Path
    spec: Optional[PathSpec]

    @classmethod
    def from_gitignore(cls, root: Path) -> "IgnoreMatcher":
        gitignore = root / ".gitignore"
        if gitignore.exists():
            lines = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
            spec = PathSpec.from_lines("gitwildmatch", lines)
        else:
            spec = None
        return cls(root=root, spec=spec)

    @classmethod
    def from_patterns(cls, root: Path, patterns: Iterable[str]) -> "IgnoreMatcher":
        spec = PathSpec.from_lines("gitwildmatch", patterns)
        return cls(root=root, spec=spec)

    def is_ignored(self, path: Path) -> bool:
        if self.spec is None:
            return False
        try:
            relative = path.resolve().relative_to(self.root.resolve())
        except Exception:  # pragma: no cover - defensive fallback
            relative = path
        candidate = str(relative).replace("\\", "/")
        return self.spec.match_file(candidate)
