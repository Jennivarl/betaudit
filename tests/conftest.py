"""Shared fixtures + fakes so tests run with no network and no API key."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import redis_client
from app.config import get_settings
from app.resolvers.base import ResolvedMarket
from app.schemas import OracleState, Platform

TRAP_URL = "https://polymarket.com/event/company-x-releases-product-y"


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point every test at a fresh temp SQLite DB with admin routes open.

    Also resets the Redis singleton so no fake client leaks between tests; by
    default REDIS_URL is unset, so caching/rate-limiting/pub-sub all no-op.
    """
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("ADMIN_TOKEN", "")
    get_settings.cache_clear()
    redis_client.reset_client()
    yield
    get_settings.cache_clear()
    redis_client.reset_client()


@pytest.fixture
def fake_redis():
    """Install an in-memory fake Redis as the active client for a test."""
    import fakeredis.aioredis

    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_client.set_client(client)
    return client


@pytest.fixture
def client(_isolated_db):
    """TestClient with lifespan run, so the DB engine + tables exist."""
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def api_key(client) -> str:
    """A freshly minted API key (admin routes are open in tests)."""
    resp = client.post("/admin/keys", json={"label": "test"})
    assert resp.status_code == 200, resp.text
    return resp.json()["api_key"]


@pytest.fixture
def auth_headers(api_key) -> dict:
    return {"X-API-Key": api_key}


@pytest.fixture
def trap_market() -> ResolvedMarket:
    """A normalized market that mirrors the demo 'trap' case."""
    return ResolvedMarket(
        platform=Platform.POLYMARKET,
        market_id="0x1234...5678",
        market_url=TRAP_URL,
        question="Will Company X release Product Y by May 31?",
        outcomes=["Yes", "No"],
        resolution_criteria=(
            "Resolves YES only upon an Official SEC 8-K Filing confirming the release "
            "by May 31. Media reports do not qualify."
        ),
        source_of_truth_specified=None,  # not declared in metadata; LLM must extract it
        oracle_type="UMA_OOv2",
        challenge_window_hours=2.0,
        current_oracle_state=OracleState.UNDISPUTED,
        raw_sources=[
            {"label": "Polymarket resolution criteria", "snippet": "Requires SEC 8-K.", "url": TRAP_URL}
        ],
    )


def make_llm_response(payload: dict) -> SimpleNamespace:
    """Fake OpenAI chat.completions.create() result with a forced function call.

    Arguments are serialized to a JSON string, exactly like the real API, so the
    parser's json.loads path is exercised.
    """
    fn = SimpleNamespace(name="report_resolution_analysis", arguments=json.dumps(payload))
    call = SimpleNamespace(function=fn)
    message = SimpleNamespace(tool_calls=[call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOpenAI:
    """Stand-in for AsyncOpenAI whose chat.completions.create returns a canned payload."""

    def __init__(self, payload: dict):
        self._payload = payload
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **_kwargs):
        return make_llm_response(self._payload)
