"""Settlement receipts: persist and list x402 payments."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Settlement
from app.payments.facilitator import SettleResult


async def record_settlement(
    session: AsyncSession,
    *,
    request_id: str,
    api_key_id: int | None,
    requirements: dict,
    result: SettleResult,
    mode: str,
) -> Settlement:
    row = Settlement(
        request_id=request_id,
        api_key_id=api_key_id,
        scheme=requirements.get("scheme", "exact"),
        network=result.network or requirements.get("network"),
        asset=requirements.get("asset"),
        amount_atomic=requirements.get("amount"),
        payer=result.payer,
        pay_to=requirements.get("payTo"),
        tx_hash=result.transaction,
        status="settled" if result.success else "failed",
        mode=mode,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_settlements(
    session: AsyncSession,
    *,
    api_key_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Settlement]:
    stmt = select(Settlement).order_by(Settlement.created_at.desc())
    if api_key_id is not None:
        stmt = stmt.where(Settlement.api_key_id == api_key_id)
    stmt = stmt.limit(min(limit, 200)).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())
