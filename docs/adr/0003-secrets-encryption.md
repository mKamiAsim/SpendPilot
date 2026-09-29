# ADR 0003: Server-side authenticated encryption

Date: 29 September 2026

## Decision

Application secrets use AES-GCM from `cryptography` 50.0.1. The key ring is `APP_ENCRYPTION_KEYS` (`keyId:base64` entries, each key 32 bytes) and `APP_ENCRYPTION_KEY_ID` selects the key for new ciphertext.

A blob is version byte `1`, a one-byte key-id length, the key id, a 12-byte nonce, then the ciphertext including the GCM tag. The key id is additional authenticated data. Decryption selects the key named in the blob, so an old key can stay on the ring after rotation.

## What this is not

The server holds these keys. This is not zero-knowledge. Saved PDF passwords and provider keys use this ring. A backup uses a separate user passphrase, recorded in ADR 0009. The server stores that archive as ciphertext and cannot read it.

Files, when a later phase stores them, belong on the `protected-files` volume with metadata in Postgres. That volume is not an encrypted filesystem by itself. Do not treat this Compose file as disk encryption.
