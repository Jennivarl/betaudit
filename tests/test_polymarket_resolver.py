"""Resolver normalization + URL parsing, no network."""

import pytest

from app.resolvers.polymarket import PolymarketResolver
from app.schemas import OracleState, Platform

r = PolymarketResolver()


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://polymarket.com/event/company-x-releases-product-y", "company-x-releases-product-y"),
        ("https://polymarket.com/market/some-market-slug", "some-market-slug"),
        ("https://polymarket.com/some-slug", "some-slug"),
        # /event/<event>/<market> -> the specific market (last segment), not the event
        (
            "https://polymarket.com/event/presidential-election-winner-2028/will-lebron-james-win",
            "will-lebron-james-win",
        ),
        ("https://polymarket.com/market/some-market-slug/", "some-market-slug"),  # trailing slash
    ],
)
def test_slug_from_url(url, expected):
    assert PolymarketResolver._slug_from_url(url) == expected


def test_matches():
    assert r.matches("https://polymarket.com/event/x")
    assert not r.matches("https://example.com/event/x")


def test_challenge_window_default_when_zero():
    # customLiveness 0 on a UMA market => default 2h.
    assert r._challenge_window_hours({"customLiveness": 0, "umaBond": 500}) == 2.0
    assert r._challenge_window_hours({"customLiveness": 3600, "umaBond": 500}) == 1.0
    assert r._challenge_window_hours({"customLiveness": 0}) is None  # not UMA -> unknown


def test_oracle_state_mapping():
    assert r._oracle_state({"closed": True}) == OracleState.RESOLVED
    assert r._oracle_state({"umaResolutionStatuses": ["disputed"]}) == OracleState.DISPUTED
    assert r._oracle_state({"umaResolutionStatuses": ["proposed"]}) == OracleState.PROPOSED
    assert r._oracle_state({"active": True}) == OracleState.UNRESOLVED


def test_normalize_reads_description_and_uma():
    market = {
        "conditionId": "0xabc",
        "question": "Will X ship by May 31?",
        "description": "Resolves YES only upon an Official SEC 8-K Filing.",
        "outcomes": '["Yes", "No"]',
        "resolvedBy": "0xUMAAdapter",
        "umaBond": 500,
        "customLiveness": 0,
        "active": True,
    }
    rm = r._normalize(market, "https://polymarket.com/event/x")
    assert rm.platform == Platform.POLYMARKET
    assert rm.market_id == "0xabc"
    assert rm.oracle_type == "UMA_OOv2"
    assert rm.challenge_window_hours == 2.0
    assert rm.outcomes == ["Yes", "No"]
    assert "SEC 8-K" in rm.resolution_criteria
