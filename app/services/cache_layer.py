"""Cache-aside layer over the two expensive steps of a verify call.

  * market data — the resolved market (contract + UMA metadata) keyed by URL,
    TTL ~1h. Skips the Polymarket Gamma round-trip on a hit.
  * LLM evaluation — the parser's grounded analysis keyed by a hash of the model
    + resolution text + queried side, TTL ~15m. Skips the LLM call on a hit.

Both take the resolver / parser injected so the endpoint can pass its own
(patchable) references and the monitor can bypass caching entirely (it needs
fresh oracle state). When Redis is off, these are transparent pass-throughs.
"""

from __future__ import annotations

import hashlib
from typing import Awaitable, Callable, Optional

from app import redis_client
from app.config import get_settings
from app.llm.parser import ClauseAnalysis, ClauseParser
from app.resolvers.base import ResolvedMarket
from app.schemas import OracleState, Platform, RuleMismatch

Resolver = Callable[[str, Optional[str]], Awaitable[ResolvedMarket]]


# --------------------------------------------------------------------------- #
# Market cache
# --------------------------------------------------------------------------- #
def _market_key(url: str) -> str:
    return "cache:market:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def _market_to_dict(m: ResolvedMarket) -> dict:
    return {
        "platform": m.platform.value,
        "market_id": m.market_id,
        "market_url": m.market_url,
        "question": m.question,
        "outcomes": m.outcomes,
        "resolution_criteria": m.resolution_criteria,
        "source_of_truth_specified": m.source_of_truth_specified,
        "oracle_type": m.oracle_type,
        "challenge_window_hours": m.challenge_window_hours,
        "current_oracle_state": m.current_oracle_state.value,
        "raw_sources": m.raw_sources,
    }


def _market_from_dict(d: dict) -> ResolvedMarket:
    return ResolvedMarket(
        platform=Platform(d["platform"]),
        market_id=d["market_id"],
        market_url=d["market_url"],
        question=d["question"],
        outcomes=list(d.get("outcomes") or []),
        resolution_criteria=d.get("resolution_criteria"),
        source_of_truth_specified=d.get("source_of_truth_specified"),
        oracle_type=d.get("oracle_type", "UNKNOWN"),
        challenge_window_hours=d.get("challenge_window_hours"),
        current_oracle_state=OracleState(d.get("current_oracle_state", "UNKNOWN")),
        raw_sources=list(d.get("raw_sources") or []),
    )


async def resolve_cached(
    url: str, queried_side: Optional[str], *, resolver: Resolver
) -> ResolvedMarket:
    key = _market_key(url)
    cached = await redis_client.cache_get_json(key)
    if cached is not None:
        return _market_from_dict(cached)
    market = await resolver(url, queried_side)  # raises propagate (not cached)
    await redis_client.cache_set_json(
        key, _market_to_dict(market), get_settings().cache_market_ttl_seconds
    )
    return market


# --------------------------------------------------------------------------- #
# LLM evaluation cache
# --------------------------------------------------------------------------- #
def _eval_key(model: str, market: ResolvedMarket, queried_side: Optional[str]) -> str:
    seed = "|".join(
        [
            model,
            queried_side or "YES",
            market.question or "",
            market.resolution_criteria or "",
            market.source_of_truth_specified or "",
        ]
    )
    return "cache:eval:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:40]


def _analysis_to_dict(a: ClauseAnalysis) -> dict:
    return {
        "source_of_truth": a.source_of_truth,
        "risk_score": a.risk_score,
        "confidence": a.confidence,
        "reasoning": a.reasoning,
        "mismatches": [
            {"clause": m.clause, "trader_thesis": m.trader_thesis, "conflict_reason": m.conflict_reason}
            for m in a.mismatches
        ],
    }


def _analysis_from_dict(d: dict) -> ClauseAnalysis:
    return ClauseAnalysis(
        source_of_truth=d.get("source_of_truth"),
        risk_score=int(d.get("risk_score", 0)),
        confidence=float(d.get("confidence", 0.5)),
        reasoning=d.get("reasoning", ""),
        mismatches=[
            RuleMismatch(
                clause=m.get("clause", ""),
                trader_thesis=m.get("trader_thesis", ""),
                conflict_reason=m.get("conflict_reason", ""),
            )
            for m in (d.get("mismatches") or [])
        ],
    )


async def analyze_cached(
    parser: ClauseParser, market: ResolvedMarket, queried_side: Optional[str]
) -> Optional[ClauseAnalysis]:
    if not parser.enabled:
        return None
    key = _eval_key(parser.model, market, queried_side)
    cached = await redis_client.cache_get_json(key)
    if cached is not None:
        return _analysis_from_dict(cached)
    analysis = await parser.parse(market, queried_side=queried_side)  # raises propagate
    if analysis is not None:
        await redis_client.cache_set_json(
            key, _analysis_to_dict(analysis), get_settings().cache_eval_ttl_seconds
        )
    return analysis
