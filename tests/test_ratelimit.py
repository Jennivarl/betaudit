"""Per-API-key rate limiting on /verify (Redis-backed, fail-open)."""

import app.main as main
from app.config import get_settings
from app.llm.parser import ClauseParser
from tests.conftest import TRAP_URL


def _patch_engine(monkeypatch, market):
    async def fake_resolve(url, queried_side=None):
        market.market_url = url
        return market

    monkeypatch.setattr(main, "resolve_market", fake_resolve)
    monkeypatch.setattr(main, "get_parser", lambda: ClauseParser(api_key=""))


def test_rate_limit_returns_429_over_cap(client, auth_headers, monkeypatch, trap_market, fake_redis):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    _patch_engine(monkeypatch, trap_market)

    body = {"market_url": TRAP_URL}
    assert client.post("/verify-resolution-rules", json=body, headers=auth_headers).status_code == 200
    assert client.post("/verify-resolution-rules", json=body, headers=auth_headers).status_code == 200
    third = client.post("/verify-resolution-rules", json=body, headers=auth_headers)
    assert third.status_code == 429
    assert third.headers.get("Retry-After") == "60"


def test_no_rate_limit_without_redis(client, auth_headers, monkeypatch, trap_market):
    # Redis off -> fail-open -> no throttling even past the cap.
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    _patch_engine(monkeypatch, trap_market)

    body = {"market_url": TRAP_URL}
    for _ in range(3):
        assert client.post("/verify-resolution-rules", json=body, headers=auth_headers).status_code == 200
