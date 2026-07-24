"""Engine scoring in both modes: LLM-fused and deterministic fallback."""

from app.engine import score_market
from app.llm.parser import ClauseAnalysis
from app.schemas import Action, RuleMismatch


def test_llm_mode_drives_abort(trap_market):
    analysis = ClauseAnalysis(
        source_of_truth="Official SEC 8-K Filing",
        risk_score=88,
        confidence=0.92,
        reasoning="Rules require an SEC 8-K filing.",
        mismatches=[
            RuleMismatch(
                clause="Requires SEC 8-K by May 31.",
                trader_thesis="Media reported the release.",
                conflict_reason="Reports do not satisfy the SEC filing requirement.",
            )
        ],
    )
    resp = score_market(trap_market, analysis=analysis, queried_side="YES")
    assert resp.action == Action.ABORT_TRADE
    assert resp.resolution_risk_score >= 70
    assert resp.confidence == 0.92
    assert resp.parsed_contract_data.source_of_truth_specified == "Official SEC 8-K Filing"
    assert resp.rule_mismatches_detected
    # Score must remain explainable and deterministic from the findings.
    factors = {c.factor for c in resp.score_breakdown}
    assert "resolution_trap" in factors


def test_deterministic_fallback_uses_metadata(trap_market):
    # No LLM analysis; but metadata names a source of truth => mismatch + risk.
    trap_market.source_of_truth_specified = "Official SEC 8-K Filing"
    resp = score_market(trap_market, analysis=None, queried_side="YES")
    assert resp.action == Action.ABORT_TRADE
    assert resp.rule_mismatches_detected
    assert any(c.factor == "source_of_truth_mismatch" for c in resp.score_breakdown)


def test_clean_market_proceeds(trap_market):
    # No source of truth, relaxed window, unresolved oracle => low risk.
    trap_market.source_of_truth_specified = None
    trap_market.resolution_criteria = "Resolves YES if the event happens. Any credible source."
    trap_market.challenge_window_hours = 48.0
    from app.schemas import OracleState

    trap_market.current_oracle_state = OracleState.UNRESOLVED
    resp = score_market(trap_market, analysis=None, queried_side="YES")
    assert resp.action == Action.PROCEED
    assert resp.resolution_risk_score < 35
