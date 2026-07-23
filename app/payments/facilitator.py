"""Facilitator client — verifies and settles x402 payments.

Two modes:
  * ``simulate`` — no chain, no network. Verifies that a payload is well-formed
    and returns a deterministic fake settlement. Lets the full 402->pay->200
    handshake run in tests and local dev without a wallet or the OKX facilitator.
  * ``live`` — POSTs to the OKX facilitator (base ``okx_base_url``) to verify the
    signature and settle on X Layer, returning the real tx hash.

The OKX facilitator (from the wire spec):
    GET  {base}{prefix}/supported -> advertised {x402Version, scheme, network}
    POST {base}{prefix}/verify    {paymentPayload, paymentRequirements} -> {isValid, invalidReason}
    POST {base}{prefix}/settle    {paymentPayload, paymentRequirements} -> {success, transaction, network, payer}
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx

SIMULATE = "simulate"
LIVE = "live"


@dataclass
class VerifyResult:
    is_valid: bool
    reason: str = ""


@dataclass
class SettleResult:
    success: bool
    transaction: str | None = None
    network: str | None = None
    payer: str | None = None
    reason: str = ""
    simulated: bool = False

    def to_response_dict(self) -> dict[str, Any]:
        """The PAYMENT-RESPONSE header body."""
        return {
            "success": self.success,
            "transaction": self.transaction,
            "network": self.network,
            "payer": self.payer,
            "simulated": self.simulated,
        }


def _payer_of(payload: dict) -> str | None:
    """Best-effort extraction of the payer address from a payment payload."""
    inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    for key in ("from", "payer", "account"):
        if inner.get(key):
            return str(inner[key])
    auth = inner.get("authorization") if isinstance(inner.get("authorization"), dict) else {}
    if auth.get("from"):
        return str(auth["from"])
    return None


class Facilitator:
    def __init__(self, base_url: str, mode: str = SIMULATE, prefix: str = "", timeout: float = 20.0):
        self._base = base_url.rstrip("/")
        self._prefix = prefix
        self._mode = mode
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self._base}{self._prefix}{path}"

    async def verify(self, payload: dict, requirements: dict) -> VerifyResult:
        if self._mode == SIMULATE:
            if not payload or not isinstance(payload.get("payload"), (dict, str)):
                return VerifyResult(False, "missing payment payload")
            if payload.get("scheme") and payload["scheme"] != requirements.get("scheme"):
                return VerifyResult(False, "scheme mismatch")
            return VerifyResult(True)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url("/verify"),
                json={"paymentPayload": payload, "paymentRequirements": requirements},
            )
            resp.raise_for_status()
            data = resp.json()
        return VerifyResult(bool(data.get("isValid")), str(data.get("invalidReason", "")))

    async def settle(self, payload: dict, requirements: dict) -> SettleResult:
        payer = _payer_of(payload)
        if self._mode == SIMULATE:
            # Deterministic, obviously-fake tx hash derived from the payload.
            seed = f"{payer}:{requirements.get('amount')}:{requirements.get('network')}"
            digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
            return SettleResult(
                success=True,
                transaction=f"0xsim{digest[:60]}",
                network=requirements.get("network"),
                payer=payer,
                simulated=True,
            )

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url("/settle"),
                json={"paymentPayload": payload, "paymentRequirements": requirements},
            )
            resp.raise_for_status()
            data = resp.json()
        return SettleResult(
            success=bool(data.get("success")),
            transaction=data.get("transaction"),
            network=data.get("network"),
            payer=data.get("payer") or payer,
            reason=str(data.get("reason", "")),
        )

    async def supported(self) -> dict:
        if self._mode == SIMULATE:
            return {"kinds": [{"x402Version": 2, "scheme": "exact", "network": "eip155:196"}]}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._url("/supported"))
            resp.raise_for_status()
            return resp.json()
