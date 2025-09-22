from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .config import AppSettings
from .tooling import Tool

try:  # pragma: no cover - executed when dependency exists
    from fastapi import HTTPException, status
    from fastapi.security import OAuth2PasswordBearer
except ModuleNotFoundError:  # pragma: no cover - fallback path
    from .stubs.fastapi import HTTPException, OAuth2PasswordBearer, status

try:  # pragma: no cover
    from pydantic import BaseModel
except ModuleNotFoundError:  # pragma: no cover
    from .stubs.pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    username: str
    roles: List[str]
    scopes: Optional[List[str]] = None


@dataclass
class TokenInfo:
    username: str
    expires_at: datetime
    roles: Tuple[str, ...]


class SecurityManager:
    """Manages OAuth token issuance and role-based access control."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self.oauth2 = OAuth2PasswordBearer(tokenUrl="/oauth/token")
        self._tokens: Dict[str, TokenInfo] = {}
        self._lock = asyncio.Lock()

    async def issue_token(
        self,
        username: Optional[str] = None,
        roles: Optional[Sequence[str]] = None,
    ) -> str:
        """Issue a bearer token for the specified user and roles."""

        username = username or self._settings.security.oauth_client_id
        normalized_roles = self._normalize_roles(roles)
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self._settings.security.token_ttl_seconds
        )
        async with self._lock:
            self._tokens[token] = TokenInfo(
                username=username, expires_at=expires_at, roles=normalized_roles
            )
        return token

    async def authenticate(self, token: str) -> AuthenticatedUser:
        async with self._lock:
            info = self._tokens.get(token)
        if info is None or info.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED.value, "Invalid or expired token")
        return AuthenticatedUser(username=info.username, roles=list(info.roles), scopes=["tools"])

    async def cleanup(self) -> None:
        async with self._lock:
            expired = [
                token for token, info in self._tokens.items() if info.expires_at < datetime.now(timezone.utc)
            ]
            for token in expired:
                del self._tokens[token]

    def authorize_tool(self, user: AuthenticatedUser, tool: Tool | Dict[str, Any]) -> None:
        """Ensure the user has permission to invoke the provided tool."""

        name, tags = self._tool_metadata(tool)
        if self._is_permitted(name, tags, user.roles):
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN.value, "Insufficient role permissions")

    def filter_tools(self, user: AuthenticatedUser, tools: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return only the tools the user is authorised to access."""

        permitted: List[Dict[str, Any]] = []
        for tool in tools:
            name, tags = self._tool_metadata(tool)
            if self._is_permitted(name, tags, user.roles):
                permitted.append(tool)
        return permitted

    def require_plugin_admin(self, user: AuthenticatedUser) -> None:
        """Enforce plugin administration privileges for the user."""

        admin_roles = set(self._settings.security.plugin_admin_roles)
        if not admin_roles.intersection(user.roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN.value, "Insufficient role permissions")

    def dependency(self) -> Callable[..., Awaitable[AuthenticatedUser]]:
        async def current_user(token: Optional[str] = None) -> AuthenticatedUser:
            if not token:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED.value, "Missing bearer token")
            return await self.authenticate(token)

        return current_user

    def _normalize_roles(self, roles: Optional[Sequence[str]]) -> Tuple[str, ...]:
        candidates = list(roles or self._settings.security.default_roles)
        if not candidates:
            candidates = list(self._settings.security.default_roles)
        unique: List[str] = []
        for role in candidates:
            if role and role not in unique:
                unique.append(role)
        return tuple(unique)

    def _tool_metadata(self, tool: Tool | Dict[str, Any]) -> Tuple[str, Tuple[str, ...]]:
        if isinstance(tool, Tool):
            return tool.name, tuple(tool.tags)
        name = str(tool.get("name", ""))
        raw_tags = tool.get("tags") or []
        tags = tuple(str(tag) for tag in raw_tags if isinstance(tag, str))
        return name, tags

    def _is_permitted(self, name: str, tags: Sequence[str], roles: Sequence[str]) -> bool:
        permissions = self._collect_permissions(roles)
        for permission in permissions:
            if self._permission_matches(name, tags, permission):
                return True
        return False

    def _collect_permissions(self, roles: Sequence[str]) -> Tuple[str, ...]:
        permissions: List[str] = []
        config = self._settings.security.role_permissions
        for role in roles:
            for permission in config.get(role, []):
                if permission not in permissions:
                    permissions.append(permission)
        return tuple(permissions)

    @staticmethod
    def _permission_matches(name: str, tags: Sequence[str], permission: str) -> bool:
        if permission == "*":
            return True
        if permission.startswith("tool:"):
            target = permission.split(":", 1)[1]
            return target == name
        if permission.startswith("tag:"):
            target = permission.split(":", 1)[1]
            if target == "*":
                return True
            return target in tags
        if permission in tags:
            return True
        return permission == name


__all__ = ["AuthenticatedUser", "SecurityManager"]
