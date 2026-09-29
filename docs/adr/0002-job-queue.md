# ADR 0002: PostgreSQL job queue

Date: 29 September 2026

## Decision

Jobs use Procrastinate 3.10.0 on the same Postgres database. There is no Redis.

The API reviewed from the 3.10.0 package is `PsycopgConnector(conninfo=...)`, `App.schema_manager.apply_schema()`, `App.run_worker(queues=...)`, and `Blueprint.task(queue=...)` registered with `add_tasks_from(..., namespace="spendpilot")`.

Schema apply is not idempotent. Startup checks `to_regclass('public.procrastinate_jobs')` before applying it, then grants `SELECT, INSERT, UPDATE, DELETE` on `procrastinate%` tables and their sequences to `spendpilot_app`.

Two tasks exist only so the workers can register: `spendpilot:documents.ready` on queue `documents`, and `spendpilot:agents.ready` on queue `agents`. They do not process statements or call a model.

Each worker writes `/tmp/spendpilot-worker-alive` every 5 seconds. The container healthcheck fails if that file is missing or older than 30 seconds.

## Row-level security

Procrastinate’s schema is not covered by the owner policies. These tables hold no user payloads. Owner-scoped jobs remain later work. LangGraph checkpoints are separate owner-scoped tables in ADR 0008. The runtime role is still not a superuser and not `BYPASSRLS`.

## Workers

`document-worker` listens on `documents`. `agent-worker` listens on `agents`. Neither has a shell tool, a filesystem tool, or an open network tool. The document worker is not given outbound network beyond Postgres, which Compose already provides to every backend container. The image installs the document and agent extras. English and Arabic OCR assets are the Debian Tesseract packages. See ADR 0004 and ADR 0008.
