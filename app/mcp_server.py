"""Minimal, spec-correct MCP server surface for BetAudit.

Exposes the resolution auditor as a single MCP tool over the Streamable-HTTP
transport (JSON-RPC 2.0 at ``POST /mcp``), so BetAudit is registerable as an
A2MCP ASP on the OKX AI Marketplace. Hand-rolled (no SDK) to match the rest of
the codebase and to reuse the exact verify engine the REST API uses.

Methods handled: ``initialize``, ``ping``, ``tools/list``, ``tools/call``, and
``notifications/*`` (acknowledged, no reply). The actual tool execution lives in
``main`` (it needs the DB session + engine); this module holds the protocol
constants, the tool schema, and the JSON-RPC envelope helpers.
"""

from __future__ import annotations

from typing import Any

from app import __version__
from app.schemas import VerifyResponse

# Protocol versions we understand; we echo the client's if supported, else this.
MCP_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_VERSIONS = {"2025-06-18", "2025-03-26", "2024-11-05"}

TOOL_NAME = "verify_resolution_rules"

SERVER_INFO = {
    "name": "BetAudit",
    "title": "BetAudit — Pre-Trade Simulation Layer",
    "version": __version__,
}

INSTRUCTIONS = (
    "BetAudit audits a prediction market's real resolution rules, oracle metadata, "
    "and dispute terms before an autonomous agent trades it. Call "
    f"{TOOL_NAME} with a Polymarket market_url (and optionally the side you intend "
    "to buy) to get a 0-100 resolution_risk_score and a PROCEED / CAUTION / "
    "ABORT_TRADE action grounded in the market's actual rules."
)

TOOL_DEF: dict[str, Any] = {
    "name": TOOL_NAME,
    "title": "Verify Resolution Rules",
    "description": (
        "Pre-trade compliance check for a prediction market. Reads the market's "
        "real resolution rules + oracle state and returns a 0-100 resolution risk "
        "score, a machine-actionable action (PROCEED / CAUTION / ABORT_TRADE), the "
        "binding source of truth, and concrete rule mismatches a headline-reading "
        "bot would miss."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "market_url": {
                "type": "string",
                "description": "Canonical Polymarket market/event URL to audit.",
            },
            "queried_side": {
                "type": "string",
                "description": "Outcome the agent intends to buy (e.g. 'YES'). Sharpens detection.",
                "default": "YES",
            },
            "subscribe_monitor": {
                "type": "boolean",
                "description": "Register the market for post-trade oracle dispute alerts.",
                "default": False,
            },
        },
        "required": ["market_url"],
    },
}

# JSON-RPC error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def rpc_result(rpc_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def rpc_error(rpc_id: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rpc_id, "error": err}


def negotiate_version(requested: Any) -> str:
    return requested if requested in SUPPORTED_VERSIONS else MCP_PROTOCOL_VERSION


def summarize(response: VerifyResponse) -> str:
    """A compact, human-readable tool result line for the calling agent/LLM."""
    lines = [
        f"{response.action.value} — resolution_risk_score {response.resolution_risk_score}/100 "
        f"(confidence {response.confidence:.2f}).",
        response.summary,
    ]
    pc = response.parsed_contract_data
    lines.append(
        f"oracle={pc.oracle_type}, state={pc.current_oracle_state.value}, "
        f"challenge_window={pc.challenge_window_hours}h, "
        f"source_of_truth={pc.source_of_truth_specified or 'not specified'}."
    )
    for m in response.rule_mismatches_detected:
        lines.append(f"MISMATCH: {m.conflict_reason}")
    return "\n".join(lines)


def tool_success(response: VerifyResponse) -> dict:
    return {
        "content": [{"type": "text", "text": summarize(response)}],
        "structuredContent": response.model_dump(mode="json"),
        "isError": False,
    }


def tool_error(message: str) -> dict:
    """A tool-level error (surfaced to the calling model, not a protocol error)."""
    return {"content": [{"type": "text", "text": message}], "isError": True}
