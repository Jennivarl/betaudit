"""Risk engine: ResolvedMarket (+ optional LLM analysis) -> VerifyResponse.

The score is always explainable: every point traces to a named component in
``score_breakdown``. Two modes:

  * LLM available  -> the model's grounded reading of the real resolution text
    drives the content risk (and supplies the mismatches); structural oracle
    metadata is added as separate auditable components.
  * LLM absent     -> a deterministic rubric over the oracle metadata alone,
    so the service still returns a defensible number without a key.
"""

from __future__ import annotations

import uuid
from typing import Optional

from app.llm.parser import ClauseAnalysis
from app.resolvers.base import ResolvedMarket
from app.schemas import (
    Action,
    Citation,
    MonitorInfo,
    OracleState,
    ParsedContractData,
    RuleMismatch,
    ScoreComponent,
    VerifyResponse,
)

# Score thresholds for the three-way action.
_ABORT_AT = 70
_CAUTION_AT = 35


def _action_for(score: int) -> Action:
    if score >= _ABORT_AT:
        return Action.ABORT_TRADE
    if score >= _CAUTION_AT:
        return Action.CAUTION
    return Action.PROCEED


def _structural_components(market: ResolvedMarket) -> list[ScoreComponent]:
    """Auditable signals from oracle metadata, independent of the LLM."""
    components: list[ScoreComponent] = []
    if market.challenge_window_hours is not None and market.challenge_window_hours <= 4:
        components.append(
            ScoreComponent(
                factor="tight_challenge_window",
                weight=15,
                detail=f"Challenge window is only {market.challenge_window_hours}h.",
            )
        )
    if market.current_oracle_state in (OracleState.PROPOSED, OracleState.UNDISPUTED):
        components.append(
            ScoreComponent(
                factor="oracle_state_advanced",
                weight=15,
                detail=f"Oracle state is {market.current_oracle_state.value}.",
            )
        )
    return components


def score_market(
    market: ResolvedMarket,
    *,
    analysis: Optional[ClauseAnalysis] = None,
    queried_side: str | None = None,
    subscribe_monitor: bool = False,
) -> VerifyResponse:
    """Turn normalized market facts (+ optional LLM analysis) into the risk payload."""

    if analysis is not None:
        components, mismatches, source_of_truth, confidence = _score_with_llm(market, analysis)
    else:
        components, mismatches, source_of_truth, confidence = _score_deterministic(market)

    score = min(100, sum(c.weight for c in components))
    action = _action_for(score)

    if mismatches:
        summary = (
            f"{action.value}: resolution hinges on "
            f"'{source_of_truth or 'a strict clause'}', not the headline."
        )
    else:
        summary = f"{action.value}: no blocking resolution mismatches detected."

    citations = [
        Citation(label=s.get("label", "source"), snippet=s.get("snippet", ""), url=s.get("url"))
        for s in market.raw_sources
    ]

    monitor = MonitorInfo(
        subscribed=subscribe_monitor,
        monitor_id=(f"mon_{uuid.uuid4().hex[:12]}" if subscribe_monitor else None),
    )

    return VerifyResponse(
        market_id=market.market_id,
        resolution_risk_score=score,
        action=action,
        parsed_contract_data=ParsedContractData(
            oracle_type=market.oracle_type,
            challenge_window_hours=market.challenge_window_hours,
            source_of_truth_specified=source_of_truth,
            current_oracle_state=market.current_oracle_state,
        ),
        rule_mismatches_detected=mismatches,
        market_url=market.market_url,
        platform=market.platform,
        queried_side=queried_side,
        confidence=confidence,
        score_breakdown=components,
        summary=summary,
        citations=citations,
        monitor=monitor,
        request_id=f"req_{uuid.uuid4().hex[:16]}",
    )


def _score_with_llm(
    market: ResolvedMarket, analysis: ClauseAnalysis
) -> tuple[list[ScoreComponent], list[RuleMismatch], Optional[str], float]:
    """LLM's grounded reading drives content risk; structural metadata adds to it."""
    source_of_truth = analysis.source_of_truth or market.source_of_truth_specified

    components: list[ScoreComponent] = [
        ScoreComponent(
            factor="llm_resolution_analysis",
            # LLM judgment dominates but is capped so structural signals still matter.
            weight=round(analysis.risk_score * 0.7),
            detail=analysis.reasoning or "Grounded reading of the resolution rules.",
        )
    ]
    components.extend(_structural_components(market))
    return components, analysis.mismatches, source_of_truth, analysis.confidence


def _score_deterministic(
    market: ResolvedMarket,
) -> tuple[list[ScoreComponent], list[RuleMismatch], Optional[str], float]:
    """No-LLM fallback: rubric over oracle metadata only."""
    components: list[ScoreComponent] = []
    mismatches: list[RuleMismatch] = []
    source_of_truth = market.source_of_truth_specified

    if source_of_truth:
        components.append(
            ScoreComponent(
                factor="source_of_truth_mismatch",
                weight=55,
                detail=(
                    f"Resolution requires '{source_of_truth}'; "
                    "press/media reports do not satisfy it."
                ),
            )
        )
        mismatches.append(
            RuleMismatch(
                clause=market.resolution_criteria or f"Requires {source_of_truth}.",
                trader_thesis="News/media reporting the event occurred.",
                conflict_reason=(
                    f"Reports do not satisfy the required '{source_of_truth}'. "
                    "Payout may resolve against a headline-based YES."
                ),
            )
        )

    components.extend(_structural_components(market))
    confidence = 0.6 if market.resolution_criteria else 0.4  # lower — no LLM reading
    return components, mismatches, source_of_truth, confidence
