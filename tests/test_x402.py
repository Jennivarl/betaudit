"""x402 pay-per-call gate — challenge, paid success, receipt, and free passthrough.

Runs in simulate mode: the facilitator verifies/settles locally, so the full
402 -> pay -> 200 handshake is exercised with no chain or network.
"""

import app.main as main
from app.config import get_settings
from app.llm.parser import ClauseParser
from app.payments.x402 import decode_header, encode_header
from tests.conftest import TRAP_URL

PAY_TO = "0x5150fa46b6778b7fc7797524c1b5bef6f8cb5f5e"


def _enable_x402(monkeypatch, mode="simulate", price="0.05"):
    monkeypatch.setenv("X402_ENABLED", "true")
    monkeypatch.setenv("X402_MODE", mode)
    monkeypatch.setenv("X402_PRICE_USDT", price)
    monkeypatch.setenv("X402_PAY_TO", PAY_TO)
    get_settings.cache_clear()


def _patch_engine(monkeypatch, market):
    async def fake_resolve(url, queried_side=None):
        market.market_url = url
        return market

    monkeypatch.setattr(main, "resolve_market", fake_resolve)
    monkeypatch.setattr(main, "get_parser", lambda: ClauseParser(api_key=""))


def _signature_header() -> dict:
    payload = {
        "x402Version": 2,
        "scheme": "exact",
        "network": "eip155:196",
        "payload": {"from": PAY_TO, "authorization": {"value": "50000"}},
    }
    return {"PAYMENT-SIGNATURE": encode_header(payload)}


def test_free_when_disabled(client, auth_headers, monkeypatch, trap_market):
    # x402 defaults off -> endpoint stays free, no payment header needed.
    _patch_engine(monkeypatch, trap_market)
    r = client.post(
        "/verify-resolution-rules", json={"market_url": TRAP_URL}, headers=auth_headers
    )
    assert r.status_code == 200
    assert "PAYMENT-RESPONSE" not in r.headers


def test_challenge_without_signature(client, auth_headers, monkeypatch, trap_market):
    _enable_x402(monkeypatch)
    _patch_engine(monkeypatch, trap_market)
    r = client.post(
        "/verify-resolution-rules", json={"market_url": TRAP_URL}, headers=auth_headers
    )
    assert r.status_code == 402
    assert "PAYMENT-REQUIRED" in r.headers
    doc = decode_header(r.headers["PAYMENT-REQUIRED"])
    assert doc["x402Version"] == 2
    req = doc["accepts"][0]
    assert req["scheme"] == "exact"
    assert req["network"] == "eip155:196"
    assert req["payTo"] == PAY_TO
    assert req["amount"] == "50000"  # 0.05 USDT * 1e6


def test_api_key_gate_precedes_payment(client, monkeypatch, trap_market):
    # No API key -> 401 before any 402 payment challenge.
    _enable_x402(monkeypatch)
    _patch_engine(monkeypatch, trap_market)
    r = client.post("/verify-resolution-rules", json={"market_url": TRAP_URL})
    assert r.status_code == 401


def test_paid_call_succeeds_and_receipts(client, auth_headers, monkeypatch, trap_market):
    _enable_x402(monkeypatch)
    _patch_engine(monkeypatch, trap_market)
    headers = {**auth_headers, **_signature_header()}
    r = client.post("/verify-resolution-rules", json={"market_url": TRAP_URL}, headers=headers)
    assert r.status_code == 200, r.text
    assert "PAYMENT-RESPONSE" in r.headers
    receipt = decode_header(r.headers["PAYMENT-RESPONSE"])
    assert receipt["success"] is True
    assert receipt["simulated"] is True
    assert receipt["payer"] == PAY_TO
    assert receipt["transaction"].startswith("0xsim")

    request_id = r.json()["request_id"]
    receipts = client.get("/payments/receipts", headers=auth_headers).json()
    assert len(receipts) == 1
    row = receipts[0]
    assert row["request_id"] == request_id
    assert row["status"] == "settled"
    assert row["mode"] == "simulate"
    assert row["amount_atomic"] == "50000"
    assert row["tx_hash"].startswith("0xsim")


def test_malformed_signature_is_challenged(client, auth_headers, monkeypatch, trap_market):
    _enable_x402(monkeypatch)
    _patch_engine(monkeypatch, trap_market)
    headers = {**auth_headers, "PAYMENT-SIGNATURE": "not-valid-base64!!"}
    r = client.post("/verify-resolution-rules", json={"market_url": TRAP_URL}, headers=headers)
    assert r.status_code == 402
    assert "PAYMENT-REQUIRED" in r.headers
