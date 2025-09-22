"""OAuth2 style helpers for API endpoints."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict, Optional

from .config import AppSettings

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
    scopes: Optional[list[str]] = None


@dataclass
class TokenInfo:
    username: str
    expires_at: datetime


class SecurityManager:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self.oauth2 = OAuth2PasswordBearer(tokenUrl="/oauth/token")
        self._tokens: Dict[str, TokenInfo] = {}
        self._lock = asyncio.Lock()

    async def issue_token(self, username: Optional[str] = None) -> str:
        username = username or self._settings.security.oauth_client_id
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self._settings.security.token_ttl_seconds
        )
        async with self._lock:
            self._tokens[token] = TokenInfo(username=username, expires_at=expires_at)
        return token

    async def authenticate(self, token: str) -> AuthenticatedUser:
        async with self._lock:
            info = self._tokens.get(token)
        if info is None or info.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED.value, "Invalid or expired token")
        return AuthenticatedUser(username=info.username, scopes=["tools"],)

    async def cleanup(self) -> None:
        async with self._lock:
            expired = [
                token for token, info in self._tokens.items() if info.expires_at < datetime.now(timezone.utc)
            ]
            for token in expired:
                del self._tokens[token]

    def dependency(self) -> Callable[..., Awaitable[AuthenticatedUser]]:
        async def current_user(token: Optional[str] = None) -> AuthenticatedUser:
            if not token:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED.value, "Missing bearer token")
            return await self.authenticate(token)

        return current_user


__all__ = ["AuthenticatedUser", "SecurityManager"]
