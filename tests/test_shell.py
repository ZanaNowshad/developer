import asyncio
import asyncio
from pathlib import Path

import pytest

from developer.errors import ToolError
from developer.gitignore import IgnoreMatcher
from developer.shell import Shell


def test_shell_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHELL", "/bin/sh")
    shell = Shell()
    result = asyncio.run(shell.execute("echo hello"))
    assert result.success is True
    assert "hello" in result.content[0].text


def test_shell_ignore_patterns(tmp_path: Path) -> None:
    matcher = IgnoreMatcher.from_patterns(tmp_path, ["blocked.txt"])
    shell = Shell().with_ignore_patterns(matcher)
    blocked_path = tmp_path / "blocked.txt"
    blocked_path.write_text("secret", encoding="utf-8")
    with pytest.raises(ToolError):
        shell._check_ignore_patterns(f"cat {blocked_path}")
