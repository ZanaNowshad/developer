"""OpenTelemetry integration helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Awaitable, Callable, Dict, Iterator, Optional

from .config import AppSettings
from .content import CallToolResult
from .errors import ToolError

try:  # pragma: no cover - executed when optional dependency exists
    from opentelemetry import trace
    from opentelemetry.trace import Span, Status, StatusCode, Tracer
except ModuleNotFoundError:  # pragma: no cover - fallback path
    from .stubs.opentelemetry import Span, Status, StatusCode, Tracer, trace


def setup_tracer(settings: AppSettings) -> Tracer:
    """Configure and return an OpenTelemetry tracer.

    When an OTLP endpoint is configured and optional dependencies are available the
    tracer provider is initialised with an OTLP HTTP exporter. Otherwise the global
    tracer is returned to ensure tracing remains optional.
    """

    tracer = trace.get_tracer(settings.telemetry.service_name)
    endpoint = settings.telemetry.exporter_endpoint
    if not endpoint:
        return tracer

    try:  # pragma: no cover - optional dependencies
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ModuleNotFoundError:
        return tracer

    try:
        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.telemetry.service_name})
        )
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        tracer = trace.get_tracer(settings.telemetry.service_name)
    except Exception:  # pragma: no cover - defensive guard
        pass
    return tracer


@contextmanager
def traced(tracer: Tracer, name: str) -> Iterator[Optional[Span]]:
    span_cm = tracer.start_as_current_span(name)
    with span_cm as span:
        yield span


async def traced_async(
    tracer: Tracer,
    name: str,
    func: Callable[[Optional[Span]], Awaitable[Any]],
    *,
    attributes: Optional[Dict[str, Any]] = None,
) -> Any:
    span_cm = tracer.start_as_current_span(name)
    with span_cm as span:
        if attributes:
            for key, value in attributes.items():
                _set_attribute(span, key, value)
        try:
            return await func(span)
        except Exception as exc:
            _record_exception(span, exc)
            raise


def annotate_tool_result(span: Optional[Span], tool_name: str, result: CallToolResult) -> None:
    """Attach metadata about the tool execution to the active span."""

    _set_attribute(span, "developer.tool", tool_name)
    _set_attribute(span, "developer.success", result.success)
    if result.success:
        _set_status(span, StatusCode.OK, "success")
        return

    message = result.error or "tool returned an error"
    _set_status(span, StatusCode.ERROR, message)
    _add_event(
        span,
        "tool.error",
        {
            "message": message,
            "code": result.code or "",
        },
    )


def annotate_tool_error(span: Optional[Span], error: ToolError) -> None:
    """Record ToolError details on the active span."""

    _add_event(
        span,
        "tool.exception",
        {
            "message": error.message,
            "code": error.code,
        },
    )
    _record_exception(span, error)


def _set_attribute(span: Optional[Span], key: str, value: Any) -> None:
    if span is None:
        return
    setter = getattr(span, "set_attribute", None)
    if callable(setter):  # pragma: no branch - defensive
        setter(key, value)


def _add_event(span: Optional[Span], name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    if span is None:
        return
    adder = getattr(span, "add_event", None)
    if callable(adder):  # pragma: no branch - defensive
        adder(name, attributes or {})


def _set_status(span: Optional[Span], status_code: Any, description: str) -> None:
    if span is None or Status is None or StatusCode is None:
        return
    setter = getattr(span, "set_status", None)
    if callable(setter):  # pragma: no branch - defensive
        try:
            setter(Status(status_code=status_code, description=description))
        except Exception:  # pragma: no cover - defensive
            pass


def _record_exception(span: Optional[Span], error: BaseException) -> None:
    if span is None:
        return
    recorder = getattr(span, "record_exception", None)
    if callable(recorder):  # pragma: no branch - defensive
        try:
            recorder(error)
        except Exception:  # pragma: no cover - defensive
            pass
    _set_status(span, StatusCode.ERROR if StatusCode else None, str(error))


__all__ = [
    "annotate_tool_error",
    "annotate_tool_result",
    "setup_tracer",
    "traced",
    "traced_async",
]
