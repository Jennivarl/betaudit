"""Lock the frozen contract: the example payload must always validate, and the
user-frozen fields must never silently disappear.
"""

import json
from pathlib import Path

from app.schemas import SCHEMA_VERSION, Action, VerifyResponse

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "verify_response.trap_market.json"

# The exact fields the user froze — presence is contractual.
FROZEN_TOP_LEVEL = {
    "market_id",
    "resolution_risk_score",
    "action",
    "parsed_contract_data",
    "rule_mismatches_detected",
}
FROZEN_PARSED = {
    "oracle_type",
    "challenge_window_hours",
    "source_of_truth_specified",
    "current_oracle_state",
}
FROZEN_MISMATCH = {"clause", "trader_thesis", "conflict_reason"}


def test_example_payload_validates():
    data = json.loads(EXAMPLE.read_text())
    resp = VerifyResponse.model_validate(data)
    assert resp.action == Action.ABORT_TRADE
    assert 0 <= resp.resolution_risk_score <= 100
    assert resp.schema_version == SCHEMA_VERSION


def test_frozen_fields_present():
    fields = set(VerifyResponse.model_fields)
    assert FROZEN_TOP_LEVEL <= fields, f"missing frozen fields: {FROZEN_TOP_LEVEL - fields}"

    from app.schemas import ParsedContractData, RuleMismatch

    assert FROZEN_PARSED <= set(ParsedContractData.model_fields)
    assert FROZEN_MISMATCH <= set(RuleMismatch.model_fields)


def test_score_out_of_range_rejected():
    import pytest
    from pydantic import ValidationError

    data = json.loads(EXAMPLE.read_text())
    data["resolution_risk_score"] = 150
    with pytest.raises(ValidationError):
        VerifyResponse.model_validate(data)
