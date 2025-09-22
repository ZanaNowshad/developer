"""Collection of local stubs used when external dependencies are unavailable."""

from . import celery, fastapi, opentelemetry, pydantic, pydantic_settings

__all__ = [
    "celery",
    "fastapi",
    "opentelemetry",
    "pydantic",
    "pydantic_settings",
]
