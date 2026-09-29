from __future__ import annotations

import os
from base64 import b64decode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionError(Exception):
    pass


class KeyRing:
    """AES-GCM with a key id so a later key can decrypt older ciphertext.

    The server holds these keys. This is not a zero-knowledge scheme and it is
    not the user-passphrase backup designed for a later phase.
    """

    def __init__(self, keys: dict[str, bytes], active_id: str) -> None:
        if not keys or active_id not in keys:
            raise EncryptionError("The active encryption key is missing from the key ring.")
        for key_id, key in keys.items():
            if not key_id or len(key_id.encode("utf-8")) > 64:
                raise EncryptionError("Key ids must be 1 to 64 bytes.")
            if len(key) != 32:
                raise EncryptionError(f"Key {key_id} must be 32 bytes.")
        self._keys = dict(keys)
        self.active_id = active_id

    def encrypt(self, plaintext: bytes) -> bytes:
        key_id = self.active_id.encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._keys[self.active_id]).encrypt(nonce, plaintext, key_id)
        return bytes([1, len(key_id)]) + key_id + nonce + ciphertext

    def decrypt(self, blob: bytes) -> bytes:
        if len(blob) < 2 + 12 + 16 or blob[0] != 1:
            raise EncryptionError("Unrecognised ciphertext.")
        length = blob[1]
        if length < 1 or len(blob) < 2 + length + 12 + 16:
            raise EncryptionError("Unrecognised ciphertext.")
        key_id_bytes = blob[2 : 2 + length]
        try:
            key_id = key_id_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EncryptionError("Unrecognised ciphertext.") from exc
        key = self._keys.get(key_id)
        if key is None:
            raise EncryptionError("No key is available for this ciphertext.")
        nonce = blob[2 + length : 2 + length + 12]
        ciphertext = blob[2 + length + 12 :]
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, key_id_bytes)
        except Exception as exc:
            raise EncryptionError("Ciphertext failed authentication.") from exc


def parse_key_ring(encoded: str, active_id: str) -> KeyRing:
    keys: dict[str, bytes] = {}
    for part in encoded.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise EncryptionError("APP_ENCRYPTION_KEYS entries must look like keyId:base64.")
        key_id, material = item.split(":", 1)
        try:
            raw = b64decode(material, validate=True)
        except Exception as exc:
            raise EncryptionError("An encryption key is not valid base64.") from exc
        keys[key_id.strip()] = raw
    return KeyRing(keys, active_id)
