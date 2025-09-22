import asyncio

from developer.mcp_server import McpServer
from developer.server import Developer


def test_mcp_server_initialize_and_list_tools() -> None:
    developer = Developer()
    server = McpServer(developer)

    async def scenario() -> None:
        await developer.startup()
        try:
            init_response = await server._handle_message({"id": 1, "method": "initialize"})
            assert init_response["result"]["protocolVersion"] == "1.0"

            list_response = await server._handle_message({"id": 2, "method": "tools/list"})
            tool_names = {tool["name"] for tool in list_response["result"]["tools"]}
            assert "text_editor" in tool_names
        finally:
            await developer.shutdown()

    asyncio.run(scenario())


def test_mcp_server_call_tool() -> None:
    developer = Developer()
    server = McpServer(developer)

    async def scenario() -> None:
        await developer.startup()
        try:
            response = await server._handle_message(
                {
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "code_analysis",
                        "arguments": {"mode": "imports", "source": "import json"},
                    },
                }
            )
            result = response["result"]
            assert result["success"] is True
            assert result["content"]
        finally:
            await developer.shutdown()

    asyncio.run(scenario())


def test_mcp_server_unknown_method() -> None:
    developer = Developer()
    server = McpServer(developer)

    async def scenario() -> None:
        error = await server._handle_message({"id": 4, "method": "missing/method"})
        assert error["error"]["code"] == -32601

    asyncio.run(scenario())
