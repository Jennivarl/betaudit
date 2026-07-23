"""API-key issuance, metering, and the audit trail — real DB, real auth."""

import app.main as main
from app.config import get_settings
from app.llm.parser import ClauseParser
from tests.conftest import TRAP_URL


def _patch_resolver(monkeypatch, market):
    async def fake_resolve(url, queried_side=None):
        market.market_url = url
        return market

    monkeypatch.setattr(main, "resolve_market", fake_resolve)
    monkeypatch.setattr(main, "get_parser", lambda: ClauseParser(api_key=""))


def test_demo_key_is_public_and_usable(client, monkeypatch, trap_market):
    # The web console mints via /demo/key without admin auth.
    r = client.post("/demo/key")
    assert r.status_code == 200
    key = r.json()["api_key"]
    assert key.startswith("rl_live_")

    _patch_resolver(monkeypatch, trap_market)
    v = client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL},
        headers={"X-API-Key": key},
    )
    assert v.status_code == 200


def test_demo_key_throttled_per_ip(client, fake_redis, monkeypatch):
    monkeypatch.setenv("DEMO_KEY_PER_MINUTE", "2")
    get_settings.cache_clear()
    assert client.post("/demo/key").status_code == 200
    assert client.post("/demo/key").status_code == 200
    assert client.post("/demo/key").status_code == 429


def test_admin_mints_key_with_prefix(client):
    r = client.post("/admin/keys", json={"label": "portal"})
    assert r.status_code == 200
    body = r.json()
    assert body["api_key"].startswith("rl_live_")
    assert body["prefix"].startswith("rl_live_")
    # The plaintext secret must never equal the stored, non-secret prefix.
    assert body["api_key"] != body["prefix"]
    assert body["label"] == "portal"
    assert body["call_count"] == 0


def test_keys_me_reflects_metering(client, auth_headers, monkeypatch, trap_market):
    _patch_resolver(monkeypatch, trap_market)

    before = client.get("/keys/me", headers=auth_headers).json()
    assert before["call_count"] == 0

    r = client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL, "queried_side": "YES"},
        headers=auth_headers,
    )
    assert r.status_code == 200

    after = client.get("/keys/me", headers=auth_headers).json()
    assert after["call_count"] == 1
    assert after["last_used_at"] is not None


def test_audit_log_records_the_call(client, auth_headers, monkeypatch, trap_market):
    _patch_resolver(monkeypatch, trap_market)

    resp = client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL, "queried_side": "YES"},
        headers=auth_headers,
    )
    request_id = resp.json()["request_id"]

    logs = client.get("/audit/logs", headers=auth_headers).json()
    assert len(logs) == 1
    row = logs[0]
    assert row["request_id"] == request_id
    assert row["status"] == "ok"
    assert row["market_url"] == TRAP_URL
    assert row["action"] in {"PROCEED", "CAUTION", "ABORT_TRADE"}
    assert row["latency_ms"] is not None


def test_audit_isolated_per_key(client, monkeypatch, trap_market):
    _patch_resolver(monkeypatch, trap_market)
    key_a = client.post("/admin/keys", json={"label": "a"}).json()["api_key"]
    key_b = client.post("/admin/keys", json={"label": "b"}).json()["api_key"]

    client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL},
        headers={"X-API-Key": key_a},
    )

    logs_b = client.get("/audit/logs", headers={"X-API-Key": key_b}).json()
    assert logs_b == []
    logs_a = client.get("/audit/logs", headers={"X-API-Key": key_a}).json()
    assert len(logs_a) == 1
