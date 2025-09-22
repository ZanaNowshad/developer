"""Internal registry and plugin integration for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Iterable, List, Optional, Sequence, Type

from .content import CallToolResult
from .errors import ToolError
from .schemas import SchemaModel


Handler = Callable[[SchemaModel], Awaitable[CallToolResult]]


class PluginProtocol:
    """Minimal protocol implemented by dynamically loaded plugins."""

    def register(self, registry: "ToolRegistry") -> None:  # pragma: no cover - runtime behaviour
        raise NotImplementedError



@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: Type[SchemaModel]
    handler: Handler
    tags: List[str] = field(default_factory=list)

    async def call(self, arguments: Dict) -> CallToolResult:
        try:
            params = self.parameters.from_dict(arguments)
        except ToolError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise ToolError.invalid_params(str(exc)) from exc
        return await self.handler(params)

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters.schema_dict(),
            "tags": list(self.tags),
        }


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool], *, plugin_manager: Optional[PluginProtocol] = None):
        self._tools: Dict[str, Tool] = {}
        self._plugin_manager = plugin_manager
        for tool in tools:
            self.register(tool)
        if self._plugin_manager is not None:
            self._plugin_manager.register(self)

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolError.invalid_request(f"Unknown tool '{name}'") from exc

    def list_all(self) -> List[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def names(self) -> Sequence[str]:
        return list(self._tools.keys())

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ToolError.invalid_request(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
