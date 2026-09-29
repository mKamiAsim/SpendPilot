# Handover

SpendPilot is not production-ready. A green build does not make it a deployment. The interface name is SpendPilot. No bank is named. No model is bundled. No secret is in the repository.

`cd backend && uv run pytest -q` on 29 September 2026: 47 passed, 1 skipped. The skip is `test_live_openai_compatible_smoke` because `MODEL_SMOKE_URL` is empty. Playwright against the gateway: `tests/ui-qa.spec.ts`, `tests/shell.spec.ts`, and `tests/product.spec.ts` passed. Compose was left on `SPENDPILOT_PROVIDER=configured`.

## Implemented and tested

These criteria have deterministic tests. They do not need a live model or a real bank PDF.

1. Another user cannot read rows, documents, events, backups, reviews, checkpoints, cards, provider secrets, or memories by id. Admin status returns an account count and no financial rows. `test_two_users_cannot_read_each_others_rows`, `test_cross_user_ids_and_admin_status_hide_financial_rows`, `test_other_users_cannot_read_a_review_or_memory`.
2. Verification and reset links expire, cannot be reused, and a reset revokes sessions. The link uses the public app URL. Idle lock is server-enforced, and a heartbeat is not activity. `test_verification_expires_and_cannot_be_reused`, `test_reset_expires_cannot_be_reused_and_revokes_sessions`, `test_verification_link_ignores_host_header`, `test_idle_lock_is_server_enforced_and_heartbeat_is_not_activity`.
3. The eleventh active card is rejected. A shared closing stays on the statement. The synthetic bank file creates an account, not an eleventh card. `test_active_card_limit_and_saved_password_is_not_returned`, `test_batch_password_failure_reimport_and_shared_total`, `test_bank_payment_is_not_a_second_spending_event`.
4. A saved PDF password is not returned. A wrong password fails that file only. Passwords and API keys are absent from investigation payloads. `test_active_card_limit_and_saved_password_is_not_returned`, `test_batch_password_failure_reimport_and_shared_total`, `test_fake_investigation_publishes_one_validated_finding`, `test_prompt_injection_pdf_does_not_invent_rows`.
5. The synthetic card fixture reconciles. An unreconciled file stays out of analytics until it is accepted. `test_batch_password_failure_reimport_and_shared_total`, `test_unreconciled_stays_out_of_analytics_until_accepted`.
6. Reimport and a retried import do not double-count. Replaying a published review does not insert a second briefing or a second accepted target. `test_batch_password_failure_reimport_and_shared_total`, `test_replay_publishes_one_briefing_and_one_accepted_target`.
7. A card purchase plus the matching bank payment is one spending event. The bank row is a transfer. Net spending stays 430.00 AED. `test_bank_payment_is_not_a_second_spending_event`.
8. A 6000.00 AED plan in 12 parts is one purchase and 500.00 AED a month. Ten parts before any repayment is 600.00 AED a month. A repayment is not spending. `test_instalment_is_one_purchase_and_terms_can_change`.
9. Fewer than twelve posted months is marked as not complete coverage. `test_bank_payment_is_not_a_second_spending_event` asserts that note. The empty-snapshot fake finding also says it is not a claim about a complete month. The fixture investigation publishes the calculated net, and that path does not use the empty-month sentence.
10. Analytics still runs when consent is off and no provider is required for that screen. The fake provider test refuses `httpx.Client`. That is an in-process check, not an operating-system firewall. `test_custom_category_counts_and_analytics_works_with_consent_off`, `test_fake_investigation_publishes_one_validated_finding`.
12. Local and scripted payloads drop passwords, API keys, storage paths, and owner ids. A model amount of 0.00 is rejected when net spending is 10.00. An instruction-only PDF invents no rows. A note on a valid file is not a row. A description that says to report 0.00 is stored as data, and the published amount stays the calculated net. Configured mode raises on a blocked endpoint and does not call the fake provider or a hosted model. `test_injected_amount_is_rejected_and_descriptions_are_data`, `test_prompt_injection_pdf_does_not_invent_rows`, `test_configured_mode_does_not_fall_back_to_the_fake_provider`, `test_configured_review_does_not_fall_back`. The bytes a real model would receive were not observed.
14. Scenario numbers come from the calculation. Missing income blocks an affordability claim. With 1000.00 AED of income, the leftover after a 10.00 AED grocery reduction is 580.00 AED. `test_missing_income_blocks_an_affordability_claim`, `test_income_allows_only_the_calculated_leftover`.
15. A confirmed category correction marks the finding, briefing, and scenario stale, and the exact description rule applies on the next import. `test_replay_publishes_one_briefing_and_one_accepted_target`, `test_confirmed_category_rule_applies_on_the_next_file`.
16. Purge removes old cash, memories, and snapshots. An instalment with a remaining balance stays. A fully repaid old plan is removed. Restore reapplies the cutoff. `test_purge_removes_old_rows_and_derived_memory`, `test_corrupt_backup_does_not_change_existing_data`.
17. Backup restore covers a valid archive, a wrong passphrase, a corrupt file, and a second restore that does not duplicate. Another user cannot download the backup. `test_corrupt_backup_does_not_change_existing_data`.
18. Desktop, 200% zoom, and a phone keyboard pass are in `docs/ui-qa.md`. Analytics uses a table of amounts, not colour alone. Contrast was not measured with a tool.
19. Compose starts from `.env.example` and the documented commands. The gateway is same-site on `127.0.0.1:8080`. Fonts are self-hosted. This was not a fresh-machine install.
20. `docs/parser-support/matrix.md` lists two synthetic layouts and rejects every other file. `test_parser_matrix_lists_synthetic_layouts_only`. No real bank is advertised as supported.

