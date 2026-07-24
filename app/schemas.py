"""Frozen public contract for the Resolution Simulation Layer.

This module is the single source of truth for the request/response shapes that
EVERY consumer depends on: the /verify-resolution-rules endpoint, the developer
portal playground, the agent audit dashboard, the Telegram bot, and per-call
billing. Treat changes here as breaking — bump ``SCHEMA_VERSION`` and add a
migration note rather than silently reshaping fields.

The user-supplied core fields are preserved exactly:
    market_id, resolution_risk_score, action, parsed_contract_data{...},
    rule_mismatches_detected[]{clause, trader_thesis, conflict_reason}
Everything else is a thin envelope the consumers need (ids, timestamps,
explainability, monitoring hooks) and does not alter those semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Action(str, Enum):
    """Three-way verdict an integrating agent acts on."""

    PROCEED = "PROCEED"
    CAUTION = "CAUTION"
    ABORT_TRADE = "ABORT_TRADE"


class OracleState(str, Enum):
    """Lifecycle of the market's resolution oracle at check time."""

    UNRESOLVED = "UNRESOLVED"       # market open, no proposal yet
    PROPOSED = "PROPOSED"           # an outcome has been proposed
    DISPUTED = "DISPUTED"           # a proposal is under active dispute
    UNDISPUTED = "UNDISPUTED"       # proposed and past challenge window, unchallenged
    RESOLVED = "RESOLVED"           # finalized on-chain
    UNKNOWN = "UNKNOWN"             # could not be determined


class Platform(str, Enum):
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"              # reserved — Phase 2 adapter


# --------------------------------------------------------------------------- #
# Request
# --------------------------------------------------------------------------- #
class VerifyRequest(BaseModel):
    """Input to POST /verify-resolution-rules."""

    market_url: str = Field(
        ...,
        description="Canonical URL of the target prediction market.",
        examples=["https://polymarket.com/event/company-x-releases-product-y"],
    )
    queried_side: Optional[str] = Field(
        default=None,
        description="Outcome the agent intends to buy (e.g. 'YES'). Sharpens mismatch detection.",
        examples=["YES"],
    )
    subscribe_monitor: bool = Field(
        default=False,
        description="If true, register this market for post-trade oracle dispute alerts.",
    )


# --------------------------------------------------------------------------- #
# Response — core (user-frozen) sub-objects
# --------------------------------------------------------------------------- #
class ParsedContractData(BaseModel):
    """Oracle / resolution metadata extracted from the market's real rules."""

    oracle_type: str = Field(..., examples=["UMA_OOv2"])
    challenge_window_hours: Optional[float] = Field(
        default=None, description="Dispute/challenge window length in hours."
    )
    source_of_truth_specified: Optional[str] = Field(
        default=None,
        description="The authoritative source the rules require for resolution.",
        examples=["Official SEC 8-K Filing"],
    )
    current_oracle_state: OracleState = OracleState.UNKNOWN


class RuleMismatch(BaseModel):
    """A concrete gap between what the rules require and the naive trader thesis."""

    clause: str = Field(..., description="The binding resolution clause, quoted/paraphrased.")
    trader_thesis: str = Field(..., description="What a headline-reading bot would assume.")
    conflict_reason: str = Field(..., description="Why the thesis fails to satisfy the clause.")


# --------------------------------------------------------------------------- #
# Response — explainability envelope
# --------------------------------------------------------------------------- #
class ScoreComponent(BaseModel):
    """One weighted contributor to the risk score, for auditability."""

    factor: str = Field(..., examples=["source_of_truth_mismatch"])
    weight: float = Field(..., description="Contribution to the 0-100 score.")
    detail: str = Field(default="", description="Human-readable note on why it fired.")


class MonitorInfo(BaseModel):
    subscribed: bool = False
    monitor_id: Optional[str] = None


class Citation(BaseModel):
    """Source snippet backing a mismatch or the score — proves the rules were read."""

    label: str = Field(..., examples=["Polymarket resolution criteria"])
    snippet: str
    url: Optional[str] = None


# --------------------------------------------------------------------------- #
# Response — top level
# --------------------------------------------------------------------------- #
class VerifyResponse(BaseModel):
    """The risk payload. User-frozen fields first, envelope after."""

    # --- user-frozen core ---
    market_id: str = Field(..., examples=["0x1234...5678"])
    resolution_risk_score: int = Field(..., ge=0, le=100, examples=[85])
    action: Action
    parsed_contract_data: ParsedContractData
    rule_mismatches_detected: list[RuleMismatch] = Field(default_factory=list)

    # --- request echo (self-describing audit rows) ---
    market_url: str
    platform: Platform
    queried_side: Optional[str] = None
    market_question: Optional[str] = Field(
        default=None, description="The market's question text, for display."
    )

    # --- explainability ---
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model/heuristic confidence.")
    score_breakdown: list[ScoreComponent] = Field(default_factory=list)
    summary: str = Field(..., description="One-line headline for portal + Telegram.")
    citations: list[Citation] = Field(default_factory=list)

    # --- monitoring hook ---
    monitor: MonitorInfo = Field(default_factory=MonitorInfo)

    # --- provenance ---
    request_id: str
    checked_at: datetime = Field(default_factory=_utcnow)
    schema_version: str = SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# Error envelope
# --------------------------------------------------------------------------- #
class ErrorCode(str, Enum):
    UNSUPPORTED_PLATFORM = "UNSUPPORTED_PLATFORM"
    MARKET_NOT_FOUND = "MARKET_NOT_FOUND"
    UNREACHABLE_SOURCE = "UNREACHABLE_SOURCE"
    AMBIGUOUS_URL = "AMBIGUOUS_URL"
    PARSE_FAILED = "PARSE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorResponse(BaseModel):
    error_code: ErrorCode
    message: str
    request_id: str
    checked_at: datetime = Field(default_factory=_utcnow)
    schema_version: str = SCHEMA_VERSION
