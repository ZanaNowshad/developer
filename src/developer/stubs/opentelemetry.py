from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class StatusCode(Enum):
    OK = "OK"
    ERROR = "ERROR"


@dataclass
class Status:
    status_code: StatusCode
    description: str = ""


class Span:
    """Very small stand-in for an OpenTelemetry span."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: Dict[str, Any] = {}
        self.events: List[Tuple[str, Dict[str, Any]]] = []
        self.exceptions: List[BaseException] = []
        self.status: Optional[Status] = None

    def __enter__(self) -> "Span":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:  # pragma: no cover - trivial
        return None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Dict[str, Any]) -> None:
        self.events.append((name, dict(attributes)))

    def record_exception(self, exc: BaseException) -> None:
        self.exceptions.append(exc)

    def set_status(self, status: Status) -> None:
        self.status = status


class Tracer:
    """Simple tracer that records created spans for inspection in tests."""

    def __init__(self) -> None:
        self.spans: List[Span] = []

    def start_as_current_span(self, name: str) -> Span:  # type: ignore[override]
        span = Span(name)
        self.spans.append(span)
        return span


class TracerProvider:
    def __init__(self) -> None:
        self._tracer = Tracer()

    def get_tracer(self, name: str) -> Tracer:
        return self._tracer

    def add_span_processor(self, processor: Any) -> None:  # pragma: no cover - noop
        return None


class Meter:
    def create_counter(self, name: str):  # pragma: no cover - unused in tests
        return lambda *args, **kwargs: None


class _TraceModule:
    def __init__(self) -> None:
        self._provider: TracerProvider = TracerProvider()

    def get_tracer(self, name: str) -> Tracer:
        return self._provider.get_tracer(name)

    def set_tracer_provider(self, provider: TracerProvider) -> None:
        self._provider = provider

    def get_tracer_provider(self) -> TracerProvider:
        return self._provider


class _MetricsModule:
    def get_meter(self, name: str) -> Meter:
        return Meter()


trace = _TraceModule()
metrics = _MetricsModule()

__all__ = [
    "Meter",
    "Span",
    "Status",
    "StatusCode",
    "Tracer",
    "TracerProvider",
    "metrics",
    "trace",
]
