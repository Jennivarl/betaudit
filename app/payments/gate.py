"""The x402 payment gate — a FastAPI dependency in front of billable routes.

Runs AFTER API-key auth, so identity + metering + audit stay intact and money
is a second, separate gate. When ``x402_enabled`` is false it is a no-op and the
endpoint is free.

Flow:
  * no ``PAYMENT-SIGNATURE``  -> 402 with a ``PAYMENT-REQUIRED`` challenge header
  * signature present         -> facilitator.verify(); invalid -> 402 again
  * verified                  -> return PaymentState; the endpoint settles after
                                 it has actually produced the result (no result,
                                 no charge — verify moves no funds, settle does).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.config import get_settings
from app.payments.facilitator import Facilitator
from app.payments.x402 import (
    build_payment_required,
    build_requirements,
    decode_header,
    encode_header,
)


@dataclass
class PaymentState:
    required: bool
    verified: bool = False
    payload: dict | None = None
    requirements: dict | None = None


def _challenge(requirements) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail="Payment required. Retry with a signed PAYMENT-SIGNATURE header.",
        headers={"PAYMENT-REQUIRED": encode_header(build_payment_required(requirements))},
    )


async def require_payment(
    x_payment_signature: str | None = Header(default=None, alias="PAYMENT-SIGNATURE"),
) -> PaymentState:
    settings = get_settings()
    if not settings.x402_enabled:
        return PaymentState(required=False)

    requirements = build_requirements(settings)

    if not x_payment_signature:
        raise _challenge(requirements)

    try:
        payload = decode_header(x_payment_signature)
    except ValueError:
        raise _challenge(requirements)

    facilitator = Facilitator(
        settings.okx_base_url, mode=settings.x402_mode, prefix=settings.okx_facilitator_prefix
    )
    result = await facilitator.verify(payload, requirements.to_dict())
    if not result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Payment invalid: {result.reason}",
            headers={"PAYMENT-REQUIRED": encode_header(build_payment_required(requirements))},
        )

    return PaymentState(
        required=True, verified=True, payload=payload, requirements=requirements.to_dict()
    )
