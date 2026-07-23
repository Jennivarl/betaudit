"""Per-API-key rate limiting, backed by Redis counters.

A fixed-window counter per key per minute (``rate:{key_id}:{YYYYMMDDHHMM}``).
Fail-open: when Redis is off or unreachable the counter returns None and the
request passes — protection, never a hard dependency. Runs right after API-key
auth, so it throttles authenticated callers before any expensive work.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status

from app import redis_client
from app.config import get_settings
from app.models import ApiKey
from app.security import require_api_key


async def enforce_rate_limit(api_key: ApiKey = Depends(require_api_key)) -> ApiKey:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return api_key

    minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    key = f"rate:{api_key.id}:{minute}"
    count = await redis_client.incr_with_expiry(key, ttl=70)
    if count is not None and count > settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({settings.rate_limit_per_minute}/min).",
            headers={"Retry-After": "60"},
        )
    return api_key
