# Coding-agent prompt — AI-first financial advisor

Attach `AI_Financial_Advisor_Specification.md` alongside this prompt. Paste the instructions below into Cursor or another coding agent. The companion specification is the authoritative detailed scope; this prompt directs implementation. No real statements, bank credentials or API secrets are included.

---

You are the principal engineer and product designer responsible for building this application from scratch. Read the entire attached AI_Financial_Advisor_Specification.md before making changes. Implement a complete, integrated product in milestone-sized increments. Do not stop at a plan, static mockup, generic dashboard, or mocked chat interface.

## Mission

Build an AI-first, privacy-conscious financial advisor that understands monthly credit-card and bank statements, investigates spending behaviour, identifies potential leakage and financial risks, explores scenarios and produces evidence-backed advice. Deep agents are central to the product. Non-LLM mode provides basic analytics and record management as a fallback.

The user selected a Python-first backend. Do not replace this with .NET, Node as the main backend, a hosted-only service, or a third-party finance SaaS. The frontend and backend can run at independent addresses. All primary records reside on the user-controlled backend. The user's local LLM is independently hosted and configured as an endpoint; do not bundle a model server or download model weights.

## Required architecture

- Python, FastAPI, Pydantic, SQLAlchemy, Alembic and PostgreSQL.
- LangChain for model/tool integration; LangGraph for persistent workflow state; Deep Agents for bounded planning, context management and specialist delegation.
- Separate API, document worker and agent worker processes from a cohesive modular backend codebase.
- Durable jobs, cancellation, retries, leases and idempotent effects. Prefer the specification's PostgreSQL-backed queue default; document a justified alternative before introducing infrastructure.
- React, TypeScript, Vite, Tailwind CSS, customised shadcn/ui, TanStack Query/Table, React Hook Form/Zod and Recharts.
- Docker Compose, persistent volumes, health checks and independent frontend/backend configuration.
- No standalone graph/vector database initially. Financial truth belongs in relational records and exact calculations. Add semantic retrieval only for a demonstrated requirement.

Verify compatible maintained package releases and actual APIs using current official documentation. Pin versions and commit lockfiles. Do not write code against remembered experimental APIs. Review the chosen authentication package's maintenance and security posture, parser redistribution licences, and agent persistence support. Record important choices in short ADRs.

## Non-negotiable product requirements

1. Multiple users with open registration, administrator-created accounts, mandatory email verification, username/password login, server-enforced auto-lock and secure password reset. Links must use a complete configured public frontend URL, expire and reject reuse.
2. Administrators manage application settings and accounts, not financial data. Never add impersonation or global transaction browsing. Public users cannot grant themselves administrative roles.
3. Up to ten active cards per user; multiple cards per bank; per-card encrypted saved PDF password. Shared primary/supplementary statements must not duplicate liabilities.
4. Batch PDF imports, local decryption, text extraction, OCR fallback, source provenance, duplicate detection, statement reconciliation and user review. Never present unsupported generic extraction as guaranteed bank support.
5. Credit-card focus with bank statements and manual income/cash/expense entries. Income and financial profile inputs are optional.
6. AED billing only initially. Preserve foreign transaction metadata and Arabic descriptions without introducing multi-currency accounting or an Arabic UI.
7. Calendar-month and statement-cycle reporting, missing-period warnings, exact decimals and correct payment/refund/transfer/instalment semantics.
8. Eighteen-month rolling retention and twelve-month default analytics. Preserve minimal active instalment continuity while deleting expired detailed financial information, including derived memory.
9. User-scoped local/external LLM profiles, explicit sharing scope, connection/capability test, encrypted credentials and no silent external fallback.
10. AI briefing, advisor conversations, adaptive behaviour/risk investigations, scenarios and inspectable evidence. Investment advice, rewards optimisation, SMS ingestion and mobile packaging are deferred.
11. Encrypted user backup/restore with owner isolation and validation. Runtime frontend assets must not depend on CDNs.

## Build a real agent system

Use a controlled outer workflow to authorise a run, freeze a financial snapshot, check coverage and consent, enforce budget, invoke the advisor, validate findings and persist results. Persist checkpoints for restart and clarification/resume. Queue state and LangGraph checkpoint state are separate concerns.

Implement the following specialist responsibilities, invoking only those useful for a request:

- Statement interpretation and contextual categorisation.
- Spending behaviour investigation.
- Payment/instalment obligations and risk investigation.
- Scenario planning.
- Evidence review and synthesis.

Provide typed tools for transaction queries, category aggregates, period comparisons, statement evidence, payment history, instalment schedules, scenario calculations and confirmed preferences. Authentication scope comes from runtime context, never a model-supplied user ID. Pagination and output limits are mandatory.

No arbitrary SQL, unrestricted Python/shell execution, host filesystem browsing, open internet access or unbounded recursive delegation. Configure the Deep Agents harness explicitly so its default capabilities cannot accidentally exceed this scope. Virtual context files, if used, belong to an isolated user/run namespace.

