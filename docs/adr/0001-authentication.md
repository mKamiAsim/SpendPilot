# ADR 0001: In-repo cookie sessions

Date: 29 September 2026

## Decision

Identity stays in this repository. Passwords are Argon2id via `argon2-cffi` 25.1.0. Sessions are opaque tokens in an HttpOnly `spendpilot_session` cookie (`SameSite=Lax`). The database stores only a SHA-256 hash of the token. CSRF uses a non-HttpOnly `spendpilot_csrf` cookie plus an `X-CSRF-Token` header, compared with `compare_digest` after a length check. Authenticated unsafe requests also match a SHA-256 of that header to `sessions.csrf_token_hash`.

Verification and reset tokens are `secrets.token_urlsafe(32)`, stored as SHA-256 hashes. Verification links last 24 hours. Reset links last 30 minutes. Both are built from `PUBLIC_APP_URL` and never from the request `Host`. A token that is expired or already used is rejected. Reset checks the new password before it consumes the token, then revokes sessions.

Idle lock defaults to 15 minutes and accepts 5–60. The server decides. `POST /api/v1/auth/heartbeat` does not count as activity. A locked session returns 423 except for logout and unlock.

The first administrator comes from `python -m app.identity.bootstrap`, which uses the migrator role, marks that email verified, and refuses if any admin already exists. Public registration cannot set `role=admin`. An administrator can turn public registration off. Unverified users may sign in. Statement import is not in this phase, so the verified-email gate is not exercised against files yet.

Password reset is available only when email mode is `smtp` with `SMTP_HOST` set, or `capture`. `capture` inserts into `mail_outbox` without `RETURNING`, so the runtime role cannot read the token back. Live SMTP is unverified.

## Why not fastapi-users

`fastapi-users` 15.0.5 was reviewed on 29 September 2026. Its cookie transport can set HttpOnly. Its database strategy stores the raw token, expires from `created_at` plus a lifetime (absolute, not idle), and does not provide CSRF or an idle lock. That fights the session model this product requires, including row-level security set per transaction. A smaller in-repo module on Argon2id, hashed cookies, and Postgres is the fit.

## Password parameters

The OWASP Password Storage Cheat Sheet, reviewed 29 September 2026, recommends Argon2id with `m=19456` (19 MiB), `t=2`, `p=1`. `app.core.security` uses those parameters.

## Out of scope

No access token in `localStorage`. The only browser storage key is `spendpilot-theme`. OAuth, passkeys, and impersonation are not part of this phase.
