"""Market resolvers: turn a market URL into normalized resolution facts.

Polymarket is the real v1 adapter. Kalshi is a reserved Phase 2 adapter. The
router picks an adapter by URL so new platforms slot in without touching the
engine.
"""

from app.resolvers.base import (
    MarketResolver,
    ResolvedMarket,
    ResolverError,
    UnsupportedPlatformError,
)
from app.resolvers.router import resolve_market, resolver_for_url

__all__ = [
    "MarketResolver",
    "ResolvedMarket",
    "ResolverError",
    "UnsupportedPlatformError",
    "resolve_market",
    "resolver_for_url",
]
