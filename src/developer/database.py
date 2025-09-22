"""Database layer with optional SQLAlchemy 2.0 async support."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import AppSettings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

try:  # pragma: no cover - executed when dependency exists
    from sqlalchemy import DateTime, Integer, String, Text, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
except ModuleNotFoundError:  # pragma: no cover - fallback path used in CI
    DeclarativeBase = None  # type: ignore
    Mapped = Any  # type: ignore
    mapped_column = None  # type: ignore
    AsyncSession = object  # type: ignore
    create_async_engine = None  # type: ignore
    async_sessionmaker = None  # type: ignore
    select = None  # type: ignore


@dataclass
class ToolInvocationRecord:
    tool_name: str
    payload: Dict[str, Any]
    created_at: datetime


if DeclarativeBase is not None:  # pragma: no branch

    class Base(DeclarativeBase):
        pass


    class ToolInvocation(Base):
        __tablename__ = "tool_invocations"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        tool_name: Mapped[str] = mapped_column(String(128))
        payload_json: Mapped[str] = mapped_column(Text)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

else:  # pragma: no cover - fallback path
    Base = object
    ToolInvocation = None  # type: ignore


class AsyncDatabase:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._memory: List[ToolInvocationRecord] = []
        self._lock = asyncio.Lock()
        self._engine = None
        self._sessionmaker: Optional[Any] = None
        if create_async_engine is not None:
            self._engine = create_async_engine(settings.database_url, echo=False, future=True)
            self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def connect(self) -> None:
        if self._engine is not None:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    async def disconnect(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()

    async def record(self, tool_name: str, payload: Dict[str, Any]) -> None:
        if self._sessionmaker is None:
            async with self._lock:
                self._memory.append(
                    ToolInvocationRecord(
                        tool_name=tool_name,
                        payload=payload,
                        created_at=_utcnow(),
                    )
                )
            return

        async with self._sessionmaker() as session:  # type: ignore[operator]
            await self._insert_record(session, tool_name, payload)

    async def recent(self, limit: int = 20) -> List[ToolInvocationRecord]:
        if self._sessionmaker is None:
            async with self._lock:
                return list(sorted(self._memory, key=lambda item: item.created_at)[-limit:])

        async with self._sessionmaker() as session:  # type: ignore[operator]
            stmt = select(ToolInvocation).order_by(ToolInvocation.created_at.desc()).limit(limit)
            rows = await session.scalars(stmt)
            return [
                ToolInvocationRecord(
                    tool_name=row.tool_name,
                    payload=json.loads(row.payload_json),
                    created_at=row.created_at,
                )
                for row in rows
            ]

    async def _insert_record(self, session: AsyncSession, tool_name: str, payload: Dict[str, Any]) -> None:
        record = ToolInvocation(
            tool_name=tool_name,
            payload_json=json.dumps(payload),
            created_at=_utcnow(),
        )
        session.add(record)
        await session.commit()


__all__ = ["AsyncDatabase", "ToolInvocationRecord"]
