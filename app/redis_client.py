"""Redis access — a thin, fail-open wrapper.

Every helper degrades gracefully: if no ``REDIS_URL`` is configured, or Redis is
unreachable, cache reads miss, cache writes drop, rate-limit checks disable, and
publishes no-op. The service therefore behaves identically with or without
Redis — just uncached and unthrottled. Redis is a performance/protection layer,
never a correctness dependency.

The client is a lazily-built module singleton; tests inject a fake via
``set_client`` and clear it with ``reset_client``.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings

_client: Any = None
_initialized = False


def set_client(client: Any) -> None:
    """Inject a client (tests) and mark initialized."""
    global _client, _initialized
    _client = client
    _initialized = True


def reset_client() -> None:
    global _client, _initialized
    _client = None
    _initialized = False


def get_client() -> Any:
    """Return the shared async Redis client, or None when disabled."""
    global _client, _initialized
    if _initialized:
        return _client
    url = get_settings().redis_url
    if url:
        from redis.asyncio import from_url

        _client = from_url(url, encoding="utf-8", decode_responses=True)
    else:
        _client = None
    _initialized = True
    return _client


async def cache_get_json(key: str) -> Any | None:
    client = get_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
    except Exception:  # noqa: BLE001 - Redis is best-effort
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


async def cache_set_json(key: str, value: Any, ttl: int) -> None:
    client = get_client()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value), ex=ttl)
    except Exception:  # noqa: BLE001
        pass


async def incr_with_expiry(key: str, ttl: int) -> int | None:
    """Atomic-ish counter. Returns the new count, or None when Redis is off/down
    (caller treats None as 'no limit applied')."""
    client = get_client()
    if client is None:
        return None
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, ttl)
        return count
    except Exception:  # noqa: BLE001
        return None


async def list_push(key: str, value: Any, cap: int = 60, ttl: int = 86400) -> None:
    """Append to a capped list (keeps the last ``cap`` items). No-op without Redis."""
    client = get_client()
    if client is None:
        return
    try:
        await client.rpush(key, value)
        await client.ltrim(key, -cap, -1)
        await client.expire(key, ttl)
    except Exception:  # noqa: BLE001
        pass


async def list_pop_all(key: str) -> list[str]:
    """Return all list items and delete the key. Empty without Redis."""
    client = get_client()
    if client is None:
        return []
    try:
        vals = await client.lrange(key, 0, -1)
        await client.delete(key)
        return [v if isinstance(v, str) else v.decode() for v in vals]
    except Exception:  # noqa: BLE001
        return []


async def publish(channel: str, message: Any) -> None:
    client = get_client()
    if client is None:
        return
    try:
        await client.publish(channel, json.dumps(message))
    except Exception:  # noqa: BLE001
        pass
