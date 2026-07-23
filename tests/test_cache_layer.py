"""Redis cache-aside layer: market cache + LLM eval cache, hit/miss + graceful off."""

from app.llm.parser import ClauseParser
from app.schemas import OracleState
from app.services.cache_layer import analyze_cached, resolve_cached
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


def _counting_resolver(market):
    calls = {"n": 0}

    async def resolver(url, side=None):
        calls["n"] += 1
        market.market_url = url
        return market

    return resolver, calls


async def test_market_cache_hit_skips_resolver(fake_redis, trap_market):
    resolver, calls = _counting_resolver(trap_market)

    m1 = await resolve_cached(TRAP_URL, "YES", resolver=resolver)
    m2 = await resolve_cached(TRAP_URL, "YES", resolver=resolver)

    assert calls["n"] == 1  # second call served from cache
    assert m1.market_id == m2.market_id
    assert m2.oracle_type == "UMA_OOv2"
    assert m2.current_oracle_state == OracleState.UNDISPUTED  # enum rehydrated


async def test_market_cache_off_without_redis(trap_market):
    # No fake_redis fixture -> Redis disabled -> resolver called every time.
    resolver, calls = _counting_resolver(trap_market)
    await resolve_cached(TRAP_URL, "YES", resolver=resolver)
    await resolve_cached(TRAP_URL, "YES", resolver=resolver)
    assert calls["n"] == 2


async def test_eval_cache_hit_skips_llm(fake_redis, trap_market):
    # A parser whose client counts calls; second analyze should hit cache.
    calls = {"n": 0}

    class CountingClient:
        def __init__(self):
            self.chat = type(
                "C", (), {"completions": type("D", (), {"create": self._create})()}
            )()

        async def _create(self, **_kwargs):
            calls["n"] += 1
            from tests.conftest import make_llm_response

            return make_llm_response(TRAP_PAYLOAD)

    parser = ClauseParser(client=CountingClient())

    a1 = await analyze_cached(parser, trap_market, "YES")
    a2 = await analyze_cached(parser, trap_market, "YES")

    assert calls["n"] == 1
    assert a1 is not None and a2 is not None
    assert a2.risk_score == 88
    assert a2.source_of_truth == "Official SEC 8-K Filing"
    assert a2.mismatches[0].clause  # rehydrated


async def test_eval_cache_disabled_parser_returns_none(fake_redis, trap_market):
    parser = ClauseParser(api_key="")  # not enabled
    assert await analyze_cached(parser, trap_market, "YES") is None
