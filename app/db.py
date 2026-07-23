"""Async database layer — engine, session factory, and schema init.

SQLAlchemy 2.0 async. SQLite (aiosqlite) in dev, Postgres (asyncpg) in prod.
The public API is intentionally tiny:

    init_engine(url)     -> (re)build the engine + sessionmaker for a URL
    async init_db()      -> create tables if they don't exist
    async get_session()  -> FastAPI dependency yielding an AsyncSession

Tests point ``database_url`` at an isolated sqlite file (or :memory:) and call
init_engine() + init_db() in a fixture, so nothing here touches the network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _async_url(url: str) -> str:
    """Normalize a sync-style URL to its async driver variant."""
    if url.startswith("sqlite+aiosqlite:") or url.startswith("postgresql+asyncpg:"):
        return url
    if url.startswith("sqlite:"):
        return url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    if url.startswith("postgresql:"):
        return url.replace("postgresql:", "postgresql+asyncpg:", 1)
    if url.startswith("postgres:"):
        return url.replace("postgres:", "postgresql+asyncpg:", 1)
    return url


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(url: str | None = None) -> AsyncEngine:
    """Build (or rebuild) the engine + session factory for ``url``.

    Called once at startup and again by tests to retarget an isolated DB.
    """
    global _engine, _sessionmaker
    resolved = _async_url(url or get_settings().database_url)
    _engine = create_async_engine(resolved, future=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        init_engine()
    assert _engine is not None
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def init_db() -> None:
    """Create tables that don't yet exist. Idempotent."""
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _apply_additive_migrations(engine)


# Small additive migrations for columns added after a table already exists in a
# deployed DB (create_all never ALTERs existing tables). Each runs in its own
# transaction and is ignored if already applied — safe and idempotent.
_MIGRATIONS = [
    "ALTER TABLE monitor_subscriptions ADD COLUMN telegram_chat_id VARCHAR",
]


async def _apply_additive_migrations(engine: AsyncEngine) -> None:
    from sqlalchemy import text

    for stmt in _MIGRATIONS:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception:  # noqa: BLE001 - column already exists / dialect variance
            pass


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, always close it."""
    maker = get_sessionmaker()
    async with maker() as session:
        yield session
