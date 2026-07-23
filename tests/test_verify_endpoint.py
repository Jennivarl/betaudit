"""Endpoint path with the resolver + parser patched (no network, no LLM key).

The DB, API-key auth, and audit logging are real (temp SQLite via conftest).
"""

from types import SimpleNamespace

import app.main as main
from app.llm.parser import ClauseParser
from app.resolvers import UnsupportedPlatformError
from app.schemas import Action
from tests.conftest import TRAP_URL, FakeOpenAI

TRAP_PAYLOAD = {
    "source_of_truth": "Official SEC 8-K Filing",
    "risk_score": 88,
    "confidence": 0.92,
    "reasoning": "Rules require an SEC 8-K filing.",
    "mismatches": [
        {
            "clause": "Requires SEC 8-K by May 31.",
            "trader_thesis": "Media reported the release.",
            "conflict_reason": "Reports do not satisfy the SEC filing requirement.",
        }
    ],
}


def _patch(monkeypatch, market, *, parser=None, resolver_exc=None):
    async def fake_resolve(url, queried_side=None):
        if resolver_exc:
            raise resolver_exc
        market.market_url = url
        return market

    monkeypatch.setattr(main, "resolve_market", fake_resolve)
    monkeypatch.setattr(main, "get_parser", lambda: parser or ClauseParser(api_key=""))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_live_audit_ws_offline_without_redis(client):
    # No Redis configured in tests -> the feed announces itself as offline.
    with client.websocket_connect("/ws/audits") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "info"
        assert "offline" in msg["message"]


def test_verify_requires_api_key(client):
    r = client.post("/verify-resolution-rules", json={"market_url": TRAP_URL})
    assert r.status_code == 401


def test_verify_rejects_bad_api_key(client):
    r = client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL},
        headers={"X-API-Key": "rl_live_deadbeef"},
    )
    assert r.status_code == 401


def test_trap_market_aborts_with_llm(client, auth_headers, monkeypatch, trap_market):
    parser = ClauseParser(client=FakeOpenAI(TRAP_PAYLOAD))
    _patch(monkeypatch, trap_market, parser=parser)
    r = client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL, "queried_side": "YES"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == Action.ABORT_TRADE.value
    assert body["resolution_risk_score"] >= 70
    assert body["parsed_contract_data"]["source_of_truth_specified"] == "Official SEC 8-K Filing"
    assert body["rule_mismatches_detected"]
    assert body["score_breakdown"]
    assert body["request_id"].startswith("req_")


def test_monitor_subscription_returns_id(client, auth_headers, monkeypatch, trap_market):
    _patch(monkeypatch, trap_market)  # deterministic parser is fine here
    r = client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL, "subscribe_monitor": True},
        headers=auth_headers,
    )
    assert r.status_code == 200
    monitor = r.json()["monitor"]
    assert monitor["subscribed"] is True
    assert monitor["monitor_id"]


def test_llm_failure_degrades_to_deterministic(client, auth_headers, monkeypatch, trap_market):
    # An enabled parser whose provider call raises must not 500 the endpoint;
    # it falls back to the deterministic rubric over the oracle metadata.
    async def boom(**_kwargs):
        raise RuntimeError("openai down")

    raising_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=boom))
    )
    parser = ClauseParser(client=raising_client)
    trap_market.source_of_truth_specified = "Official SEC 8-K Filing"  # deterministic flags it
    _patch(monkeypatch, trap_market, parser=parser)

    r = client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL, "queried_side": "YES"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["action"] == Action.ABORT_TRADE.value


def test_unsupported_platform_returns_error_envelope(
    client, auth_headers, monkeypatch, trap_market
):
    _patch(monkeypatch, trap_market, resolver_exc=UnsupportedPlatformError("no resolver"))
    r = client.post(
        "/verify-resolution-rules",
        json={"market_url": "https://example.com/x"},
        headers=auth_headers,
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error_code"] == "UNSUPPORTED_PLATFORM"
    assert body["request_id"].startswith("req_")
