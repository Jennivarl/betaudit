"""Telegram bot surface (Phase 6) — helpers + message formatting.

The bot runs in webhook mode on the existing web service: Telegram POSTs updates
to ``/telegram/webhook`` (wired in main.py), which runs the same verify engine
as the REST/MCP paths and replies in chat. This module holds the Telegram HTTP
helpers, the market-URL extractor, and the verdict formatter.
"""

from __future__ import annotations

import re

import httpx

from app.schemas import VerifyResponse

_API = "https://api.telegram.org"
_TIMEOUT = 20.0

# Matches a Polymarket market/event URL anywhere in a message.
_URL_RE = re.compile(r"https?://(?:www\.)?polymarket\.com/\S+", re.IGNORECASE)

WELCOME = (
    "🛡️ <b>BetAudit</b> — pre-trade resolution auditor\n\n"
    "Send me a <b>Polymarket market URL</b> and I'll read its real resolution "
    "rules, oracle state, and dispute terms, then hand back a 0–100 risk score "
    "and a verdict: <b>PROCEED</b> / <b>CAUTION</b> / <b>ABORT_TRADE</b>.\n\n"
    "Try one:\n"
    "<code>https://polymarket.com/market/new-rhianna-album-before-gta-vi-926</code>\n\n"
    "<b>Commands</b>\n"
    "• <code>/watch &lt;url&gt;</code> — get pinged if the oracle disputes or resolves\n"
    "• <code>/watching</code> — list what you're watching\n"
    "• <code>/unwatch</code> — stop all alerts\n"
    "• <code>/clear</code> — delete my messages in this chat\n\n"
    "Grounded in the rules, not the headline."
)

PROMPT = (
    "Send me a <b>Polymarket market URL</b> to audit "
    "(e.g. <code>https://polymarket.com/market/&lt;slug&gt;</code>)."
)

_ACTION_EMOJI = {"ABORT_TRADE": "🔴", "CAUTION": "🟠", "PROCEED": "🟢"}
_ACTION_WORD = {"ABORT_TRADE": "ABORT_TRADE", "CAUTION": "CAUTION", "PROCEED": "PROCEED"}


def extract_market_url(text: str) -> str | None:
    m = _URL_RE.search(text or "")
    return m.group(0).rstrip(").,") if m else None


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_verdict(r: VerifyResponse, base_url: str = "https://betauditmcp.xyz") -> str:
    action = r.action.value
    emoji = _ACTION_EMOJI.get(action, "⚪")
    pc = r.parsed_contract_data
    lines = [
        f"{emoji} <b>{_ACTION_WORD.get(action, action)}</b> — risk <b>{r.resolution_risk_score}/100</b>",
        "",
        f"<b>Market:</b> <a href=\"{_esc(r.market_url)}\">{_esc(pc.oracle_type)} market</a>",
        f"<b>Oracle:</b> {_esc(pc.oracle_type)} · state {pc.current_oracle_state.value}"
        + (f" · window {pc.challenge_window_hours}h" if pc.challenge_window_hours is not None else ""),
    ]
    if pc.source_of_truth_specified:
        lines.append(f"<b>Source of truth:</b> {_esc(pc.source_of_truth_specified)}")
    if r.rule_mismatches_detected:
        lines.append("")
        lines.append("<b>Why:</b>")
        for m in r.rule_mismatches_detected[:4]:
            lines.append(f"• {_esc(m.conflict_reason)}")
    lines.append("")
    lines.append(f"<i>confidence {r.confidence:.2f} · {base_url.replace('https://', '')}</i>")
    return "\n".join(lines)


_SEVERITY_EMOJI = {"high": "🔴", "medium": "🟠", "low": "⚪"}


def format_alert(sub, event) -> str:
    """A dispute/state-change alert for a watched market."""
    emoji = _SEVERITY_EMOJI.get(event.severity, "🚨")
    return "\n".join(
        [
            f"{emoji} <b>Oracle alert</b> — a market you're watching changed.",
            "",
            f"<b>{event.old_state} → {event.new_state}</b>",
            _esc(event.message),
            f"<a href=\"{_esc(sub.market_url)}\">view market</a>",
        ]
    )


async def send_message(chat_id: int | str, text: str, token: str) -> int | None:
    """Send a message; returns the Telegram message_id (for later deletion)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{_API}/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
    try:
        return r.json()["result"]["message_id"]
    except Exception:  # noqa: BLE001
        return None


async def delete_message(chat_id: int | str, message_id: int, token: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{_API}/bot{token}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id},
            )
        return bool(r.json().get("ok"))
    except Exception:  # noqa: BLE001
        return False


async def send_chat_action(chat_id: int | str, action: str, token: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(
                f"{_API}/bot{token}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
            )
    except Exception:  # noqa: BLE001 - typing indicator is best-effort
        pass
