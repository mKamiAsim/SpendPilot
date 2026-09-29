# SpendPilot

Self-hosted personal finance foundation. This tree is phases 0 and 1 only: decisions, Compose, identity, row-level isolation, and the application shell. It is not production-ready. Do not deploy it.

The product name in the interface is SpendPilot. Statement import and the ledger are later phases.

`npm run dev` in `frontend/` shows a development-only September fixture on Overview, Transactions, and Advisor, plus `/dev/components`. Those figures are not in the production build. They are not a statement and they do not name a bank. The production gateway shows an empty state instead.

## Run locally

1. Copy `.env.example` to `.env` and replace the placeholder passwords. Leave `SMTP_HOST` empty. No bank PDF, mailbox, or model endpoint is required.
2. `docker compose up --build`
3. Open `http://127.0.0.1:8080`

The gateway is bound to `127.0.0.1:8080`. Postgres has no host port. The official Postgres image starts as root and drops to the `postgres` user. The API, both workers, and the gateway run as non-root.

Create the first administrator once, after the API is healthy:

```bash
docker compose --profile bootstrap run --rm bootstrap
```

Set `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL`, and `BOOTSTRAP_ADMIN_PASSWORD` in `.env` before that command. The command refuses to run if an administrator already exists.

`EMAIL_DELIVERY=capture` stores outgoing messages in `mail_outbox` so tests can run without SMTP. That table is not a mailbox. Live SMTP is unverified.

## Tests

Backend tests start a disposable Postgres container and need Docker:

```bash
cd backend && uv run pytest
```

With Compose already serving the gateway:

```bash
cd frontend && npx playwright test
```

## What is unverified

- No bank or card statement is in the repository. No bank is named.
- SMTP is not configured and has not been exercised against a real server.
- No OpenAI-compatible model endpoint is configured. The SSRF helper does not make a network call.
- OCR engines and language data are not in the image. See `docs/adr/0004-pdf-ocr-licences.md`.

## Layout

`backend/app` holds the API, identity, and empty domain packages. `frontend/src` holds the shell. `infra/docker` holds the images. `docs/adr` records the phase 0 decisions.
