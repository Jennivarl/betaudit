"""ORM models: API keys and the per-call audit log.

These back Phase 2 (auth + metering + auditability). The audit row is a
flattened projection of the frozen VerifyResponse — enough to power the
portal's audit dashboard and per-call billing without re-parsing the JSON,
with the full response stashed in ``response_json`` for replay.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApiKey(Base):
    """An issued API key. Only the SHA-256 hash is stored; the plaintext is
    shown once at creation and never persisted."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(24), index=True)  # e.g. "rl_live_ab12cd"
    label: Mapped[str] = mapped_column(String(120), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    calls: Mapped[list["CallLog"]] = relationship(back_populates="api_key")


class CallLog(Base):
    """One row per billable /verify call — the audit + metering record."""

    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(40), index=True)
    api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id"), nullable=True, index=True
    )

    # Flattened projection of the response (dashboard + billing read these directly).
    market_url: Mapped[str] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(String(24), nullable=True)
    queried_side: Mapped[str | None] = mapped_column(String(40), nullable=True)
    action: Mapped[str | None] = mapped_column(String(24), nullable=True)
    resolution_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    oracle_state: Mapped[str | None] = mapped_column(String(24), nullable=True)
    mismatch_count: Mapped[int] = mapped_column(Integer, default=0)
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok | error
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # full replayable payload
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    api_key: Mapped["ApiKey | None"] = relationship(back_populates="calls")


class Settlement(Base):
    """An x402 payment receipt — one row per settled (or simulated) paid call."""

    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(40), index=True)
    api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id"), nullable=True, index=True
    )

    scheme: Mapped[str] = mapped_column(String(24))
    network: Mapped[str | None] = mapped_column(String(40), nullable=True)
    asset: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_atomic: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pay_to: Mapped[str | None] = mapped_column(String(64), nullable=True)

    tx_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="settled")  # settled | failed
    mode: Mapped[str] = mapped_column(String(16), default="simulate")   # simulate | live
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class MonitorSubscription(Base):
    """A market a caller asked us to watch for post-trade oracle changes."""

    __tablename__ = "monitor_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id"), nullable=True, index=True
    )

    platform: Mapped[str | None] = mapped_column(String(24), nullable=True)
    market_id: Mapped[str] = mapped_column(String(120))
    market_url: Mapped[str] = mapped_column(Text)
    queried_side: Mapped[str | None] = mapped_column(String(40), nullable=True)

    last_oracle_state: Mapped[str] = mapped_column(String(24))
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["MonitorEvent"]] = relationship(
        back_populates="subscription", order_by="MonitorEvent.created_at.desc()"
    )


class MonitorEvent(Base):
    """A detected oracle state change — the post-trade dispute alert."""

    __tablename__ = "monitor_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("monitor_subscriptions.id"), index=True
    )
    monitor_id: Mapped[str] = mapped_column(String(40), index=True)

    old_state: Mapped[str] = mapped_column(String(24))
    new_state: Mapped[str] = mapped_column(String(24))
    severity: Mapped[str] = mapped_column(String(12))  # high | medium | low
    message: Mapped[str] = mapped_column(Text)

    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    subscription: Mapped["MonitorSubscription"] = relationship(back_populates="events")
