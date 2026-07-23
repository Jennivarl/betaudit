"""x402 wire primitives: payment requirements, header codecs, atomic amounts.

Kept SDK-free — x402 is a wire protocol, so we speak it directly. Header values
are base64-encoded JSON, per the OKX/X Layer spec:

    402 response   PAYMENT-REQUIRED : base64({x402Version, accepts:[requirements]})
    client retry   PAYMENT-SIGNATURE: base64({x402Version, scheme, network, payload})
    200 response   PAYMENT-RESPONSE : base64({success, transaction, network, payer})
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

X402_VERSION = 2
SCHEME_EXACT = "exact"


def to_atomic(amount_human: str, decimals: int) -> str:
    """Convert a human token amount (e.g. '0.05') to an atomic integer string."""
    try:
        scaled = Decimal(str(amount_human)) * (Decimal(10) ** decimals)
    except InvalidOperation as exc:  # pragma: no cover - guards bad config
        raise ValueError(f"invalid token amount: {amount_human!r}") from exc
    if scaled != scaled.to_integral_value():
        # More precision than the asset supports.
        raise ValueError(f"amount {amount_human!r} exceeds {decimals} decimals")
    return str(int(scaled))


def encode_header(obj: dict) -> str:
    """base64(JSON) — the on-the-wire encoding for x402 headers."""
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def decode_header(value: str) -> dict:
    """Decode a base64(JSON) x402 header. Raises ValueError on malformed input."""
    try:
        raw = base64.b64decode(value, validate=True)
        parsed = json.loads(raw)
    except (binascii.Error, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("malformed x402 header") from exc
    if not isinstance(parsed, dict):
        raise ValueError("x402 header is not a JSON object")
    return parsed


@dataclass
class PaymentRequirements:
    """One acceptable way to pay — mirrors the OKX Go pkg struct."""

    scheme: str
    network: str
    asset: str
    amount: str          # atomic integer, as a string
    pay_to: str
    max_timeout_seconds: int
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme,
            "network": self.network,
            "asset": self.asset,
            "amount": self.amount,
            "payTo": self.pay_to,
            "maxTimeoutSeconds": self.max_timeout_seconds,
            "extra": self.extra,
        }


def build_requirements(settings) -> PaymentRequirements:
    """Derive the PaymentRequirements this ASP demands, from settings."""
    return PaymentRequirements(
        scheme=SCHEME_EXACT,
        network=settings.x402_network,
        asset=settings.x402_asset,
        amount=to_atomic(settings.x402_price_usdt, settings.x402_asset_decimals),
        pay_to=settings.x402_pay_to,
        max_timeout_seconds=settings.x402_max_timeout_seconds,
        extra={"assetDecimals": settings.x402_asset_decimals, "priceUsdt": settings.x402_price_usdt},
    )


def build_payment_required(requirements: PaymentRequirements) -> dict:
    """The PaymentRequired document advertised in the 402 challenge."""
    return {"x402Version": X402_VERSION, "accepts": [requirements.to_dict()]}
