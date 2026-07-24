"""Opt-in integration test against the real OpenAI API.

Skipped by default. Needs a funded key. Run with:
    RUN_LIVE_LLM=1 pytest tests/test_live_llm.py

Uses the deliberately trapped market from conftest (resolution requires an
Official SEC 8-K filing; media reports do not qualify) and asserts the model
grounds on that trap rather than the headline.
"""

import os

import pytest

from app.llm.parser import ClauseParser

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM") != "1",
    reason="set RUN_LIVE_LLM=1 (and OPENAI_API_KEY) to hit the live OpenAI API",
)


async def test_llm_flags_the_sec_trap(trap_market):
    parser = ClauseParser()  # reads OPENAI_API_KEY + LLM_MODEL from settings
    assert parser.enabled, "OPENAI_API_KEY must be set for the live LLM test"

    analysis = await parser.parse(trap_market, queried_side="YES")
    assert analysis is not None
    # The trap is unambiguous — a grounded reading should classify at least one
    # real risk factor and surface at least one concrete mismatch.
    assert analysis.risk_factors, f"expected risk factors, got {analysis.risk_factors}"
    assert analysis.mismatches, "expected at least one rule mismatch"
    print(f"\nlive LLM -> factors={analysis.risk_factors} conf={analysis.confidence} "
          f"source={analysis.source_of_truth!r} reasoning={analysis.reasoning!r}")
