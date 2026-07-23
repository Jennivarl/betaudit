"""Per-call audit logging + retrieval.

One CallLog row per /verify call, success or failure. The row is a flat
projection of the frozen VerifyResponse so the dashboard and billing can read
it without re-parsing JSON; the full payload is kept in ``response_json``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CallLog
from app.schemas import ErrorResponse, VerifyResponse


async def record_success(
    session: AsyncSession,
    *,
    response: VerifyResponse,
    api_key_id: int | None,
    llm_used: bool,
    latency_ms: int | None,
) -> CallLog:
    row = CallLog(
        request_id=response.request_id,
        api_key_id=api_key_id,
        market_url=response.market_url,
        platform=response.platform.value,
        queried_side=response.queried_side,
        action=response.action.value,
        resolution_risk_score=response.resolution_risk_score,
        confidence=response.confidence,
        oracle_state=response.parsed_contract_data.current_oracle_state.value,
        mismatch_count=len(response.rule_mismatches_detected),
        llm_used=llm_used,
        status="ok",
        latency_ms=latency_ms,
        response_json=response.model_dump_json(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def record_error(
    session: AsyncSession,
    *,
    error: ErrorResponse,
    market_url: str,
    queried_side: str | None,
    api_key_id: int | None,
    latency_ms: int | None,
) -> CallLog:
    row = CallLog(
        request_id=error.request_id,
        api_key_id=api_key_id,
        market_url=market_url,
        queried_side=queried_side,
        status="error",
        error_code=error.error_code.value,
        latency_ms=latency_ms,
        response_json=error.model_dump_json(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_logs(
    session: AsyncSession,
    *,
    api_key_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CallLog]:
    stmt = select(CallLog).order_by(CallLog.created_at.desc())
    if api_key_id is not None:
        stmt = stmt.where(CallLog.api_key_id == api_key_id)
    stmt = stmt.limit(min(limit, 200)).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())
