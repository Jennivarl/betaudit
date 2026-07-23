"""Telegram bot: URL extraction, verdict formatting, handler + webhook + watch/clear."""

from types import SimpleNamespace

import app.main as main
from app import redis_client
from app.config import get_settings
from app.engine import score_market
from app.llm.parser import ClauseParser
from app.telegram import extract_market_url, format_verdict


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def commit(self):
        pass


def _fake_maker():
    return lambda: _FakeSession()


def test_extract_market_url():
    assert (
        extract_market_url("audit this https://polymarket.com/market/abc please")
        == "https://polymarket.com/market/abc"
    )
    assert extract_market_url("https://polymarket.com/event/xyz-123").endswith("xyz-123")
    assert extract_market_url("(https://polymarket.com/market/abc).") == "https://polymarket.com/market/abc"
    assert extract_market_url("no link here") is None
    assert extract_market_url("https://example.com/x") is None


def test_format_verdict_abort(trap_market):
    trap_market.source_of_truth_specified = "Official SEC 8-K Filing"
    resp = score_market(trap_market, analysis=None, queried_side="YES")
    msg = format_verdict(resp)
    assert "ABORT_TRADE" in msg
    assert "risk" in msg.lower()
    assert "🔴" in msg
    assert "Official SEC 8-K Filing" in msg
    assert "<b>" in msg  # HTML formatting


async def test_handler_replies_with_verdict(monkeypatch, trap_market):
    trap_market.source_of_truth_specified = "Official SEC 8-K Filing"
    sent: list[str] = []

    async def fake_send(chat_id, text, token):
        sent.append(text)

    async def fake_action(chat_id, action, token):
        pass

    async def fake_resolve(url, queried_side=None):
        trap_market.market_url = url
        return trap_market

    async def fake_record(session, response, **kw):
        pass

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(main.telegram, "send_message", fake_send)
    monkeypatch.setattr(main.telegram, "send_chat_action", fake_action)
    monkeypatch.setattr(main, "resolve_market", fake_resolve)
    monkeypatch.setattr(main, "get_parser", lambda: ClauseParser(api_key=""))
    monkeypatch.setattr(main, "get_sessionmaker", lambda: (lambda: _FakeSession()))
    monkeypatch.setattr(main, "_record_and_publish", fake_record)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()

    await main.handle_telegram_update(
        {"message": {"chat": {"id": 1}, "text": "https://polymarket.com/market/trap"}}
    )
    assert sent
    assert "ABORT_TRADE" in sent[0]


async def test_handler_start_sends_welcome(monkeypatch):
    sent: list[str] = []

    async def fake_send(chat_id, text, token):
        sent.append(text)

    monkeypatch.setattr(main.telegram, "send_message", fake_send)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()

    await main.handle_telegram_update({"message": {"chat": {"id": 1}, "text": "/start"}})
    assert sent and "BetAudit" in sent[0]


async def test_handler_non_url_prompts(monkeypatch):
    sent: list[str] = []

    async def fake_send(chat_id, text, token):
        sent.append(text)

    monkeypatch.setattr(main.telegram, "send_message", fake_send)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()

    await main.handle_telegram_update({"message": {"chat": {"id": 1}, "text": "hello"}})
    assert sent and "Polymarket market URL" in sent[0]


def test_webhook_noop_without_token(client):
    r = client.post("/telegram/webhook", json={"message": {"chat": {"id": 1}, "text": "hi"}})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_watch_subscribes_with_chat_id(monkeypatch, trap_market):
    sent: list[str] = []
    captured: dict = {}

    async def fake_send(chat_id, text, token):
        sent.append(text)
        return None

    async def fake_action(chat_id, action, token):
        pass

    async def fake_resolve(url, queried_side=None):
        trap_market.market_url = url
        return trap_market

    async def fake_create(session, **kw):
        captured.update(kw)

    monkeypatch.setattr(main.telegram, "send_message", fake_send)
    monkeypatch.setattr(main.telegram, "send_chat_action", fake_action)
    monkeypatch.setattr(main, "resolve_market", fake_resolve)
    monkeypatch.setattr(main.monitor_service, "create_subscription", fake_create)
    monkeypatch.setattr(main, "get_sessionmaker", _fake_maker)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    get_settings.cache_clear()

    await main.handle_telegram_update(
        {"message": {"chat": {"id": 42}, "text": "/watch https://polymarket.com/market/x"}}
    )
    assert captured.get("telegram_chat_id") == "42"
    assert sent and "Watching" in sent[0]


