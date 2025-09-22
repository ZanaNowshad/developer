import asyncio

import pytest

from developer.content import CallToolResult, Content
from developer.errors import ToolError
from developer.observability import (
    annotate_tool_error,
    annotate_tool_result,
    traced_async,
)
from developer.stubs import opentelemetry as otel_stub


def test_annotate_tool_result_records_success() -> None:
    tracer = otel_stub.trace.get_tracer("success-test")
    with tracer.start_as_current_span("tool.success") as span:
        result = CallToolResult.success_result([Content.text_content("ok")])
        annotate_tool_result(span, "demo", result)
    recorded = tracer.spans[-1]
    assert recorded.attributes["developer.tool"] == "demo"
    assert recorded.attributes["developer.success"] is True
    assert recorded.status is not None
    assert recorded.status.status_code == otel_stub.StatusCode.OK


def test_annotate_tool_error_records_failure() -> None:
    tracer = otel_stub.trace.get_tracer("error-test")
    with tracer.start_as_current_span("tool.error") as span:
        error = ToolError.invalid_params("bad input")
        annotate_tool_error(span, error)
        result = CallToolResult.error_result("bad input", code=error.code)
        annotate_tool_result(span, "flaky", result)
    recorded = tracer.spans[-1]
    assert recorded.status is not None
    assert recorded.status.status_code == otel_stub.StatusCode.ERROR
    assert any(name == "tool.exception" for name, _ in recorded.events)
    assert any(name == "tool.error" for name, _ in recorded.events)


def test_traced_async_records_exceptions() -> None:
    tracer = otel_stub.trace.get_tracer("async-test")

    async def _boom(span) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(traced_async(tracer, "tool.boom", _boom))

    recorded = tracer.spans[-1]
    assert any(isinstance(exc, RuntimeError) for exc in recorded.exceptions)
