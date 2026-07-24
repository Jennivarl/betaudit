"""OpenAI clause parser with an injected fake client (no network, no key)."""

from app.llm.parser import ClauseParser
from tests.conftest import FakeOpenAI

TRAP_PAYLOAD = {
    "source_of_truth": "Official SEC 8-K Filing",
    "risk_factors": ["requires_official_source", "strict_deadline"],
    "confidence": 0.92,
    "reasoning": "Rules require an SEC 8-K filing; a media headline does not satisfy YES.",
    "mismatches": [
        {
            "clause": "Requires SEC 8-K filing confirmation by May 31st.",
            "trader_thesis": "News media reporting the release on May 29th.",
            "conflict_reason": "Press reports do not satisfy the on-chain SEC filing requirement.",
        }
    ],
}


async def test_parser_extracts_structured_analysis(trap_market):
    parser = ClauseParser(client=FakeOpenAI(TRAP_PAYLOAD))
    assert parser.enabled
    analysis = await parser.parse(trap_market, queried_side="YES")
    assert analysis is not None
    assert analysis.risk_factors == ["requires_official_source", "strict_deadline"]
    assert analysis.confidence == 0.92
    assert analysis.source_of_truth == "Official SEC 8-K Filing"
    assert len(analysis.mismatches) == 1
    assert "SEC" in analysis.mismatches[0].clause


async def test_parser_filters_bad_factors_and_clamps_confidence(trap_market):
    # Unknown factor codes are dropped; confidence is clamped to [0, 1].
    payload = {
        **TRAP_PAYLOAD,
        "risk_factors": ["requires_official_source", "totally_made_up_factor"],
        "confidence": 5,
    }
    parser = ClauseParser(client=FakeOpenAI(payload))
    analysis = await parser.parse(trap_market, queried_side="YES")
    assert analysis.risk_factors == ["requires_official_source"]  # bogus code filtered
    assert analysis.confidence == 1.0


async def test_disabled_parser_returns_none(trap_market):
    parser = ClauseParser(api_key="")  # no key, no client
    assert not parser.enabled
    assert await parser.parse(trap_market, queried_side="YES") is None
