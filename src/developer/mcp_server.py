"""Minimal JSON-RPC server for the Model Context Protocol over stdio."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Dict, Optional

from .content import CallToolResult
from .server import Developer

CONTENT_LENGTH = "Content-Length"


class McpServer:
    """Implements the subset of MCP required by the Developer tools server."""

    def __init__(self, developer: Optional[Developer] = None) -> None:
        self._developer = developer or Developer()
        self._running = True

    async def serve_stdio(self) -> None:
        await self._developer.startup()
        try:
            while self._running:
                message = await self._read_message()
                if message is None:
                    break
                response = await self._handle_message(message)
                if response is not None:
                    await self._write_message(response)
        finally:
            await self._developer.shutdown()

    async def _read_message(self) -> Optional[Dict[str, Any]]:
        headers: Dict[str, str] = {}
        while True:
            line = await asyncio.to_thread(sys.stdin.buffer.readline)
            if not line:
                return None
            stripped = line.strip()
            if not stripped:
                break
            key, _, value = stripped.partition(b":")
            headers[key.decode("utf-8").strip()] = value.decode("utf-8").strip()
        length = int(headers.get(CONTENT_LENGTH, "0"))
        if length == 0:
            return None
        body = await asyncio.to_thread(sys.stdin.buffer.read, length)
        return json.loads(body.decode("utf-8"))

    async def _write_message(self, response: Dict[str, Any]) -> None:
        payload = json.dumps(response).encode("utf-8")
        header = f"{CONTENT_LENGTH}: {len(payload)}\r\n\r\n".encode("utf-8")
        await asyncio.to_thread(sys.stdout.buffer.write, header + payload)
        await asyncio.to_thread(sys.stdout.buffer.flush)

    async def _handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = message.get("method")
        if method is None:
            return None
        if method in {"initialize", "mcp/initialize"}:
            return self._response(message, {
                "protocolVersion": "1.0",
                "serverInfo": {"name": "developer", "version": "0.1.0"},
                "capabilities": {"tools": True},
            })
        if method in {"tools/list", "list_tools"}:
            tools = await self._developer.list_tools()
            return self._response(message, {"tools": tools})
        if method in {"tools/call", "call_tool"}:
            params = message.get("params") or {}
            name = params.get("name") or params.get("tool")
            if not name:
                return self._error(message, code=-32602, message="Missing tool name")
            arguments = params.get("arguments") or params.get("args") or {}
            result = await self._developer.call_tool(name, arguments)
            return self._response(message, self._serialize_result(result))
        if method in {"ping", "mcp/ping"}:
            return self._response(message, {"ok": True})
        if method in {"shutdown", "mcp/shutdown", "exit"}:
            self._running = False
            return self._response(message, {"ok": True})
        return self._error(message, code=-32601, message=f"Unknown method {method}")

    def _response(self, request: Dict[str, Any], result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}

    def _error(self, request: Dict[str, Any], *, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": code, "message": message},
        }

    @staticmethod
    def _serialize_result(result: CallToolResult) -> Dict[str, Any]:
        payload = result.to_dict()
        return payload
