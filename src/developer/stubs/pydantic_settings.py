"""Shim for pydantic_settings.BaseSettings used when the real package is unavailable."""

from __future__ import annotations

from typing import Any, Dict

from .pydantic import BaseSettings as _BaseSettings, ConfigDict as _ConfigDict


class BaseSettings(_BaseSettings):
    """Alias that mirrors pydantic-settings behaviour."""

    pass


def SettingsConfigDict(**kwargs: Any) -> Dict[str, Any]:
    return _ConfigDict(**kwargs)


__all__ = ["BaseSettings", "SettingsConfigDict"]
