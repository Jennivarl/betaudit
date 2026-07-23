"""Opt-in integration test against the real Polymarket Gamma API.

Skipped by default. Run with:  RUN_LIVE=1 pytest tests/test_live_gamma.py
"""

import os

import pytest

from app.resolvers.polymarket import PolymarketResolver

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to hit the live Gamma API"
)

LIVE_MARKET_URL = "https://polymarket.com/market/new-rhianna-album-before-gta-vi-926"


async def test_resolves_a_real_market():
    rm = await PolymarketResolver().resolve(LIVE_MARKET_URL)
    assert rm.market_id
    assert rm.question
    assert rm.outcomes
    assert rm.oracle_type == "UMA_OOv2"
    assert rm.challenge_window_hours is not None
    assert rm.resolution_criteria  # description carries the rules
