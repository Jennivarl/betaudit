"""Management DTOs for the developer portal (keys + audit).

Deliberately separate from ``schemas.py`` (the frozen verification contract):
these shapes serve the portal/admin surface and can evolve independently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import ApiKey, CallLog, MonitorEvent, MonitorSubscription, Settlement


class CreateKeyRequest(BaseModel):
    label: str = Field(default="", max_length=120, description="Human label for the key.")


class ApiKeyOut(BaseModel):
    id: int
    prefix: str
    label: str
    active: bool
    call_count: int
    created_at: datetime
    last_used_at: Optional[datetime] = None

    @classmethod
    def from_orm_key(cls, k: ApiKey) -> "ApiKeyOut":
        return cls(
            id=k.id,
            prefix=k.prefix,
            label=k.label,
            active=k.active,
            call_count=k.call_count,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )


class CreatedKeyOut(ApiKeyOut):
    """Returned once at creation — includes the one-time plaintext secret."""

    api_key: str = Field(..., description="Full secret. Shown once; store it now.")


class CallLogOut(BaseModel):
    request_id: str
    market_url: str
    platform: Optional[str] = None
    queried_side: Optional[str] = None
    action: Optional[str] = None
    resolution_risk_score: Optional[int] = None
    confidence: Optional[float] = None
    oracle_state: Optional[str] = None
    mismatch_count: int
    llm_used: bool
    status: str
    error_code: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: datetime

    @classmethod
    def from_orm_log(cls, c: CallLog) -> "CallLogOut":
        return cls(
            request_id=c.request_id,
            market_url=c.market_url,
            platform=c.platform,
            queried_side=c.queried_side,
            action=c.action,
            resolution_risk_score=c.resolution_risk_score,
            confidence=c.confidence,
            oracle_state=c.oracle_state,
            mismatch_count=c.mismatch_count,
            llm_used=c.llm_used,
            status=c.status,
            error_code=c.error_code,
            latency_ms=c.latency_ms,
            created_at=c.created_at,
        )


class SettlementOut(BaseModel):
    request_id: str
    scheme: str
    network: Optional[str] = None
    asset: Optional[str] = None
    amount_atomic: Optional[str] = None
    payer: Optional[str] = None
    pay_to: Optional[str] = None
    tx_hash: Optional[str] = None
    status: str
    mode: str
    created_at: datetime

    @classmethod
    def from_orm_settlement(cls, s: Settlement) -> "SettlementOut":
        return cls(
            request_id=s.request_id,
            scheme=s.scheme,
            network=s.network,
            asset=s.asset,
            amount_atomic=s.amount_atomic,
            payer=s.payer,
            pay_to=s.pay_to,
            tx_hash=s.tx_hash,
            status=s.status,
            mode=s.mode,
            created_at=s.created_at,
        )


class SetWebhookRequest(BaseModel):
    webhook_url: str = Field(..., description="HTTPS URL to POST dispute alerts to.")


class MonitorSubscriptionOut(BaseModel):
    monitor_id: str
    platform: Optional[str] = None
    market_id: str
    market_url: str
    queried_side: Optional[str] = None
    last_oracle_state: str
    webhook_url: Optional[str] = None
    active: bool
    created_at: datetime
    last_checked_at: Optional[datetime] = None

    @classmethod
    def from_orm_sub(cls, s: MonitorSubscription) -> "MonitorSubscriptionOut":
        return cls(
            monitor_id=s.monitor_id,
            platform=s.platform,
            market_id=s.market_id,
            market_url=s.market_url,
            queried_side=s.queried_side,
            last_oracle_state=s.last_oracle_state,
            webhook_url=s.webhook_url,
            active=s.active,
            created_at=s.created_at,
            last_checked_at=s.last_checked_at,
        )


class MonitorEventOut(BaseModel):
    monitor_id: str
    old_state: str
    new_state: str
    severity: str
    message: str
    delivered: bool
    delivery_error: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_orm_event(cls, e: MonitorEvent) -> "MonitorEventOut":
        return cls(
            monitor_id=e.monitor_id,
            old_state=e.old_state,
            new_state=e.new_state,
            severity=e.severity,
            message=e.message,
            delivered=e.delivered,
            delivery_error=e.delivery_error,
            created_at=e.created_at,
        )
