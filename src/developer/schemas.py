"""Schema definitions backed by a lightweight Pydantic v2 compatible layer."""

from __future__ import annotations

from typing import Any, ClassVar, Dict, Literal, Optional

from .errors import ToolError

try:  # pragma: no cover - exercised when optional dependency exists
    from pydantic import BaseModel, ConfigDict, Field, ValidationError
except ModuleNotFoundError:  # pragma: no cover - executed in constrained environments
    from .stubs.pydantic import BaseModel, ConfigDict, Field, ValidationError


class SchemaModel(BaseModel):
    """Base class shared by all schema models."""

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def schema_dict(cls) -> Dict[str, Any]:
        return cls.model_json_schema()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        try:
            return cls.model_validate(data)
        except ValidationError as exc:  # pragma: no cover - defensive path
            raise ToolError.invalid_params(str(exc)) from exc


class TextEditorParams(SchemaModel):
    command: Literal["view", "write", "str_replace", "undo_edit"]
    path: str
    file_text: Optional[str] = None
    old_str: Optional[str] = None
    new_str: Optional[str] = None

    _schema: ClassVar[Dict[str, Any]] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["view", "write", "str_replace", "undo_edit"],
                "description": "Command to execute",
            },
            "path": {"type": "string", "description": "Absolute path to the target file"},
            "file_text": {"type": ["string", "null"], "description": "Content used by the write command"},
            "old_str": {"type": ["string", "null"], "description": "String replaced in str_replace"},
            "new_str": {"type": ["string", "null"], "description": "Replacement value for str_replace"},
        },
        "required": ["command", "path"],
        "additionalProperties": False,
    }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextEditorParams":
        instance = super().from_dict(data)
        if instance.command == "write" and instance.file_text is None:
            raise ToolError.invalid_params("file_text is required for the write command")
        if instance.command == "str_replace" and (instance.old_str is None or instance.new_str is None):
            raise ToolError.invalid_params("old_str and new_str are required for str_replace")
        return instance

    @classmethod
    def schema_dict(cls) -> Dict[str, Any]:  # pragma: no cover - static schema used for docs
        return dict(cls._schema)


class ShellParams(SchemaModel):
    command: str = Field(description="Command to execute in the shell")

    @classmethod
    def schema_dict(cls) -> Dict[str, Any]:  # pragma: no cover - static schema used for docs
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command"},
            },
            "required": ["command"],
            "additionalProperties": False,
        }


class ScreenCaptureParams(SchemaModel):
    display: Optional[int] = Field(default=None, description="Display index to capture")
    window_title: Optional[str] = Field(default=None, description="Window title to capture")

    @classmethod
    def schema_dict(cls) -> Dict[str, Any]:  # pragma: no cover - static schema used for docs
        return {
            "type": "object",
            "properties": {
                "display": {
                    "type": ["integer", "null"],
                    "description": "Index of the display to capture",
                },
                "window_title": {
                    "type": ["string", "null"],
                    "description": "Specific window title to capture",
                },
            },
            "additionalProperties": False,
        }


class ImageProcessorParams(SchemaModel):
    path: str = Field(description="Absolute path to the image to process")
    resize: Optional[Literal["1/2", "1/4"]] = Field(
        default=None, description="Optional downscale factor"
    )

    @classmethod
    def schema_dict(cls) -> Dict[str, Any]:  # pragma: no cover - static schema used for docs
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute image path"},
                "resize": {
                    "type": ["string", "null"],
                    "enum": ["1/2", "1/4"],
                    "description": "Optional resize factor",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        }


class WorkflowParams(SchemaModel):
    step_description: str
    step_number: int
    total_steps: int
    next_step_needed: bool
    is_step_revision: Optional[bool] = None
    revises_step: Optional[int] = None
    branch_from_step: Optional[int] = None
    branch_id: Optional[str] = None
    needs_more_steps: Optional[bool] = None

    @classmethod
    def schema_dict(cls) -> Dict[str, Any]:  # pragma: no cover - static schema used for docs
        return {
            "type": "object",
            "properties": {
                "step_description": {"type": "string"},
                "step_number": {"type": "integer"},
                "total_steps": {"type": "integer"},
                "next_step_needed": {"type": "boolean"},
                "is_step_revision": {"type": ["boolean", "null"]},
                "revises_step": {"type": ["integer", "null"]},
                "branch_from_step": {"type": ["integer", "null"]},
                "branch_id": {"type": ["string", "null"]},
                "needs_more_steps": {"type": ["boolean", "null"]},
            },
            "required": ["step_description", "step_number", "total_steps", "next_step_needed"],
            "additionalProperties": False,
        }


class CodeAnalysisParams(SchemaModel):
    mode: Literal["signatures", "imports"] = Field(default="signatures")
    source: str = Field(description="Python source code to analyse")

    @classmethod
    def schema_dict(cls) -> Dict[str, Any]:  # pragma: no cover - static schema used for docs
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["signatures", "imports"],
                    "description": "Type of analysis to run",
                },
                "source": {"type": "string", "description": "Python source code"},
            },
            "required": ["source"],
            "additionalProperties": False,
        }
