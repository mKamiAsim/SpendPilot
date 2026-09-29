# ADR 0007: Early agent provider

Date: 29 September 2026

## Decision

Phase 4 speaks to an OpenAI-compatible HTTP endpoint saved on the user's provider profile. The API key is AES-GCM ciphertext and is not returned by the API. Consent is `none`, `summary`, or `selected_transactions`. Document assistance stays off, so raw page text is not sent.

`SPENDPILOT_PROVIDER=fake` selects a deterministic in-process provider for CI. It reads the frozen snapshot through the same read-only tools and does not open a socket. `configured` uses only the saved endpoint. A failure does not switch to the fake provider or to a hosted model.

The connection test and every redirect call `validate_endpoint` before the next request. Credentials are not sent to a different host after a redirect. The probe body is the sentence "Reply with ready." and contains no ledger data.

A finding is stored only when its amount equals the snapshot's net spending and every evidence id is in that snapshot. Monthly reviews, specialist roles, and owner-scoped checkpoints are in ADR 0008. The optional `agents` extra is still not installed in the image.

## Unverified

`MODEL_SMOKE_URL` is empty. The live OpenAI-compatible smoke test is implemented and skipped until that URL is set. A scripted HTTP transport covers the tool loop. That script is not a live model, and acceptance criteria 11 and 13 are not passed.
