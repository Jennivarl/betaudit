"""Resolver interface + the normalized fact object every adapter returns.

An adapter's only job is retrieval + normalization: fetch the market and hand
back the *real* resolution rules and oracle metadata. It does NOT score risk or
call the LLM — that is the engine's job. Keeping adapters dumb is what lets
Kalshi (Phase 2) drop in behind the same interface.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional

from app.schemas import OracleState, Platform


@dataclass
class ResolvedMarket:
    """Normalized, platform-agnostic view of a market's resolution facts."""

    platform: Platform
    market_id: str
    market_url: str
    question: str
    outcomes: list[str]

    # The fine print the score actually depends on.
    resolution_criteria: str = ""
    source_of_truth_specified: Optional[str] = None

    # Oracle metadata.
    oracle_type: str = "UNKNOWN"
    challenge_window_hours: Optional[float] = None
    current_oracle_state: OracleState = OracleState.UNKNOWN

    # Raw source snippets for citations / audit.
    raw_sources: list[dict] = field(default_factory=list)


class ResolverError(Exception):
    """Base class for resolver failures."""


class UnsupportedPlatformError(ResolverError):
    """No adapter matches the given URL."""


class MarketResolver(abc.ABC):
    """Contract every platform adapter implements."""

    platform: Platform

    @abc.abstractmethod
    def matches(self, url: str) -> bool:
        """Return True if this adapter handles the given market URL."""

    @abc.abstractmethod
    async def resolve(self, url: str, queried_side: Optional[str] = None) -> ResolvedMarket:
        """Fetch and normalize the market's resolution facts."""
