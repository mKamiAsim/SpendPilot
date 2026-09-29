from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type

# OWASP Password Storage Cheat Sheet, reviewed 29 September 2026:
# Argon2id with m=19456 (19 MiB), t=2, p=1.
password_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

_DUMMY_HASH = password_hasher.hash("spendpilot-timing-padding")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    return True


def verify_password_or_dummy(password_hash: str | None, password: str) -> bool:
    if password_hash is None:
        verify_password(_DUMMY_HASH, password)
        return False
    return verify_password(password_hash, password)


def password_needs_rehash(password_hash: str) -> bool:
    return password_hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
