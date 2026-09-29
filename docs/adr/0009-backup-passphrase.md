# ADR 0009: User-passphrase backups

Date: 29 September 2026

## Decision

A backup is sealed with a passphrase the user chooses at export time. Argon2id derives a 32-byte key (one pass, 8 MiB, parallelism 1) from a random 16-byte salt. AES-GCM encrypts the JSON with a random nonce. The stored blob is version byte `1`, the salt, the nonce, and the ciphertext. The server keeps that blob in `backups` and does not store the passphrase or the derived key, so it cannot read the archive later.

The default export omits provider API keys and saved PDF passwords. An export includes them only when `include_secrets` is set. Restore decrypts the whole archive before any write. A wrong passphrase or corrupt ciphertext returns an error and leaves existing rows unchanged. A successful restore writes as the signed-in owner, ignores any owner id in the file, and then applies the 18-month purge.

The server key ring in ADR 0003 is a different mechanism. It still encrypts PDF passwords and provider keys at rest. It is not the backup key.

## Unverified

This has not been exercised against a lost server key or a real operator volume. Losing `APP_ENCRYPTION_KEYS` still makes saved PDF passwords and provider keys unreadable. A backup that did not set `include_secrets` cannot bring those secrets back.
