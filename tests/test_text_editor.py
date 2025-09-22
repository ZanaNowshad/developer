import asyncio
from pathlib import Path

import asyncio
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from developer.content import Role
from developer.errors import ToolError
from developer.gitignore import IgnoreMatcher
from developer.text_editor import MAX_WRITE_CHAR_COUNT, TextEditor


def test_write_and_view_file(tmp_path: Path) -> None:
    editor = TextEditor()

    @given(content=st.text(min_size=1, max_size=64, alphabet=list("abc def\n")))
    def run_case(content: str) -> None:
        file_path = tmp_path / "example.txt"
        asyncio.run(editor.write(file_path, content))
        result = asyncio.run(editor.view(file_path))
        assert result.success is True
        assert result.content[0].text is not None
        assert content in result.content[0].text
        assert Role.ASSISTANT in result.content[0].audience

    run_case()


def test_str_replace(tmp_path: Path) -> None:
    editor = TextEditor()
    file_path = tmp_path / "example.txt"
    asyncio.run(editor.write(file_path, "Hello, world!"))
    result = asyncio.run(editor.str_replace(file_path, "world", "Python"))
    assert result.success is True
    assert "Python" in result.content[1].text


def test_undo_edit(tmp_path: Path) -> None:
    editor = TextEditor()
    file_path = tmp_path / "example.txt"
    asyncio.run(editor.write(file_path, "First"))
    asyncio.run(editor.str_replace(file_path, "First", "Second"))
    undo = asyncio.run(editor.undo_edit(file_path))
    assert undo.success is True
    content = file_path.read_text(encoding="utf-8")
    assert content == "First"


def test_write_character_limit(tmp_path: Path) -> None:
    editor = TextEditor()
    file_path = tmp_path / "example.txt"
    with pytest.raises(ToolError):
        asyncio.run(editor.write(file_path, "x" * (MAX_WRITE_CHAR_COUNT + 1)))


def test_history_limit(tmp_path: Path) -> None:
    editor = TextEditor(max_history=2)
    file_path = tmp_path / "history.txt"
    asyncio.run(editor.write(file_path, "v1"))
    asyncio.run(editor.str_replace(file_path, "v1", "v2"))
    asyncio.run(editor.str_replace(file_path, "v2", "v3"))
    asyncio.run(editor.str_replace(file_path, "v3", "v4"))
    asyncio.run(editor.undo_edit(file_path))
    asyncio.run(editor.undo_edit(file_path))
    with pytest.raises(ToolError):
        asyncio.run(editor.undo_edit(file_path))


def test_gitignore_respected(tmp_path: Path) -> None:
    matcher = IgnoreMatcher.from_patterns(tmp_path, ["secret.txt"])
    editor = TextEditor().with_ignore_patterns(matcher)
    secret = tmp_path / "secret.txt"
    with pytest.raises(ToolError):
        asyncio.run(editor.write(secret, "hidden"))