Agents can investigate automatically under user settings. Changes to financial records, adoption of targets and permanent preference updates need a defined user-confirmation action. Source PDFs are untrusted content, never instructions.

Return structured findings with source/calculation references, snapshot ID, assumptions, severity and evidence limitations. Validate every reference and significant numeric claim before publication. A second LLM does not substitute for deterministic validation. Reject or qualify conclusions unsupported by available history. Show activity summaries, not hidden chain-of-thought.

Separate inferred hypotheses from confirmed user facts. Corrections and accepted targets influence future reviews. Retention, deletion and user isolation apply to checkpoints, virtual files, caches, memories and conversations as well as ledger tables.

Simple questions use a short tool-assisted route; monthly reviews use deeper planning. Enforce configurable call, time, concurrency and delegation limits. Provider outages should yield explicit errors or verified partial findings, never mocked successful advice.

## Preserve financial correctness

Use Decimal/Numeric and decimal-string API values. Card bill payments settle liabilities and are not a second purchase expense. Match bank/card payment records conservatively. Cash withdrawals and subsequent cash purchases must not be counted twice. Refunds, cashback, fees, interest, overpayments and transfers remain distinct.

Maintain both acquisition and obligation views for instalments. A known AED 6,000 twelve-month purchase is one acquisition plus AED 500 monthly commitments, not AED 12,000 in spending. Do not invent missing principal, repayment terms, payment timeliness, MCCs or income. Use an unknown status when evidence is insufficient.

Source statement equations and amount signs vary: version bank adapters and reconcile source-defined totals. Keep unreconciled items in review. Corrected imports use a replacement/version flow. Same-amount same-day legitimate purchases cannot be deleted solely by a heuristic duplicate rule.

No representative real bank statements have been supplied. Build clearly labelled synthetic fixtures and an honest parser support matrix. Do not invent a list of certified UAE banks. Structure the adapter interface so authorised redacted real fixtures can be added without redesign.

## Deliver a polished interface

Create a professional financial workspace, not a default component gallery. Define typography, spacing, semantic colours, dark/light themes, motion, cards, buttons, form states and responsive layouts as a coherent design system.

Lead the home screen with a monthly financial briefing. Support it with category trends, commitments, source coverage and actionable findings. Each finding opens evidence and allows a follow-up, correction or scenario. The advisor is persistent and contextual, not a decorative chat widget.

Build all specification screens: authentication, onboarding, overview, cards/accounts, import queue, split-pane statement review, transaction explorer, analytics, obligations/instalments, advisor, scenarios/simple targets, settings and separate administration.

Chart interactions should open filtered transactions. Show source dates, incomplete coverage and observed versus projected amounts. All screens need realistic loading, empty, error and partial states. Provide cancellation/progress for long work and SSE reconnection. Do not let a heartbeat prevent idle locking.

Target keyboard accessibility and WCAG 2.2 AA. Check contrast in both themes, focus order, table navigation, reduced motion and chart alternatives. Use synthetic demo data only in an explicitly separate demo/test mode, never as production placeholders.

## Mandatory visual design execution contract

The specification's sections 10.1–10.5 are binding UI requirements, not optional inspiration. Read them in full before implementing screens. A working backend and default shadcn components are insufficient completion criteria.

