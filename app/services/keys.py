"""API-key issuance and verification.

Keys look like ``rl_live_<40 hex>``. We store only the SHA-256 hash plus a
short, non-secret ``prefix`` for display/audit. The plaintext is returned once
by :func:`issue_key` and never persisted.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey

_KEY_ENV = "live"
_PREFIX = f"rl_{_KEY_ENV}_"
_PREFIX_DISPLAY_LEN = len(_PREFIX) + 6  # rl_live_ + first 6 chars of the secret


def _hash(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


@dataclass
class IssuedKey:
    """Result of minting a key — carries the one-time plaintext."""

    plaintext: str
    record: ApiKey


async def issue_key(session: AsyncSession, *, label: str = "") -> IssuedKey:
    """Mint a new API key, persist its hash, and return the plaintext once."""
    secret = secrets.token_hex(20)  # 40 hex chars
    plaintext = f"{_PREFIX}{secret}"
    record = ApiKey(
        key_hash=_hash(plaintext),
        prefix=plaintext[:_PREFIX_DISPLAY_LEN],
        label=label or "",
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return IssuedKey(plaintext=plaintext, record=record)


async def verify_key(session: AsyncSession, plaintext: str) -> ApiKey | None:
    """Return the active ApiKey matching ``plaintext``, or None."""
    if not plaintext or not plaintext.startswith(_PREFIX):
        return None
    stmt = select(ApiKey).where(ApiKey.key_hash == _hash(plaintext), ApiKey.active.is_(True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def touch_usage(session: AsyncSession, key: ApiKey) -> None:
    """Record one use against a key (metering). Caller commits or relies on us."""
    key.call_count += 1
    key.last_used_at = datetime.now(timezone.utc)
    await session.commit()
