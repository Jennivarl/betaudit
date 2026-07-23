"""x402 wire primitives: atomic amounts + header codec round-trips."""

import pytest

from app.payments.x402 import decode_header, encode_header, to_atomic


def test_to_atomic_scales_by_decimals():
    assert to_atomic("0.05", 6) == "50000"
    assert to_atomic("1", 6) == "1000000"
    assert to_atomic("0", 6) == "0"
    assert to_atomic("12.34", 6) == "12340000"


def test_to_atomic_rejects_excess_precision():
    # 6-decimal asset can't represent 7 decimal places.
    with pytest.raises(ValueError):
        to_atomic("0.0000001", 6)


def test_header_round_trip():
    doc = {"x402Version": 2, "accepts": [{"scheme": "exact", "amount": "50000"}]}
    assert decode_header(encode_header(doc)) == doc


def test_decode_rejects_garbage():
    with pytest.raises(ValueError):
        decode_header("$$not-base64$$")
