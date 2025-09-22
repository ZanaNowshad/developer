"""Content and result structures for MCP tool invocations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List, Optional


class Role(str, Enum):
    """Audience roles for content objects."""

    ASSISTANT = "assistant"
    USER = "user"


@dataclass(slots=True)
class Content:
    """Represents a unit of tool output."""

    type: str
    text: Optional[str] = None
    data: Optional[str] = None
    media_type: Optional[str] = None
    audience: List[Role] = field(default_factory=list)
    priority: Optional[float] = None

    @classmethod
    def text_content(
        cls,
        text: str,
        *,
        audience: Optional[Iterable[Role]] = None,
        priority: Optional[float] = None,
    ) -> "Content":
        return cls(
            type="text",
            text=text,
            audience=list(audience) if audience else [],
            priority=priority,
        )

    @classmethod
    def image_content(
        cls,
        data: str,
        media_type: str,
        *,
        priority: Optional[float] = None,
    ) -> "Content":
        return cls(type="image", data=data, media_type=media_type, priority=priority)

    def to_dict(self) -> dict:
        payload = {
            "type": self.type,
            "priority": self.priority,
        }
        if self.text is not None:
            payload["text"] = self.text
        if self.data is not None:
            payload["data"] = self.data
        if self.media_type is not None:
            payload["media_type"] = self.media_type
        if self.audience:
            payload["audience"] = [role.value for role in self.audience]
        return {k: v for k, v in payload.items() if v is not None}


@dataclass(slots=True)
class CallToolResult:
    """Result of executing a tool."""

    success: bool
    content: List[Content]
    error: Optional[str] = None
    code: Optional[str] = None
    data: Optional[dict] = None

    @classmethod
    def success_result(cls, content: Iterable[Content]) -> "CallToolResult":
        return cls(success=True, content=list(content))

    @classmethod
    def error_result(
        cls, message: str, *, code: Optional[str] = None, data: Optional[dict] = None
    ) -> "CallToolResult":
        return cls(success=False, content=[], error=message, code=code, data=data)

    def to_dict(self) -> dict:
        base = {
            "success": self.success,
            "content": [item.to_dict() for item in self.content],
        }
        if self.error is not None:
            base["error"] = self.error
        if self.code is not None:
            base["code"] = self.code
        if self.data is not None:
            base["data"] = self.data
        return base
