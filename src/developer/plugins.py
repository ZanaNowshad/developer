"""Dynamic plugin architecture with sandboxed registration."""

from __future__ import annotations

import runpy
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .errors import ToolError
from .tooling import Tool, ToolRegistry


@dataclass
class PluginRecord:
    name: str
    loaded: bool
    error: Optional[str] = None
    registered_tools: List[str] = field(default_factory=list)


class SandboxRegistry:
    """Lightweight facade passed to plugins to ensure isolation."""

    def __init__(self) -> None:
        self._tools: List[Tool] = []

    def register(self, tool: Tool) -> None:
        if not isinstance(tool, Tool):  # pragma: no cover - defensive
            raise ToolError.invalid_request("Plugins must register Tool instances")
        self._tools.append(tool)

    @property
    def tools(self) -> List[Tool]:
        return list(self._tools)


class PluginManager:
    """Loads plugins defined in the configuration and registers their tools."""

    def __init__(self, plugin_paths: Iterable[str]) -> None:
        self._plugin_paths = list(dict.fromkeys(plugin_paths))
        self._records: Dict[str, PluginRecord] = {}
        self._tools_by_plugin: Dict[str, List[str]] = {}

    def register(self, registry: ToolRegistry) -> None:
        for name in self._plugin_paths:
            self._records[name] = self._load_plugin(name, registry)

    def reload(self, registry: ToolRegistry) -> None:
        for name in list(self._plugin_paths):
            self._records[name] = self._load_plugin(name, registry)

    def describe(self) -> List[PluginRecord]:
        return list(self._records.values())

    def _load_plugin(self, module_name: str, registry: ToolRegistry) -> PluginRecord:
        sandbox = SandboxRegistry()
        previous_tools = self._tools_by_plugin.get(module_name, [])
        for tool_name in previous_tools:
            registry.unregister(tool_name)
        self._tools_by_plugin[module_name] = []
        try:
            module_globals = runpy.run_module(module_name, run_name=f"{module_name}.__plugin__")
        except ModuleNotFoundError as exc:
            return PluginRecord(name=module_name, loaded=False, error=str(exc))
        except Exception as exc:  # pragma: no cover - plugin failure
            return PluginRecord(name=module_name, loaded=False, error=str(exc))

        register_func = module_globals.get("register")
        if not callable(register_func):
            return PluginRecord(
                name=module_name,
                loaded=False,
                error="Plugin must expose a callable 'register' function",
            )

        try:
            register_func(sandbox)
        except Exception as exc:  # pragma: no cover - plugin bug
            return PluginRecord(name=module_name, loaded=False, error=str(exc))

        tools = sandbox.tools
        record = PluginRecord(
            name=module_name,
            loaded=True,
            registered_tools=[tool.name for tool in tools],
        )
        for tool in tools:
            registry.unregister(tool.name)
            registry.register(tool)
        self._tools_by_plugin[module_name] = [tool.name for tool in tools]
        return record


__all__ = ["PluginManager", "PluginRecord", "SandboxRegistry"]
