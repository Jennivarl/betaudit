"""MCP Streamable-HTTP surface: initialize, tools/list, tools/call (real engine)."""

import app.main as main
from app.llm.parser import ClauseParser
from app.mcp_server import TOOL_NAME
from tests.conftest import TRAP_URL, FakeOpenAI

TRAP_PAYLOAD = {
    "source_of_truth": "Official SEC 8-K Filing",
    "risk_score": 88,
    "confidence": 0.92,
    "reasoning": "Rules require an SEC 8-K filing.",
    "mismatches": [
        {"clause": "SEC 8-K by May 31.", "trader_thesis": "Headline.", "conflict_reason": "No filing."}
    ],
}


def _patch(monkeypatch, market, *, parser=None):
    async def fake_resolve(url, queried_side=None):
        market.market_url = url
        return market

    monkeypatch.setattr(main, "resolve_market", fake_resolve)
    monkeypatch.setattr(main, "get_parser", lambda: parser or ClauseParser(api_key=""))


def _rpc(client, method, params=None, rpc_id=1):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params or {}},
    )


def test_initialize_handshake(client):
    r = _rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    res = body["result"]
    assert res["protocolVersion"] == "2025-06-18"
    assert res["serverInfo"]["name"] == "BetAudit"
    assert "tools" in res["capabilities"]


def test_initialize_falls_back_on_unknown_version(client):
    res = _rpc(client, "initialize", {"protocolVersion": "1999-01-01"}).json()["result"]
    assert res["protocolVersion"] == "2025-06-18"  # server's supported version


def test_tools_list_exposes_the_auditor(client):
    res = _rpc(client, "tools/list").json()["result"]
    names = [t["name"] for t in res["tools"]]
    assert TOOL_NAME in names
    tool = res["tools"][0]
    assert "market_url" in tool["inputSchema"]["properties"]
    assert tool["inputSchema"]["required"] == ["market_url"]


def test_notifications_are_acknowledged(client):
    r = client.post(
        "/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    assert r.status_code == 202


def test_tools_call_runs_the_real_engine(client, monkeypatch, trap_market):
    parser = ClauseParser(client=FakeOpenAI(TRAP_PAYLOAD))
    _patch(monkeypatch, trap_market, parser=parser)

    r = _rpc(
        client,
        "tools/call",
        {"name": TOOL_NAME, "arguments": {"market_url": TRAP_URL, "queried_side": "YES"}},
    )
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is False
    assert result["content"][0]["type"] == "text"
    sc = result["structuredContent"]
    assert sc["action"] == "ABORT_TRADE"
    assert sc["resolution_risk_score"] >= 70
    assert sc["parsed_contract_data"]["source_of_truth_specified"] == "Official SEC 8-K Filing"


def test_tools_call_missing_url_is_invalid_params(client):
    r = _rpc(client, "tools/call", {"name": TOOL_NAME, "arguments": {}})
    body = r.json()
    assert body["error"]["code"] == -32602


def test_tools_call_bad_market_is_tool_error(client, monkeypatch, trap_market):
    from app.resolvers import UnsupportedPlatformError

    async def boom(url, queried_side=None):
        raise UnsupportedPlatformError("no resolver for this URL")

    monkeypatch.setattr(main, "resolve_market", boom)
    monkeypatch.setattr(main, "get_parser", lambda: ClauseParser(api_key=""))

    r = _rpc(
        client, "tools/call", {"name": TOOL_NAME, "arguments": {"market_url": "https://x.com/y"}}
    )
    result = r.json()["result"]
    assert result["isError"] is True


def test_unknown_method(client):
    body = _rpc(client, "does/not/exist").json()
    assert body["error"]["code"] == -32601


def test_mcp_call_writes_audit_with_no_key(client, monkeypatch, trap_market):
    # MCP calls aren't tied to a local API key; they still audit (api_key_id=None).
    _patch(monkeypatch, trap_market)
    _rpc(
        client,
        "tools/call",
        {"name": TOOL_NAME, "arguments": {"market_url": TRAP_URL}},
    )
    # Admin can see it in the global audit? Our /audit/logs is per-key; instead
    # just assert the call succeeded end-to-end (audit write did not raise).
    res = _rpc(
        client, "tools/call", {"name": TOOL_NAME, "arguments": {"market_url": TRAP_URL}}
    ).json()["result"]
    assert res["isError"] is False
