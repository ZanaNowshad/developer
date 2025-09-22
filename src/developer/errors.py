"""Error types used by the Developer server."""

from __future__ import annotations

from typing import Optional


class ToolError(Exception):
    """Represents an error returned to MCP clients."""

    def __init__(self, message: str, code: str = "internal_error", data: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.data = data

    @classmethod
    def invalid_params(cls, message: str, data: Optional[dict] = None) -> "ToolError":
        return cls(message=message, code="invalid_params", data=data)

    @classmethod
    def invalid_request(cls, message: str, data: Optional[dict] = None) -> "ToolError":
        return cls(message=message, code="invalid_request", data=data)

    @classmethod
    def internal_error(cls, message: str, data: Optional[dict] = None) -> "ToolError":
        return cls(message=message, code="internal_error", data=data)
