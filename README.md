# SpendPilot

Self-hosted personal finance app through hardening: identity, the ledger, a monthly briefing, instalments, analytics, encrypted backup, and the acceptance-criteria map. It is not production-ready. Do not deploy it. The handover is `docs/handover.md`. The screenshot pass is `docs/ui-qa.md`.

The product name in the interface is SpendPilot. Statement layouts are synthetic fixtures: a generic AED card, a generic AED bank file, an ADCB LuLu card, one Emirates Islamic card layout, an Emirates NBD Mastercard Platinum, and an ADCB consolidated statement. Real files were not used to confirm the named layouts. A text PDF is not sent through OCR. A scanned page uses the English and Arabic Tesseract data in the image. No model is bundled.

`npm run dev` in `frontend/` still shows a development-only September fixture on Overview, Transactions, and Advisor, plus `/dev/components`. Those figures are not in the production build. Cards and statements call the API in every build.

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

- No real bank statement is in the repository. No bank is named. Both PDFs are synthetic. A named bank is not supported.
- SMTP is not configured and has not been exercised against a real server.
- No OpenAI-compatible model endpoint is configured. `MODEL_SMOKE_URL` is empty, so the live smoke test stays pending. The CI provider is deterministic and is not a hosted fallback. Live tool-calling and a live deep review are not claimed.
- A scanned page is OCR'd only when the file has no text layer. The image includes Tesseract English and Arabic data under their Apache-2.0 notices. See `docs/adr/0004-pdf-ocr-licences.md`. No authorised bank statement was used, so OCR of a real statement is unverified. OCR text is not sent to a model. Document assistance stays off.
- Compose was checked with one unencrypted synthetic card PDF: the document worker committed it, a second upload stayed a duplicate, and the card list did not show the shared closing. The wrong-password batch was not repeated against Compose. A files volume created before this image may be owned by root; new volumes are created for uid 10001.
- Phase 7 mapped the twenty acceptance criteria in `docs/handover.md`. A green test run is not a production claim. Criteria 11 and the live half of 13 stay unverified while `MODEL_SMOKE_URL` is empty. The parser matrix, prompt-injection PDF, cross-user ids, and secret redaction are covered by `backend/tests/test_hardening.py`. CI sets `SPENDPILOT_PROVIDER=fake` and does not fall back to a hosted model.

## Layout

`backend/app` holds the API, identity, cards, import, and analytics. `frontend/src` holds the shell. `infra/docker` holds the images. `docs/adr` records the phase 0 decisions. `docs/parser-support/matrix.md` lists the synthetic layouts. `docs/adr/0009-backup-passphrase.md` records the backup key.
