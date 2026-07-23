"""Adapter registry: pick a resolver by URL, fail loudly when none matches."""

from __future__ import annotations

from typing import Optional

from app.resolvers.base import MarketResolver, ResolvedMarket, UnsupportedPlatformError
from app.resolvers.polymarket import PolymarketResolver

# Order matters only if URL patterns overlap; they do not today.
_RESOLVERS: list[MarketResolver] = [
    PolymarketResolver(),
    # Phase 2: KalshiResolver(),
]


def resolver_for_url(url: str) -> MarketResolver:
    for resolver in _RESOLVERS:
        if resolver.matches(url):
            return resolver
    raise UnsupportedPlatformError(f"No resolver handles URL: {url}")


async def resolve_market(url: str, queried_side: Optional[str] = None) -> ResolvedMarket:
    return await resolver_for_url(url).resolve(url, queried_side=queried_side)
