"""Oracle monitor: subscribe via /verify, detect a state change, receipt the alert.

Detection is driven synchronously through POST /monitors/{id}/check with the
resolver monkeypatched — no background loop, no network.
"""

import app.main as main
from app.llm.parser import ClauseParser
from app.resolvers.base import ResolvedMarket
from app.schemas import OracleState, Platform
from app.services import monitor as monitor_service
from tests.conftest import TRAP_URL


def _market(state: OracleState, url: str = TRAP_URL) -> ResolvedMarket:
    return ResolvedMarket(
        platform=Platform.POLYMARKET,
        market_id="0x1234...5678",
        market_url=url,
        question="Will Company X release Product Y by May 31?",
        outcomes=["Yes", "No"],
        resolution_criteria="Resolves YES only upon an Official SEC 8-K Filing.",
        source_of_truth_specified=None,
        oracle_type="UMA_OOv2",
        challenge_window_hours=2.0,
        current_oracle_state=state,
        raw_sources=[],
    )


def _subscribe(client, auth_headers, monkeypatch, trap_market) -> str:
    async def fake_resolve(url, queried_side=None):
        trap_market.market_url = url
        return trap_market

    monkeypatch.setattr(main, "resolve_market", fake_resolve)
    monkeypatch.setattr(main, "get_parser", lambda: ClauseParser(api_key=""))
    r = client.post(
        "/verify-resolution-rules",
        json={"market_url": TRAP_URL, "queried_side": "YES", "subscribe_monitor": True},
        headers=auth_headers,
    )
    assert r.status_code == 200
    monitor = r.json()["monitor"]
    assert monitor["subscribed"] is True
    return monitor["monitor_id"]


def _patch_state(monkeypatch, state: OracleState):
    async def fake_resolve(url, queried_side=None):
        return _market(state)

    monkeypatch.setattr(monitor_service, "resolve_market", fake_resolve)


def test_subscribe_creates_monitor(client, auth_headers, monkeypatch, trap_market):
    monitor_id = _subscribe(client, auth_headers, monkeypatch, trap_market)

    subs = client.get("/monitors", headers=auth_headers).json()
    assert len(subs) == 1
    assert subs[0]["monitor_id"] == monitor_id
    assert subs[0]["last_oracle_state"] == OracleState.UNDISPUTED.value  # from trap_market
    assert subs[0]["active"] is True


def test_check_detects_dispute_and_alerts(client, auth_headers, monkeypatch, trap_market):
    monitor_id = _subscribe(client, auth_headers, monkeypatch, trap_market)

    # Oracle flips UNDISPUTED -> DISPUTED.
    _patch_state(monkeypatch, OracleState.DISPUTED)
    events = client.post(f"/monitors/{monitor_id}/check", headers=auth_headers).json()
    assert len(events) == 1
    assert events[0]["old_state"] == OracleState.UNDISPUTED.value
    assert events[0]["new_state"] == OracleState.DISPUTED.value
    assert events[0]["severity"] == "high"

    # Alert is now in the trail, and the subscription's state advanced.
    alerts = client.get("/alerts", headers=auth_headers).json()
    assert len(alerts) == 1
    assert alerts[0]["new_state"] == OracleState.DISPUTED.value
    sub = client.get(f"/monitors/{monitor_id}", headers=auth_headers).json()
    assert sub["last_oracle_state"] == OracleState.DISPUTED.value


def test_check_is_idempotent_when_unchanged(client, auth_headers, monkeypatch, trap_market):
    monitor_id = _subscribe(client, auth_headers, monkeypatch, trap_market)

    _patch_state(monkeypatch, OracleState.DISPUTED)
    first = client.post(f"/monitors/{monitor_id}/check", headers=auth_headers).json()
    assert len(first) == 1
    # Same state again -> no new alert.
    second = client.post(f"/monitors/{monitor_id}/check", headers=auth_headers).json()
    assert second == []
    assert len(client.get("/alerts", headers=auth_headers).json()) == 1


def test_resolved_state_deactivates_subscription(client, auth_headers, monkeypatch, trap_market):
    monitor_id = _subscribe(client, auth_headers, monkeypatch, trap_market)

    _patch_state(monkeypatch, OracleState.RESOLVED)
    events = client.post(f"/monitors/{monitor_id}/check", headers=auth_headers).json()
    assert events[0]["severity"] == "high"
    sub = client.get(f"/monitors/{monitor_id}", headers=auth_headers).json()
    assert sub["active"] is False


def test_monitors_isolated_per_key(client, auth_headers, monkeypatch, trap_market):
    monitor_id = _subscribe(client, auth_headers, monkeypatch, trap_market)

    other = client.post("/admin/keys", json={"label": "other"}).json()["api_key"]
    other_headers = {"X-API-Key": other}

    assert client.get("/monitors", headers=other_headers).json() == []
    assert client.get(f"/monitors/{monitor_id}", headers=other_headers).status_code == 404
    assert client.post(f"/monitors/{monitor_id}/check", headers=other_headers).status_code == 404
