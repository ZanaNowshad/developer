"""Primary Developer MCP server implementation with modernised architecture."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .ast_tools import extract_function_signatures, list_imports
from .cache import CacheBackend, create_cache
from .config import AppSettings
from .content import CallToolResult, Content
from .database import AsyncDatabase
from .errors import ToolError
from .gitignore import IgnoreMatcher
from .image_processor import ImageProcessor
from .observability import (
    annotate_tool_error,
    annotate_tool_result,
    setup_tracer,
    traced_async,
)
from .plugins import PluginManager
from .realtime import RealTimeHub
from .screen_capture import ScreenCapture
from .schemas import (
    CodeAnalysisParams,
    ImageProcessorParams,
    ScreenCaptureParams,
    ShellParams,
    TextEditorParams,
    WorkflowParams,
)
from .shell import Shell
from .text_editor import TextEditor
from .tasks import TaskQueue
from .tooling import Tool, ToolRegistry
from .utils import expand_path, is_absolute_path
from .workflow import Workflow

_TEXT_EDITOR_DESCRIPTION = """Text Editor Tool: File Content Manipulation\n\nProvides commands to perform text editing operations on files, such as viewing, creating, overwriting, and modifying content, along with an undo capability for recent changes."""

_SHELL_DESCRIPTION = "Execute shell commands on the system"

_LIST_WINDOWS_DESCRIPTION = (
    "List all available window titles that can be used with screen_capture.\n"
    "Returns a list of window titles that can be used with the window_title parameter\n"
    "of the screen_capture tool."
)

_SCREEN_CAPTURE_DESCRIPTION = (
    "Capture a screenshot of a specified display or window.\n"
    "You can capture either:\n1. A full display (monitor) using the display parameter\n"
    "2. A specific window by its title using the window_title parameter\n\n"
    "Only one of display or window_title should be specified."
)

_IMAGE_PROCESSOR_DESCRIPTION = (
    "Process an image file from disk. The image will be:\n"
    "1. Resized if larger than max width while maintaining aspect ratio\n"
    "2. Optionally resized further by 1/2 or 1/4 to reduce file size\n"
    "3. Preserved in original format (JPEG stays JPEG, PNG stays PNG) for optimal compression\n"
    "4. Returned as base64 encoded data"
)

_WORKFLOW_DESCRIPTION = """Workflow Tool: Guiding Complex Problem-Solving\n\nManages multi-step problem-solving processes with support for sequential progression, branching paths, and step revisions."""

_CODE_ANALYSIS_DESCRIPTION = (
    "Perform static analysis of Python source code. "
    "Supports extracting function signatures and listing import dependencies."
)


class Developer:
    def __init__(
        self,
        *,
        settings: Optional[AppSettings] = None,
        cache: Optional[CacheBackend] = None,
        database: Optional[AsyncDatabase] = None,
        task_queue: Optional[TaskQueue] = None,
        realtime: Optional[RealTimeHub] = None,
        plugin_manager: Optional[PluginManager] = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.cache = cache or create_cache(self.settings)
        self.database = database or AsyncDatabase(self.settings)
        self.task_queue = task_queue or TaskQueue(self.settings)
        self.realtime = realtime or RealTimeHub()
        self.tracer = setup_tracer(self.settings)
        self.plugin_manager = plugin_manager or PluginManager(self.settings.plugin_modules())

        cwd = self.settings.workspace_path
        ignore = IgnoreMatcher.from_gitignore(cwd)
        max_history = max(0, self.settings.text_editor_max_history)
        self._text_editor = TextEditor(max_history=max_history).with_ignore_patterns(ignore)
        self._shell = Shell().with_ignore_patterns(ignore)
        self._screen_capture = ScreenCapture()
        self._image_processor = ImageProcessor()
        self._workflow = Workflow(True, None, True)
        self._registry = ToolRegistry(
            [
                Tool(
                    name="text_editor",
                    description=_TEXT_EDITOR_DESCRIPTION,
                    parameters=TextEditorParams,
                    handler=self._handle_text_editor,
                    tags=["core", "files"],
                ),
                Tool(
                    name="shell",
                    description=_SHELL_DESCRIPTION,
                    parameters=ShellParams,
                    handler=self._handle_shell,
                    tags=["core", "system"],
                ),
                Tool(
                    name="list_windows",
                    description=_LIST_WINDOWS_DESCRIPTION,
                    parameters=ScreenCaptureParams,
                    handler=self._handle_list_windows,
                    tags=["optional", "screen"],
                ),
                Tool(
                    name="screen_capture",
                    description=_SCREEN_CAPTURE_DESCRIPTION,
                    parameters=ScreenCaptureParams,
                    handler=self._handle_screen_capture,
                    tags=["optional", "screen"],
                ),
                Tool(
                    name="image_processor",
                    description=_IMAGE_PROCESSOR_DESCRIPTION,
                    parameters=ImageProcessorParams,
                    handler=self._handle_image_processor,
                    tags=["optional", "images"],
                ),
                Tool(
                    name="workflow",
                    description=_WORKFLOW_DESCRIPTION,
                    parameters=WorkflowParams,
                    handler=self._handle_workflow,
                    tags=["core", "workflow"],
                ),
                Tool(
                    name="code_analysis",
                    description=_CODE_ANALYSIS_DESCRIPTION,
                    parameters=CodeAnalysisParams,
                    handler=self._handle_code_analysis,
                    tags=["analysis", "python"],
                ),
            ]
        , plugin_manager=self.plugin_manager)

        self._code_analysis_task = self.task_queue.task("code_analysis")(
            self._execute_code_analysis
        )

    async def startup(self) -> None:
        await self.database.connect()

    async def shutdown(self) -> None:
        await self.database.disconnect()

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @staticmethod
    async def get_tools_schema_as_json() -> str:
        developer = Developer()
        await developer.startup()
        try:
            data = await developer.list_tools()
        finally:
            await developer.shutdown()
        return json.dumps(data, indent=2)

    async def list_tools(self) -> Iterable[dict[str, Any]]:
        ttl = self.settings.tools_cache_ttl_seconds
        cached = None
        if ttl > 0:
            cached = await self.cache.get("tools:list")
            if cached is not None:
                return cached
        tools = self._registry.list_all()
        if ttl > 0:
            await self.cache.set("tools:list", tools, ttl=ttl)
        return tools

    async def plugin_status(self) -> Iterable[dict[str, Any]]:
        return [record.__dict__ for record in self.plugin_manager.describe()]

    async def reload_plugins(self) -> None:
        self.plugin_manager.reload(self._registry)
        await self.cache.invalidate("tools:")

    def resolve_path(self, path_str: str) -> Path:
        expanded = expand_path(path_str)
        path = Path(expanded)
        if is_absolute_path(str(path)):
            return path
        suggestion = Path.cwd() / path
        raise ToolError.invalid_params(
            f"The path {path_str} is not an absolute path, did you possibly mean {suggestion}?"
        )

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> CallToolResult:
        tool = self._registry.get(name)
        async def _execute(span: Any) -> CallToolResult:
            try:
                result = await tool.call(arguments)
            except ToolError as exc:
                annotate_tool_error(span, exc)
                result = CallToolResult.error_result(exc.message, code=exc.code, data=exc.data)
            annotate_tool_result(span, name, result)
            await self.database.record(name, arguments)
            broadcast_payload = {
                "tool": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": result.success,
            }
            if not result.success and result.error:
                broadcast_payload["error"] = result.error
            await self.realtime.broadcast("tool_executed", broadcast_payload)
            return result

        return await traced_async(
            self.tracer,
            f"tool.{name}",
            _execute,
            attributes={"developer.tool": name},
        )

    async def _handle_text_editor(self, params: TextEditorParams) -> CallToolResult:
        path = self.resolve_path(params.path)
        match params.command:
            case "view":
                return await self._text_editor.view(path)
            case "write":
                if params.file_text is None:
                    raise ToolError.invalid_params("file_text is required for the write command")
                return await self._text_editor.write(path, params.file_text)
            case "str_replace":
                if params.old_str is None or params.new_str is None:
                    raise ToolError.invalid_params(
                        "old_str and new_str are required for the str_replace command"
                    )
                return await self._text_editor.str_replace(path, params.old_str, params.new_str)
            case "undo_edit":
                return await self._text_editor.undo_edit(path)
            case _:
                raise ToolError.invalid_params(
                    "Unknown command. Allowed commands are: view, write, str_replace, undo_edit"
                )

    async def _handle_shell(self, params: ShellParams) -> CallToolResult:
        return await self._shell.execute(params.command)

    async def _handle_list_windows(self, params: ScreenCaptureParams) -> CallToolResult:
        _ = params  # Unused but required for schema consistency
        return await self._screen_capture.list_windows()

    async def _handle_screen_capture(self, params: ScreenCaptureParams) -> CallToolResult:
        return await self._screen_capture.capture(params.display, params.window_title)

    async def _handle_image_processor(self, params: ImageProcessorParams) -> CallToolResult:
        path = self.resolve_path(params.path)
        return await self._image_processor.process(path, params.resize)

    async def _handle_workflow(self, params: WorkflowParams) -> CallToolResult:
        return await self._workflow.execute_step(params)

    async def _handle_code_analysis(self, params: CodeAnalysisParams) -> CallToolResult:
        contents = await self.task_queue.dispatch(self._code_analysis_task, params.model_dump())
        return CallToolResult.success_result(contents)

    async def _execute_code_analysis(self, payload: Dict[str, Any]) -> Iterable[Content]:
        params = CodeAnalysisParams.from_dict(payload)
        if params.mode == "signatures":
            signatures = [
                {
                    "name": sig.name,
                    "arguments": sig.arguments,
                    "lineno": sig.lineno,
                }
                for sig in extract_function_signatures(params.source)
            ]
            content = json.dumps({"signatures": signatures}, indent=2)
        else:
            imports = list_imports(params.source)
            content = json.dumps({"imports": imports}, indent=2)
        return [Content.text_content(content)]
