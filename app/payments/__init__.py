"""x402 pay-per-call layer for the ASP (Phase 3).

Speaks the OKX x402 wire protocol (X Layer extension of Coinbase's x402):
a 402 challenge carrying ``PAYMENT-REQUIRED``, a client retry carrying
``PAYMENT-SIGNATURE``, facilitator verify/settle, and a ``PAYMENT-RESPONSE``
receipt header. Everything is gated behind ``x402_enabled`` so the endpoint is
free until we deliberately turn payment on.
"""
