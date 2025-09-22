import asyncio
from pathlib import Path
from textwrap import dedent

import pytest
from hypothesis import given, strategies as st

from developer.config import AppSettings
from developer.errors import ToolError
from developer.server import Developer


def test_resolve_path(tmp_path: Path) -> None:
    developer = Developer()
    resolved = developer.resolve_path(str(tmp_path))
    assert resolved == tmp_path


def test_resolve_path_relative() -> None:
    developer = Developer()
    with pytest.raises(ToolError):
        developer.resolve_path("relative/path.txt")


def test_call_tool_view(tmp_path: Path) -> None:
    developer = Developer()
    file_path = tmp_path / "example.txt"
    file_path.write_text("sample", encoding="utf-8")
    result = asyncio.run(
        developer.call_tool(
            "text_editor",
            {"command": "view", "path": str(file_path)},
        )
    )
    assert result.success is True
    assert "sample" in result.content[0].text


def test_call_tool_write_requires_content(tmp_path: Path) -> None:
    developer = Developer()
    file_path = tmp_path / "new.txt"
    result = asyncio.run(
        developer.call_tool(
            "text_editor",
            {"command": "write", "path": str(file_path)},
        )
    )
    assert result.success is False
    assert result.error is not None
    assert "file_text is required" in result.error


def test_list_tools_cached() -> None:
    developer = Developer()
    first = asyncio.run(developer.list_tools())
    second = asyncio.run(developer.list_tools())
    assert list(first) == list(second)


def test_plugin_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    plugin_module = plugin_dir / "demo_plugin.py"
    plugin_module.write_text(
        dedent(
            """
            from developer.content import CallToolResult, Content
            from developer.schemas import ShellParams
            from developer.tooling import Tool

            async def _handler(params: ShellParams) -> CallToolResult:
                return CallToolResult.success_result([Content.text_content("ok")])

            def register(registry):
                registry.register(
                    Tool(
                        name="demo_plugin_tool",
                        description="Demo tool",
                        parameters=ShellParams,
                        handler=_handler,
                    )
                )
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(plugin_dir))
    settings = AppSettings(enabled_plugins=["demo_plugin"])
    developer = Developer(settings=settings)
    tools = asyncio.run(developer.list_tools())
    assert any(tool["name"] == "demo_plugin_tool" for tool in tools)


def test_plugin_reload_failure_removes_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    plugin_module = plugin_dir / "flaky_plugin.py"
    plugin_module.write_text(
        dedent(
            """
            import os

            from developer.content import CallToolResult, Content
            from developer.schemas import ShellParams
            from developer.tooling import Tool

            async def _handler(params: ShellParams) -> CallToolResult:
                return CallToolResult.success_result([Content.text_content("ok")])

            def register(registry):
                if os.environ.get("FLAKY_PLUGIN_FAIL") == "1":
                    raise RuntimeError("boom")
                registry.register(
                    Tool(
                        name="flaky_plugin_tool",
                        description="Flaky tool",
                        parameters=ShellParams,
                        handler=_handler,
                    )
                )
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(plugin_dir))
    monkeypatch.setenv("FLAKY_PLUGIN_FAIL", "0")
    settings = AppSettings(enabled_plugins=["flaky_plugin"], tools_cache_ttl_seconds=0)
    developer = Developer(settings=settings)

    async def scenario() -> None:
        tools = await developer.list_tools()
        assert any(tool["name"] == "flaky_plugin_tool" for tool in tools)

        monkeypatch.setenv("FLAKY_PLUGIN_FAIL", "1")
        await developer.reload_plugins()
        tools_after = await developer.list_tools()
        assert not any(tool["name"] == "flaky_plugin_tool" for tool in tools_after)

        records = developer.plugin_manager.describe()
        record = next(rec for rec in records if rec.name == "flaky_plugin")
        assert record.loaded is False
        assert record.error is not None

    asyncio.run(scenario())


def test_code_analysis_imports() -> None:
    developer = Developer()

    @given(identifier=st.text(min_size=1, max_size=5, alphabet=list("abc")))
    def run_case(identifier: str) -> None:
        source = f"import {identifier}\n"
        result = asyncio.run(
            developer.call_tool(
                "code_analysis",
                {"mode": "imports", "source": source},
            )
        )
        payload = result.to_dict()
        assert payload["content"][0]["text"]
        assert identifier in payload["content"][0]["text"]

    run_case()