Reference direction: [Linear](https://linear.app/) for navigation and interaction discipline, [Mercury](https://mercury.com/) for financial hierarchy, [Monarch](https://www.monarch.com/) for understandable personal-finance presentation, and [shadcn blocks](https://ui.shadcn.com/blocks) for implementation primitives. Study public product screenshots where accessible; create an original composition. Do not clone branding or turn the application into a marketing website. If you cannot visually inspect a reference, say so and follow the explicit screen blueprints instead.

Use the specified navy/teal, restrained light/dark design tokens, clear type scale, tabular money values, grid, responsive shell and border-first surfaces. The product must look intentionally designed. Installing a UI library is not designing the product.

Implement a design vertical slice before mass-producing pages: Overview, Transactions with evidence drawer, and Advisor with structured findings. Use labelled development-only fixtures with consistent totals to test real density and edge cases. Create docs/ui-design-direction.md and a development component preview. The overview must have a dominant financial briefing, a complementary obligations panel and supporting analytical content; do not use equal-sized statistic tiles as the whole design. The advisor must integrate findings, evidence and action controls, not only Markdown chat bubbles.

Run the actual application, capture and visually inspect 1440x900, 1024x768 and 390x844 screenshots. Iterate on observed hierarchy, whitespace, wrapping, chart labels, alignment, contrast and drawer behaviour. Then extend the established components to remaining screens. Do this self-review autonomously; user approval is not required for routine visual refinement. If screenshot inspection is unavailable, report that limitation and leave the visual gate pending rather than claiming success.

Deliver screenshot paths and docs/ui-qa.md covering the section 10.5 rubric, light/dark states, loading/empty/error/partial states, keyboard interaction and 200% zoom. No clipped content, nonfunctional controls, unreadable chart labels or page-wide horizontal overflow may remain. Stock dashboard blocks, generic gradients, fake production data and desktop-only layouts fail acceptance even if tests compile. A rubric score alone does not establish visual quality.

## Security and operational requirements

Use a maintained authentication implementation with established Argon2id/password and random-token primitives. Prefer opaque server-side cookie sessions, HttpOnly/Secure settings, CSRF protection, explicit CORS and production HTTPS. Do not store browser authentication tokens in localStorage.

Ownership checks cover API queries, files, jobs, SSE events, agent tools and restores. Add PostgreSQL RLS as defence in depth with non-owner/non-bypass runtime roles and tested pooled-connection context. Use separate migration privileges.

Encrypt provider keys and statement passwords; never return secrets after saving. Keep encryption key persistence/rotation/recovery documented. Email reset requires configured SMTP; do not claim it works without connectivity. Logs and administrative traces contain metadata rather than financial content. External tracing is disabled by default.

Endpoint configuration must safely allow intended private/local model addresses while preventing SSRF to metadata or control-plane services. Validate schemes, redirects, DNS and credential origin boundaries. File parsing runs with bounded resources and no network access. Cleanup decrypted temporary files after failure and restart.

Document same-site gateway deployment for separately hosted frontend/backend and any supported direct-origin mode. Explain that a container's localhost is not the host LLM address. No hard hardware/GPU requirement; configurable worker concurrency and measured resource use are sufficient.

## Suggested repository layout

```text
backend/
  app/
    api/ core/ identity/ accounts/ ingestion/ ledger/
    analytics/ agents/ scenarios/ lifecycle/ administration/
  migrations/
  tests/
frontend/
  src/
    app/ components/ features/ lib/ styles/
  tests/
infra/
  docker/
docs/
  adr/ api/ operations/ parser-support/
fixtures/
  synthetic/
compose.yaml
.env.example
README.md
```

Adapt structure where useful, retaining domain boundaries and avoiding unnecessary abstractions. Generate frontend API types from the validated API contract. Separate pure calculation functions from providers and persistence so financial logic remains testable.

## Execution sequence

1. Inspect the repository and its instructions. Establish the agreed requirements, make a concise implementation checklist and record missing validation inputs. Do not reopen settled product questions.
2. Build deployment/authentication/ownership foundations and the UI design system. Complete the three-screen visual design slice and screenshot self-review in specification sections 10.1–10.5 before proliferating UI pages.
3. Complete one statement-to-ledger-to-analytics vertical slice with reconciliation and provenance.
4. Implement a real early local-LLM vertical slice: configured endpoint → scoped tools → investigation → validated finding → UI evidence. Do not defer all intelligence until the end.
5. Expand bounded deep-agent workflows, monthly briefings, memory, risk and scenarios.
6. Complete remaining screens, bank/manual flows, lifecycle and administration.
7. Run meaningful security, financial, integration and visual tests; fix failures; document limitations honestly.

Continue routine reversible implementation autonomously. If real bank fixtures, SMTP credentials or an LLM endpoint are unavailable, provide working configuration paths and deterministic test adapters, mark those external validations pending and continue other work. Never present mocks as real integrations or request financial secrets in source files.

## Required tests and evidence

Use pytest/domain tests, PostgreSQL-backed integration tests, parser fixtures, agent contract/evaluation cases and Playwright browser tests. Match the specification's twenty acceptance criteria.

Critical cases: two-user leakage; admin permissions; reset expiry/reuse; duplicate/replayed imports; shared balances; payment double-counting; refunds; instalment conversions; incomplete months; wrong PDF password; malformed model output; invented evidence; prompt injection in a PDF; model timeout; cancellation/resume; expired-data memory removal; corrupt backup; and responsive/keyboard usability.

A CI fake provider is acceptable for repeatable contracts. A real configured-model smoke test is separately required before claiming live agent compatibility. Evaluate whether the system investigates and grounds conclusions, not merely whether it returns fluent text. Capture representative screenshots of completed main flows and resolve visible clipping, contrast and spacing issues.

## Final handover

Provide runnable source, migrations, locked dependencies, Compose configuration, setup/run instructions, environment-variable reference, backup/key-recovery guide, parser support matrix, agent/provider configuration guide, architecture decisions and test results. Include a future-work list matching the specification.

In the final report distinguish implemented and tested, implemented but externally unverified, deferred, and blocked. Identify exact commands to run and any operator configuration required. Do not claim production readiness based solely on a successful build. Do not deploy externally, connect real accounts or publish financial data without explicit user instruction.

Start by reading the specification and repository, then implement the first milestone.