async def test_watching_lists(monkeypatch):
    sent: list[str] = []

    async def fake_send(chat_id, text, token):
        sent.append(text)

    async def fake_list(session, chat, active_only=True):
        return [SimpleNamespace(last_oracle_state="DISPUTED", market_url="https://polymarket.com/market/x")]

    monkeypatch.setattr(main.telegram, "send_message", fake_send)
    monkeypatch.setattr(main.monitor_service, "list_by_chat", fake_list)
    monkeypatch.setattr(main, "get_sessionmaker", _fake_maker)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    get_settings.cache_clear()

    await main.handle_telegram_update({"message": {"chat": {"id": 1}, "text": "/watching"}})
    assert sent and "Watching" in sent[0] and "DISPUTED" in sent[0]


async def test_unwatch(monkeypatch):
    sent: list[str] = []

    async def fake_send(chat_id, text, token):
        sent.append(text)

    async def fake_deact(session, chat):
        return 2

    monkeypatch.setattr(main.telegram, "send_message", fake_send)
    monkeypatch.setattr(main.monitor_service, "deactivate_by_chat", fake_deact)
    monkeypatch.setattr(main, "get_sessionmaker", _fake_maker)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    get_settings.cache_clear()

    await main.handle_telegram_update({"message": {"chat": {"id": 1}, "text": "/unwatch"}})
    assert sent and "Stopped watching 2" in sent[0]


async def test_clear_deletes_tracked_messages(monkeypatch, fake_redis):
    deleted: list[int] = []

    async def fake_del(chat_id, mid, token):
        deleted.append(mid)
        return True

    async def fake_send(chat_id, text, token):
        return 999

    monkeypatch.setattr(main.telegram, "delete_message", fake_del)
    monkeypatch.setattr(main.telegram, "send_message", fake_send)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    get_settings.cache_clear()

    await redis_client.list_push("tg:msgs:7", 101)
    await redis_client.list_push("tg:msgs:7", 102)

    await main.handle_telegram_update(
        {"message": {"chat": {"id": 7}, "message_id": 200, "text": "/clear"}}
    )
    assert 101 in deleted and 102 in deleted  # tracked bot messages
    assert 200 in deleted  # the /clear command itself


async def test_deliver_sends_telegram_alert(monkeypatch):
    import app.telegram as tgmod
    from app.services import monitor as mon

    sent: list = []

    async def fake_send(chat_id, text, token):
        sent.append((chat_id, text))
        return 1

    monkeypatch.setattr(tgmod, "send_message", fake_send)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    get_settings.cache_clear()

    sub = SimpleNamespace(
        telegram_chat_id="42", webhook_url=None, market_url="https://polymarket.com/market/x"
    )
    event = SimpleNamespace(
        old_state="UNDISPUTED", new_state="DISPUTED", severity="high",
        message="disputed", delivered=False, delivery_error=None,
    )
    await mon._deliver(sub, event, _FakeSession())
    assert sent and sent[0][0] == "42"
    assert "DISPUTED" in sent[0][1]
    assert event.delivered is True


def test_webhook_rejects_bad_secret(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cret")
    get_settings.cache_clear()
    r = client.post(
        "/telegram/webhook",
        json={"message": {"chat": {"id": 1}, "text": "hi"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert r.status_code == 403
