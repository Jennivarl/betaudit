"""Oracle monitor — the post-trade half of the product.

A caller subscribes a market (via ``subscribe_monitor`` on /verify). A poller
re-resolves each active subscription, and when the oracle state changes it
records a ``MonitorEvent`` (the dispute alert) and best-effort delivers it to
the subscription's webhook. Telegram delivery is layered on in Phase 6.

The detection logic (:func:`poll_subscription`) is a plain async function with
the resolver injectable, so it is tested deterministically without a network or
the background loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import MonitorEvent, MonitorSubscription
from app.resolvers import resolve_market
from app.resolvers.base import ResolvedMarket, ResolverError
from app.schemas import OracleState

# States that end a subscription's useful life.
_TERMINAL = {OracleState.RESOLVED.value}


def classify(old_state: str, new_state: str) -> tuple[str, str]:
    """Map a state transition to (severity, human message)."""
    if new_state == OracleState.DISPUTED.value:
        return "high", "Oracle proposal is now DISPUTED — the resolution is contested."
    if new_state == OracleState.RESOLVED.value:
        return "high", "Market has RESOLVED on-chain — verify the outcome against your position."
    if new_state == OracleState.PROPOSED.value:
        return "medium", "An outcome has been PROPOSED — the challenge window is open."
    if new_state == OracleState.UNDISPUTED.value:
        return "medium", "Proposal is UNDISPUTED and finalizing — last window to challenge."
    return "low", f"Oracle state changed from {old_state} to {new_state}."


async def create_subscription(
    session: AsyncSession,
    *,
    monitor_id: str,
    api_key_id: int | None,
    market: ResolvedMarket,
    queried_side: str | None,
    telegram_chat_id: str | None = None,
) -> MonitorSubscription:
    sub = MonitorSubscription(
        monitor_id=monitor_id,
        api_key_id=api_key_id,
        platform=market.platform.value,
        market_id=market.market_id,
        market_url=market.market_url,
        queried_side=queried_side,
        last_oracle_state=market.current_oracle_state.value,
        telegram_chat_id=telegram_chat_id,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


async def get_subscription(
    session: AsyncSession, monitor_id: str, *, api_key_id: int | None = None
) -> MonitorSubscription | None:
    stmt = select(MonitorSubscription).where(MonitorSubscription.monitor_id == monitor_id)
    if api_key_id is not None:
        stmt = stmt.where(MonitorSubscription.api_key_id == api_key_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_subscriptions(
    session: AsyncSession, *, api_key_id: int | None = None, limit: int = 50, offset: int = 0
) -> list[MonitorSubscription]:
    stmt = select(MonitorSubscription).order_by(MonitorSubscription.created_at.desc())
    if api_key_id is not None:
        stmt = stmt.where(MonitorSubscription.api_key_id == api_key_id)
    stmt = stmt.limit(min(limit, 200)).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_by_chat(
    session: AsyncSession, telegram_chat_id: str, *, active_only: bool = True
) -> list[MonitorSubscription]:
    stmt = select(MonitorSubscription).where(
        MonitorSubscription.telegram_chat_id == telegram_chat_id
    )
    if active_only:
        stmt = stmt.where(MonitorSubscription.active.is_(True))
    stmt = stmt.order_by(MonitorSubscription.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def deactivate_by_chat(session: AsyncSession, telegram_chat_id: str) -> int:
    subs = await list_by_chat(session, telegram_chat_id, active_only=True)
    for s in subs:
        s.active = False
    await session.commit()
    return len(subs)


async def list_events(
    session: AsyncSession,
    *,
    api_key_id: int | None = None,
    monitor_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MonitorEvent]:
    stmt = select(MonitorEvent).order_by(MonitorEvent.created_at.desc())
    if monitor_id is not None:
        stmt = stmt.where(MonitorEvent.monitor_id == monitor_id)
    if api_key_id is not None:
        stmt = stmt.join(
            MonitorSubscription, MonitorEvent.subscription_id == MonitorSubscription.id
        ).where(MonitorSubscription.api_key_id == api_key_id)
    stmt = stmt.limit(min(limit, 200)).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def poll_subscription(
    session: AsyncSession, sub: MonitorSubscription, *, resolver=None
) -> MonitorEvent | None:
    """Re-resolve one subscription; record + deliver an event if the state changed."""
    # Resolve the callable at call time so the module global stays monkeypatchable.
    resolve = resolver or resolve_market
    try:
        market = await resolve(sub.market_url, sub.queried_side)
    except ResolverError:
        sub.last_checked_at = datetime.now(timezone.utc)
        await session.commit()
        return None

    new_state = market.current_oracle_state.value
    sub.last_checked_at = datetime.now(timezone.utc)

    # Ignore no-ops and transitions into UNKNOWN (avoid alerting on lost signal).
    if new_state == sub.last_oracle_state or new_state == OracleState.UNKNOWN.value:
        await session.commit()
        return None

    severity, message = classify(sub.last_oracle_state, new_state)
    event = MonitorEvent(
        subscription_id=sub.id,
        monitor_id=sub.monitor_id,
        old_state=sub.last_oracle_state,
        new_state=new_state,
        severity=severity,
        message=message,
    )
    sub.last_oracle_state = new_state
    if new_state in _TERMINAL:
        sub.active = False
    session.add(event)
    await session.commit()
    await session.refresh(event)

    await _deliver(sub, event, session)
    return event


async def poll_all_active(session: AsyncSession) -> list[MonitorEvent]:
    result = await session.execute(
        select(MonitorSubscription).where(MonitorSubscription.active.is_(True))
    )
    events: list[MonitorEvent] = []
    for sub in result.scalars().all():
        event = await poll_subscription(session, sub)
        if event is not None:
            events.append(event)
    return events


async def _deliver(
    sub: MonitorSubscription, event: MonitorEvent, session: AsyncSession
) -> None:
    """Best-effort delivery to the subscription's channels (Telegram + webhook).

    Failures are recorded, never raised, so the poller never dies on delivery."""
    settings = get_settings()
    delivered = False
    error: str | None = None

    # Telegram push (if this subscription came from the bot).
    if sub.telegram_chat_id and settings.telegram_bot_token:
        try:
            from app import telegram

            await telegram.send_message(
                sub.telegram_chat_id,
                telegram.format_alert(sub, event),
                settings.telegram_bot_token,
            )
            delivered = True
        except Exception as exc:  # noqa: BLE001
            error = f"telegram: {str(exc)[:200]}"

    # Webhook (if configured).
    if sub.webhook_url:
        payload = {
            "monitor_id": sub.monitor_id,
            "market_url": sub.market_url,
            "market_id": sub.market_id,
            "queried_side": sub.queried_side,
            "old_state": event.old_state,
            "new_state": event.new_state,
            "severity": event.severity,
            "message": event.message,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.monitor_webhook_timeout_seconds) as client:
                resp = await client.post(sub.webhook_url, json=payload)
                resp.raise_for_status()
            delivered = True
        except Exception as exc:  # noqa: BLE001
            error = f"webhook: {str(exc)[:200]}"

    event.delivered = delivered
    event.delivery_error = error
    await session.commit()


async def run_loop() -> None:
    """Background poller. Started in lifespan only when monitor_enabled is true."""
    interval = get_settings().monitor_interval_seconds
    while True:
        try:
            maker = get_sessionmaker()
            async with maker() as session:
                await poll_all_active(session)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - never let the loop die on a transient error
            pass
        await asyncio.sleep(interval)
