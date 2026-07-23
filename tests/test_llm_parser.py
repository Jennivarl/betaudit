"""OpenAI clause parser with an injected fake client (no network, no key)."""

from app.llm.parser import ClauseParser
from tests.conftest import FakeOpenAI

TRAP_PAYLOAD = {
    "source_of_truth": "Official SEC 8-K Filing",
    "risk_score": 88,
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
    assert analysis.risk_score == 88
    assert analysis.confidence == 0.92
    assert analysis.source_of_truth == "Official SEC 8-K Filing"
    assert len(analysis.mismatches) == 1
    assert "SEC" in analysis.mismatches[0].clause


async def test_parser_clamps_out_of_range(trap_market):
    payload = {**TRAP_PAYLOAD, "risk_score": 250, "confidence": 5}
    parser = ClauseParser(client=FakeOpenAI(payload))
    analysis = await parser.parse(trap_market, queried_side="YES")
    assert analysis.risk_score == 100
    assert analysis.confidence == 1.0


async def test_disabled_parser_returns_none(trap_market):
    parser = ClauseParser(api_key="")  # no key, no client
    assert not parser.enabled
    assert await parser.parse(trap_market, queried_side="YES") is None
