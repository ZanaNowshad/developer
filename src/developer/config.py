"""Configuration management using a Pydantic style settings object."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

try:  # pragma: no cover - executed when optional dependency exists
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # pragma: no cover - executed in constrained environments
    from .stubs.pydantic import BaseModel, Field

try:  # pragma: no cover
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover
    from .stubs.pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseModel):
    oauth_client_id: str = Field(default="developer-local", description="OAuth client identifier")
    oauth_client_secret: str = Field(default="developer-secret", description="Client secret")
    token_ttl_seconds: int = Field(default=3_600, description="Token lifetime")
    default_roles: List[str] = Field(
        default_factory=lambda: ["developer"],
        description="Roles granted to tokens when none are specified",
    )
    role_permissions: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "developer": ["tag:*"],
            "observer": ["tag:core"],
            "admin": ["*"],
        },
        description=(
            "Mapping of role names to permission strings supporting '*' for all tools, "
            "'tool:<name>' for specific tools, and 'tag:<tag>' for tagged tools."
        ),
    )
    plugin_admin_roles: List[str] = Field(
        default_factory=lambda: ["admin"],
        description="Roles permitted to reload or manage plugins",
    )


class TelemetrySettings(BaseModel):
    exporter_endpoint: Optional[str] = Field(default=None, description="OTLP endpoint URI")
    service_name: str = Field(default="developer-platform", description="Telemetry service name")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVELOPER_", extra="allow")

    workspace_root: str = Field(default_factory=lambda: str(Path.cwd()))
    database_url: str = Field(default="sqlite+aiosqlite:///./developer.db")
    redis_url: str = Field(default="memory://")
    celery_broker_url: str = Field(default="memory://")
    celery_backend_url: str = Field(default="memory://")
    enabled_plugins: List[str] = Field(default_factory=list)
    tools_cache_ttl_seconds: int = Field(
        default=30,
        description="Seconds to cache tool metadata responses",
    )
    text_editor_max_history: int = Field(
        default=10,
        description="Number of undo history entries to retain per file",
    )
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)

    def plugin_modules(self) -> List[str]:
        return list(self.enabled_plugins)

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace_root)


__all__ = ["AppSettings", "SecuritySettings", "TelemetrySettings"]