CI is `.github/workflows/ci.yml`. The job sets `SPENDPILOT_PROVIDER=fake` and an empty `MODEL_SMOKE_URL`, then runs pytest. `test_ci_uses_the_fake_provider` checks that the test process is on the fake provider and that the smoke URL is empty. The workflow has not been observed on GitHub from this machine. Playwright is not in that workflow because it needs the gateway.

The investigation prompt tells the model that transaction descriptions are untrusted data, not instructions. That sentence does not by itself prove a live model will ignore them.

## Implemented but externally unverified

- Criterion 11. The live smoke test is skipped while `MODEL_SMOKE_URL` is empty. A fake-provider finding is not this criterion.
- Criterion 13, live half. Caps, cancel, resume, one briefing, and an honest SSRF failure are tested on the fake path (`test_short_questions_do_not_delegate_and_caps_hold`, `test_replay_publishes_one_briefing_and_one_accepted_target`, `test_configured_review_does_not_fall_back`). A complex monthly review against a real model was not run.
- Criterion 12, live half. Redaction is tested against the scripted client and stored snapshots. A packet captured at a real model endpoint was not.
- Criterion 10, operating-system half. The fake provider does not construct an HTTP client. Networking was not blocked outside the process.
- Live SMTP. `test_reset_stays_off_without_smtp` checks the empty-host path. No message was sent through a mail server.
- Visual contrast, and the evidence drawer, were not part of the phase 7 screenshot pass.
- The GitHub Actions run itself. The workflow file is in the tree. This environment did not watch it go green.

## Deferred

OCR and scanned statements, named bank layouts, LangGraph and Deep Agents, Arabic and RTL, an offline installer, rewards and MCC, foreign exchange, bank login, bundled model weights, and a production deployment. See ADR 0004 and ADR 0008.

## Blocked

- `MODEL_SMOKE_URL` is empty, so criteria 11 and the live half of 13 stay unverified.
- No authorised bank PDF is available, so criterion 20 cannot move past synthetic layouts.
- `SMTP_HOST` is empty, so live mail stays unverified.

Do not read a green pytest line as production-ready.
