from __future__ import annotations

import os
from base64 import b64encode

import pytest

from app.core.crypto import EncryptionError, parse_key_ring


def test_encrypt_round_trip_and_rotation():
    first = os.urandom(32)
    second = os.urandom(32)
    encoded = f"v1:{b64encode(first).decode()},v2:{b64encode(second).decode()}"
    original = parse_key_ring(encoded, "v1")
    blob = original.encrypt(b"statement-password")
    assert original.decrypt(blob) == b"statement-password"
    rotated = parse_key_ring(encoded, "v2")
    assert rotated.decrypt(blob) == b"statement-password"
    fresh = rotated.encrypt(b"next")
    assert fresh[2 : 2 + fresh[1]].decode() == "v2"
    with pytest.raises(EncryptionError):
        parse_key_ring(f"v2:{b64encode(second).decode()}", "v2").decrypt(blob)


def test_tampered_ciphertext_is_rejected():
    key = os.urandom(32)
    ring = parse_key_ring(f"v1:{b64encode(key).decode()}", "v1")
    blob = bytearray(ring.encrypt(b"secret"))
    blob[-1] ^= 0x01
    with pytest.raises(EncryptionError):
        ring.decrypt(bytes(blob))
