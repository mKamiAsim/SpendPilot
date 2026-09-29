# AI Financial Advisor — Functional and Technical Specification

Version 1.1 • 29 September 2026 • Implementation baseline for review

## 1. Product definition

Build an AI-first personal financial application that investigates credit-card and bank statements, explains spending behaviour, identifies potential leakage and financial risks, and helps users make practical changes. Deep agents are the central product capability. Charts and deterministic calculations supply evidence to those agents. Users who decline an LLM retain useful statement management and basic analytics.

The initial release serves individual users through a multi-user, user-controlled installation. It focuses on UAE-issued, AED-billed cards, up to ten active cards per user. Both the frontend and backend are independently deployable. Financial information stays on the user's backend unless that user authorises relevant external LLM processing. A local model is an independently hosted endpoint; this application does not install or run model weights.

This document distinguishes agreed requirements from recommended implementation defaults. Defaults below make the specification implementable; they are not claims that every detail was explicitly selected by the user. No production deployment, account connection, or real financial processing is authorised by this document alone.

## 2. Agreed scope and release boundaries

| Area | Initial release |
|---|---|
| Access | Multiple users; username/password; required verified email; open registration and administrator-created accounts |
| Isolation | Each user's statements, credentials, records, conversations and settings are private through application permissions |
| Administration | Application configuration, user lifecycle, email setup and operational health; no financial-data browsing or impersonation |
| Cards | Up to ten active cards per user; several cards may belong to one bank |
| Sources | Password-protected PDF card statements, bank statements, manual cash/income/expense entries |
| Passwords | Encrypted saved password per card; not sent to an LLM |
| Frequency | Monthly statement-based analysis; no claim of real-time balances |
| Reporting | Calendar months across cards and individual statement cycles |
| History | Rolling eighteen-month retention; twelve-month default analytics window |
| AI | User-configured local or external provider, endpoint, model and optional API key; explicit consent; basic fallback |
| Advice | Spending, payment behaviour, obligations, scenarios and potential risks; no investment advice |
| Instalments | Separate purchase and repayment views; preserve active future obligations |
| Currency | AED billing only; preserve foreign transaction metadata without introducing FX portfolio accounting |
| Interface | English; responsive modern web UI; preserve Arabic statement descriptions |
| Deployment | Docker capability; separately addressed frontend/backend supported |
| Backup | Encrypted user backup/export and restore |

Deferred: reward optimisation and MCC-based recommendations; mixed billing currencies; SMS/email transaction ingestion; mobile packaging; Arabic/RTL UI; fully disconnected installation packaging; advanced category-monitoring controls; sophisticated progress coaching. Actual cashback or points printed on a statement may be displayed as source information, without reward optimisation.

No direct bank login, automatic payment, subscription cancellation, investment execution or autonomous credit application is included. No claim of universal bank-format accuracy or fraud detection certification.

## 3. User journeys

### 3.1 Installation and account onboarding

1. Installer configures the backend address, frontend public URL, allowed frontend origins, persistent storage, application encryption key and SMTP settings.
2. A one-time bootstrap mechanism creates the first administrator; public registration can never select an administrator role.
3. User registers a unique username and email with password. Email verification is required before uploading financial information.
4. Verification links use a configured complete public frontend URL and expiring single-use tokens. Administrator-created users receive a setup/verification link rather than an emailed password.
5. First login explains local backend storage and offers AI configuration or Continue with basic analytics. Optional income/balance/commitment fields can be skipped.
6. User creates card profiles and saves passwords if desired. Card display uses aliases and masked identifiers; full PAN/CVV are neither requested nor retained deliberately.

Startup/new browser-session access requires authentication. Recommended default idle timeout: 15 minutes, configurable within installation bounds. Server-side expiration is authoritative. Background processing or an SSE heartbeat does not count as user activity. Forgotten-password flow is available only when email delivery is configured; a fully disconnected recovery approach is deferred with packaging.

### 3.2 Monthly statement import

User selects multiple PDFs spanning cards and months. Each file has its own progress and outcome. The app detects duplicates, identifies likely accounts and periods, and asks for confirmation when ambiguous. A bank statement can use a password supplied for that import; optional account-scoped encrypted password storage uses the same protection as card passwords.

Successful extraction goes through reconciliation. Verified results become available automatically. Uncertain fields, totals or mappings enter a review queue. The review workspace shows the PDF page next to extracted rows; users can edit, split categories, assign a card, and reject a bad import. A clear explicit action permits accepting a known discrepancy with a reason; such data remains flagged and cannot masquerade as verified.

After a verified batch, an enabled AI review is queued once per changed data snapshot. Batch coalescing prevents one costly monthly review per PDF. If the user disabled automatic reviews, show Run monthly review instead. External processing follows the user's saved consent scope and budget; no silent provider fallback.

### 3.3 Financial briefing and conversation

The home page leads with a monthly briefing: what changed, what deserves attention, and which actions could help. Each finding links to evidence and offers Ask about this, Explore scenario, Correct assumption, and Dismiss. Basic mode shows the same records and baseline charts but clearly identifies intelligent review as unavailable.

A user can ask cross-card questions, compare months, investigate a merchant, or explore a proposed reduction. Follow-ups retain the relevant scope. The advisor asks a focused question when information essential to a conclusion is missing. Users can accept a simple target and later compare results; extensive coaching automation is deferred.

### 3.4 Corrections, deletion and account changes

Corrections preserve original source values and a user-visible change history. They increment the financial snapshot version and mark affected insights/scenarios stale. Re-analysis updates rather than silently appending contradictory briefings. Closed cards remain in historical reporting; the ten-card limit applies to active cards as an implementation default. Account disablement revokes sessions and prevents new/resumed jobs. Account deletion removes financial records, files, secrets, memory and derived results under a documented lifecycle.

## 4. Functional modules

### Cards and accounts

Card alias, bank, masked identifier, AED billing currency, optional limit, observed statement dates/due dates, encrypted password and active/closed status. Do not assume due dates are constant. Support a statement containing multiple primary/supplementary cards and shared account-level totals: allocate transactions to known cards without duplicating shared balances or liabilities.

Bank accounts supply observed balances, transfers and income where available. Manual entries include date, amount, direction, category, description and account/cash designation. Transfers between own accounts and payments to cards are not new spending. Cash withdrawals move value to cash; manually recorded purchases must not double-count the withdrawal.

### Transactions and categorisation

Retain transaction date, posting date, original description, normalised merchant, exact amount, currency, debit/credit meaning, type, account/card, source page/row and extraction status. Preserve foreign amount/currency if printed, while using the bank's posted AED amount as authoritative.

Types include purchase, payment, refund, fee, interest, cashback credit, transfer, instalment posting, cash advance and unknown. Categorisation priority: user correction, user rule, reliable existing mapping, model suggestion, uncategorised. Suggested necessity/luxury labels are editable contextual judgements. Never infer MCC as a confirmed fact from a merchant name. Split amounts must sum exactly to the original amount.

### Basic analytics

Spending totals and trends, category/merchant/card filters, gross purchases, refunds and net spending, fees and interest, observed payments, instalment commitments and statement coverage. Use original-purchase refunds where confidently matched; otherwise show a separate refund in its posted period and explain the treatment. Cashback is a distinct credit and not a purchase refund.

Calendar spending uses transaction dates where available, with clearly labelled posting-date fallback. Statement reconciliation uses posted statement entries. Exclude internal transfers from consolidated expense totals. Define each percentage denominator in the UI. Month comparisons identify partial coverage and avoid comparing an incomplete month to a complete month as if equivalent.

### AI analytics and risk

Adaptive investigations cover frequency versus ticket-size changes; recurring merchant spend; sustained category concentration; new or increased recurring charges; fees; possible duplicate charges; debt/instalment accumulation; and observed payment behaviour. Distinguish an anomalous charge from proven fraud, recurring payments from confirmed subscriptions, and a subscription from one the user actually does not use.

Do not infer financial distress from high dining spend alone. Without reliable income and balances, discuss card obligations and spending patterns, not definitive affordability. Payment posting alone may not prove payment by the exact due date; include unknown/insufficient-evidence outcomes. Account credits may represent refunds or overpayment, not income.

### Scenarios and targets

User or agent specifies a proposed category reduction, purchase, or repayment change. The calculation tool returns baseline, assumptions, date range and exact effects. No generic UAE interest rate or invented repayment rule: exact debt-interest projections require user-provided/verified card terms; otherwise label estimates or decline that calculation. Savings scenarios do not imply investment returns.

### Instalments

Record original amount if known, plan identifier, monthly amount, remaining instalments, end date, principal/fee split if supplied and source evidence. A missing original amount stays unknown. Purchase analysis counts the original purchase once where known; obligation analysis shows scheduled repayments. Never add both together into a single spending total. Identify plan conversions to avoid treating converted purchases as a second acquisition. Early settlements and adjustments need explicit mappings or review. Forecasts derived from statement counts are labelled estimates.

## 5. AI architecture

### Runtime design

Use LangChain integrations and typed tools, LangGraph for persistent workflow state, and Deep Agents for bounded planning and delegation. A controlled outer workflow establishes authorisation, data coverage, consent and budget before invoking a financial advisor deep agent. Simple factual questions use a short route; investigations use specialist delegation. All agents run on the user-controlled backend through that user's model connection.

| Role | Responsibility | Required evidence |
|---|---|---|
| Advisor/orchestrator | Plan investigation, choose specialists, reconcile findings, produce prioritised response | Snapshot and tool result references |
| Statement interpreter | Resolve ambiguous descriptions/layouts and propose categories | Source page/row; no bypass of reconciliation |
| Behaviour investigator | Analyse frequency, merchant mix and sustained category changes | Comparable periods and transaction cohorts |
| Obligations/risk investigator | Examine payments, charges and instalment commitments | Observed balances, dates, terms and coverage |
| Scenario planner | Suggest realistic interventions and invoke calculations | Explicit assumptions and calculation result IDs |
| Evidence reviewer | Challenge unsupported claims and contradictions | Referenced data plus deterministic validation results |

Specialists are logical roles, not separate mandatory servers or compulsory calls on every request. Start with fixed specialist definitions and shallow bounded delegation. Never run an unbounded recursive agent swarm. A model-based reviewer supplements exact validation; it is not proof of correctness.

### Monthly review workflow

Queued → authorise → acquire snapshot → assess coverage → retrieve relevant memories → plan → investigate → calculate scenarios → validate claims → persist briefing → stream completion. Ambiguity can produce a user question and a persistent pause. Cancellation, timeout or provider failure yields a clear state and verified partial results if any. Resume rechecks ownership, current consent and snapshot validity. Restarting a worker must not duplicate accepted targets or publish duplicate reviews.

### Tool contract

Tools include get_data_coverage, query_transactions, aggregate_spending, compare_periods, inspect_statement_evidence, get_payment_history, get_instalment_schedule, calculate_scenario, retrieve_confirmed_preferences, propose_category_correction and propose_target. Tools expose validated filters and finite result limits, not arbitrary SQL or Python execution.

Authenticated user identity is injected by the runtime and cannot be supplied or changed by the model. A guessed transaction ID from another user returns no information. Proposed mutations are staged; users approve financial-record edits and goal adoption through normal application endpoints. Pure analysis and read-only investigations can run automatically under the user's settings.

Disable default shell/code execution, unrestricted filesystem tools and open internet tools in the agent harness. If virtual files are needed for context management, use an isolated per-user/per-run backend with allowlisted operations and bounded size. No host filesystem mount is exposed to the model.

### Structured outputs

Each finding contains: finding_id, snapshot_id, kind, title, plain-language explanation, severity, evidence_refs, calculation_refs, assumptions, coverage limitations, confidence basis, suggested actions, created_at and stale status. Confidence is a qualitative evidence assessment, not a calibrated probability unless separately validated. Render structured insight cards as well as narrative responses.

Evidence references are durable internal IDs resolved by the backend. Reject invented or unauthorised references. Numeric claims must match calculation results or source facts. If validation fails, attempt a bounded correction and then return an honest incomplete finding.

### Memory

Separate conversation history, confirmed preferences, correction rules, accepted targets and inferred hypotheses. Hypotheses are not promoted to facts without evidence or confirmation. Users can inspect/delete memories. Key every thread, checkpoint, store entry and cache by owner. Maintain source lineage so retention and user deletion remove stale derived personal information. No unreviewed self-modification of production system prompts.

### Provider configuration and consent

Per-user profiles contain connection type, endpoint, model, encrypted API key if required, timeout and execution budget. Support a local OpenAI-compatible connection and explicit provider adapters; compatibility is tested, not assumed. Local endpoints may use unauthenticated connections on a trusted private network, with a clear deployment setting. Never expose saved secrets back to the browser.

Test streaming, structured output, tool calling and context limits using synthetic nonfinancial probes. Unsupported models receive actionable feedback and a clearly identified reduced route, not fabricated success. No automatic switch to an external provider.

Consent levels: no LLM; summary-level sharing; selected transaction details; separately authorised document/page assistance. Store a consent version on each run. Minimise and redact outbound payloads; account identifiers, PDF passwords and credentials never enter prompts. A configured local endpoint is reached from the backend/container, not necessarily the browser; explain this on the setup screen. Basic processing remains available after provider failure.

Proposed conservative defaults, configurable: maximum 40 model calls per deep review, delegation depth 2, two simultaneous specialist calls, 10-minute run deadline. These are initial limits to tune through evaluation, not guarantees of capability. Track token use where reported; cost estimates require actual configured pricing and must not be invented for local models.

## 6. Backend and data architecture

Python/FastAPI with Pydantic request/response validation; SQLAlchemy with Alembic migrations; PostgreSQL primary storage; separate Python worker processes; React/TypeScript/Vite frontend. Select and pin compatible maintained releases during implementation rather than hardcoding an unverified latest version here.

Use a modular monolith with independently running API and workers. Suggested modules: identity, users, accounts, ingestion, ledger, categorisation, analytics, agents, scenarios, lifecycle and administration. Services share explicit domain interfaces, not arbitrary cross-module database writes.

Recommended initial job mechanism: PostgreSQL-backed durable queue with transactional enqueue, leases, heartbeat, attempt count and idempotency keys. Queue claiming can use row locking with SKIP LOCKED. Include bounded retries, abandoned-lease recovery and dead-letter inspection. Prefer a maintained compatible implementation when verified; do not add Redis solely for convention. Job delivery may repeat, so all effects must be idempotent. LangGraph checkpoints track agent progress and are distinct from the job queue.

Core entities: User, Role, Session, VerificationToken, ResetToken, Account, Card, SecretReference, Statement, SourceDocument, ExtractionRun, Transaction, TransactionSplit, TransferMatch, MerchantRule, InstalmentPlan, InstalmentEntry, FinancialSnapshot, AgentRun, AgentThread, Finding, EvidenceReference, Scenario, Target, MemoryItem, ConsentRecord, ProviderProfile, Job, AuditEvent and BackupManifest.

Use UUIDs, UTC operational timestamps, date-only financial dates, owner_id on private records, indexed owner/date access paths and exact Numeric/Decimal amounts. Serialise money as decimal strings at API boundaries; frontend calculations cannot define financial truth. Raw source and corrected normalised records remain distinct. Store source files in encrypted protected volumes with database metadata; keys are outside database backups unless specifically exported in protected form.

PostgreSQL row-level security provides defence in depth for private tables alongside service authorisation. Runtime roles must not own tables, be superusers or have BYPASSRLS. Use transaction-local owner context and test pooled connection reuse. Workers and LangGraph persistence need equivalent ownership enforcement even where integration tables cannot use the same policy directly. Migrations run with a separate privileged role.

Vector search is not required for financial totals. Begin with scoped structured retrieval and full-text search. Add pgvector only if evaluation shows a need for semantic memory retrieval; preserve the same retention and ownership guarantees. No separate graph or vector server in the initial deployment.

## 7. Document processing and reconciliation

Use local PDF text/layout extraction as the first route, with a separately isolated OCR route for scanned pages. Candidate tools include pypdf/pikepdf and pdfplumber; OCRmyPDF/Tesseract can serve OCR after authorised decryption. Validate licences and redistribution terms before final dependency selection. Package required OCR language assets for English/Arabic processing; do not require model downloads at runtime.

File pipeline: quarantine → validate type/limits → decrypt → identify layout → extract → normalise → reconcile → review/commit. Set upload-size, page, memory, CPU and execution limits. Clean temporary decrypted copies on success/failure and startup recovery. Do not pass passwords on logged command lines. Parser/OCR processes run without network access and without broad file access.

Adapters expose detect, extract and validate methods with versioned fixtures. Bank layout changes must not silently succeed. Since no representative bank PDFs were supplied, specific bank support is not yet certified. Build representative synthetic fixtures, a generic fallback and an honest support matrix; require authorised redacted real-format fixtures before claiming a named bank is production-supported.

Reconciliation for a liability account uses a documented sign convention: closing liability = opening liability + purchases + fees + interest + advances − payments − refunds − other credits, adjusted only for statement-defined accounting. Instalment postings and conversions depend on their explicit source treatment. Never force a universal equation by duplicating principal or inventing entries. Compare source totals and extracted totals with a documented currency rounding tolerance; unreconciled differences remain visible.

Exact-file duplicates use owner-scoped content hashes. Statement identity uses account, period and source attributes. Repeated legitimate same-day/same-amount purchases are not automatically deleted. Overlapping statement transaction matches are reviewed conservatively. Importing a corrected statement creates a version/replacement workflow, not additive double-counting.

## 8. API and live interaction

Version routes under /api/v1. Groups: /auth, /users/me, /cards, /accounts, /statements, /imports, /transactions, /analytics, /instalments, /advisor/threads, /advisor/runs, /findings, /scenarios, /targets, /settings/llm, /backups and /admin. Define contracts through generated OpenAPI and typed frontend clients.

Long-running requests return 202 with a job/run identifier and status URL. Provide ownership-checked status, cancel, resume and SSE events. Event types include queued, stage_changed, tool_summary, finding_ready, clarification_required, completed and failed. Stream concise activity summaries, not hidden chain-of-thought or secret-bearing tool arguments. Support reconnect with event IDs and bounded replay. Never put access tokens in SSE URLs.

Mutations that can be retried accept idempotency keys. Use stable error codes, safe messages and correlation IDs. Pagination and server-side filtering apply to transactions. Optimistic concurrency protects corrections and user settings from silent overwrite.

## 9. Authentication, privacy and security

FastAPI is not a complete account system. Select a maintained compatible authentication/account library after a maintenance and security review; record the choice in an architecture decision. Use established password hashing and token primitives rather than custom cryptography. Acceptance requirements apply regardless of library.

Use Argon2id password hashes and opaque server-side sessions with HttpOnly cookies. Production uses HTTPS, Secure cookies, appropriate SameSite settings, CSRF protection and explicit allowed origins. Never persist bearer tokens in localStorage. Recommended distributed deployment uses a same-site frontend gateway routing /api to the independently hosted backend; document direct cross-origin credentials if supported and browser restrictions for truly cross-site deployments.

Verification/reset tokens are random, stored hashed, single-use and purpose-bound. Recommended expiry: verification 24 hours, reset 30 minutes. URLs use configured PUBLIC_APP_URL, never untrusted Host headers. Reset requests give non-enumerating responses, rate-limit abuse and revoke old sessions after completion. Email changes require verification and invalidate obsolete tokens. Administrators cannot see plaintext passwords, provider keys or statement secrets.

Use a maintained authenticated-encryption library for stored secrets. Key management includes persistent key IDs, rotation and backup recovery. Losing a server key must not silently destroy access without documented warning. Encrypting with a server-held key does not protect against an operator who controls that server; UI privacy is not a zero-knowledge guarantee.

User-configured LLM endpoints create an SSRF boundary: allow intended local model hosts through an explicit deployment policy, block metadata/control-plane targets and unsafe schemes, validate DNS/redirect behaviour and separate outbound credentials per configured origin. Do not simply prohibit all private IPs, since local models are a requirement.

Treat PDFs and model output as untrusted data. Sanitize rendered Markdown, prevent arbitrary links/actions, ignore document instructions and restrict tools. No financial content in default admin logs, exception payloads, email bodies or hosted telemetry. LangSmith or any cloud tracing is disabled by default; local redacted run summaries provide observability.

## 10. Modern UI specification

Use React, TypeScript, Vite, Tailwind CSS, customised shadcn/ui, TanStack Query/Table, React Hook Form/Zod and Recharts. Libraries are proposed implementation choices subject to compatible version verification. Financial computations remain backend-owned.

Visual direction: a polished financial workspace with a welcoming briefing page, restrained navy/teal accents, semantic warning colours, readable typography, tabular money alignment, coherent spacing and light/dark themes. Build design tokens and reusable components before proliferating screens. Avoid a generic grid of identical KPI cards or a chat window as the entire product.

| Screen | Required experience |
|---|---|
| Sign-in/registration | Clear validation, verification/resend flow, reset states and accessible password controls |
| Onboarding | Explain data location; optional AI connection test; card creation; first batch upload |
| Home briefing | Coverage/status header, prioritised findings, spending context, commitments and review action |
| Cards | Card list and detail; cycles, observed balances, statement history, instalments and masked settings |
| Statements/imports | Batch queue, progress, duplicate/missing statuses and review entry points |
| Statement review | Resizable PDF/evidence pane and editable extraction table; keyboard-friendly validation |
| Transactions | Server-side filters/search, category changes, splits, source drill-down and bulk operations |
| Analytics | Cross-card calendar trends, statement-cycle views and linked chart-to-transaction filters |
| Obligations | Known dues and instalment timeline; clear source date and projected/observed distinction |
| Advisor | Persistent conversations, context chips, streamed status, structured findings and evidence drawer |
| Scenarios/targets | Editable assumptions, calculated comparison and explicit acceptance |
| Settings | Profile, auto-lock, AI provider/consent, memories, backups and retention explanation |
| Admin | Users, SMTP, registration settings and redacted operational health only |

Every screen needs loading, empty, partial, error, locked and success states where relevant. Show last statement date and never imply live account status. Responsive tables can scroll or switch to detail cards without hiding financial meaning. Target WCAG 2.2 AA through keyboard access, focus order, contrast, labels, reduced motion and chart data alternatives. Charts use colour plus labels; amounts are selectable and legible. Self-host fonts/icons/assets, with no runtime CDN dependency.

### 10.1 Mandatory visual direction and references

Design an original, premium financial workspace: the operational clarity of Linear, financial information hierarchy inspired by Mercury, and approachable personal-finance storytelling inspired by Monarch. These are reference directions, not instructions to copy their branding or exact screens. Study product screenshots/demos on the public pages, not just marketing hero sections.

| Reference | URL | Study and apply | Do not reproduce |
|---|---|---|---|
| Linear | https://linear.app/ | Navigation hierarchy, compact toolbars, focused detail panels, typography and interaction consistency | Issue-tracker terminology, brand assets or a marketing landing page |
| Mercury | https://mercury.com/ | Account/transaction presentation, disciplined whitespace and legible financial values | Bank branding, money-transfer features or claims that we are a bank |
| Monarch | https://www.monarch.com/ | Personal spending context, understandable category visuals and goal presentation | Unrequested investment/net-worth modules or copied dashboard composition |
| shadcn/ui blocks | https://ui.shadcn.com/blocks | Accessible structural primitives, sidebar/table/form implementation patterns | An unchanged stock dashboard block as the final product |

References reviewed 29 September 2026. Their public content can change. The design requirements here remain authoritative. If screenshots are unavailable to the coding agent, it must say so, proceed from this specification and never claim visual inspection it did not perform. Do not require users to create reference-site accounts. Use original icons/compositions; no copied logos, proprietary illustrations or bundled reference screenshots in the app.

### 10.2 Design tokens and composition

The following is the selected starting direction, not a menu of unrelated styles. Implement it consistently, adjusting colour pairs only as necessary to meet measured contrast.

| Token | Light theme | Dark theme / behaviour |
|---|---|---|
| Canvas | #F6F7F9 | #10151D |
| Main surface | #FFFFFF | #18212C |
| Secondary surface | #EEF2F6 | #202B38 |
| Primary text | #17212F | #F1F5F9 |
| Secondary text | #526174 | #B1BDCC |
| Borders | #DCE3EB | #354354 |
| Primary action | #0F766E with white label | #5EEAD4 with #10231F label |
| Focus | Visible 2px outline with offset | Theme-appropriate high contrast |
| Semantic states | Green/amber/red paired with words and icons | Independently tested text/background pairs |
| Typography | Self-hosted Inter or equivalent licensed sans; system fallback | Same metrics and hierarchy |
| Type scale | Page title 28–32px; section 18–20px; body 14–16px; metadata 12–13px | Money uses tabular numerals; key value 30–36px |
| Spacing | 4, 8, 12, 16, 24, 32, 48px | Reuse tokens, avoid arbitrary per-screen spacing |
| Radius | Inputs/buttons 8px; panels 12px; prominent briefing 16px | No pill-shaped everything |
| Elevation | Border-first surfaces; subtle shadow only for floating/raised elements | No heavy shadows around every card |
| Motion | 120–200ms for hover/drawer transitions | Respect reduced motion; no perpetual decorative animation |

Use a 12-column content grid on wide screens with 24px gutters, 28–32px page padding and a maximum reading canvas near 1440px. Desktop sidebar is approximately 232px; collapsed rail approximately 72px. Top utility bar is approximately 64px. Dense review/table screens may use the available width rather than the reading limit. At 1024–1279px reduce gutters and collapse supporting columns; below 768px use a single column and an accessible navigation drawer. Padding becomes 16px on phones. These are guides, not hard widths that cause overflow.

Navigation groups: Overview; Money (Cards & accounts, Transactions, Statements, Obligations); Intelligence (Advisor, Scenarios); Settings. Administration is a separate permission-controlled destination. Avoid displaying every possible action in the sidebar. Provide a compact command/search control for navigation, with keyboard shortcut hints where implemented.

### 10.3 Screen blueprints

**Overview / monthly briefing**

- Header: month and scope selector on the left; quiet data-coverage indicator; one primary Upload statements action and a secondary Run review action. Show last statement date without suggesting live balances.
- First content row: an eight-column financial briefing and four-column obligations panel. The briefing leads with a specific takeaway, two supporting sentences, and at most three ranked findings. Include evidence and Explore action links. This is not an oversized welcome banner.
- Obligations panel: dated list of upcoming known card dues and instalments, with source-date labels. Unknown values are not zero. Use a compact timeline, not another large generic chart.
- Next row: a wide spending trend plus a narrower category breakdown. Add a restrained strip of at most three key values such as net spending, fees and known monthly instalment commitments. Each has a defined period, comparison and caveat.
- Lower content: ranked opportunities or recent transactions with a clear View all link. Do not repeat the same totals in multiple widgets.
- Phone order: header, main briefing, key values, obligations, trend, categories, recent activity. A large decorative card illustration must never push useful information below the fold.

**Cards and account detail**

Use a compact list/grid with bank/card alias, masked last digits, source date and observed amount. Modest card accents identify accounts; do not create a wall of photorealistic credit cards. Selecting a card opens a detail page with Overview, Statements, Transactions and Instalments tabs. Shared liability must be labelled at account level. Due date and statement period receive stronger hierarchy than decorative branding.

**Transactions**

Toolbar: search, date range, account filter, category filter and More filters. Show removable active-filter chips and a clear reset. Table: date, merchant/description, category, card, type and right-aligned amount. Keep a sticky header, approximately 48–56px rows, subtle dividers and keyboard-accessible selection. Bulk actions appear only after selection. Clicking a row opens a 400–480px evidence/detail drawer on wide screens, full screen on phones. Keep the underlying filters and scroll position. Preserve Arabic strings with appropriate text direction without changing the English UI.

**Statement review**

Header shows filename, period, account, reconciliation status and remaining issue count. Desktop uses resizable source PDF and extraction panes, initially near 45/55. Selecting a transaction highlights its source region where coordinates are available, otherwise navigates to its source page. Use Previous issue / Next issue controls, inline correction validation, and a sticky footer explaining whether commit is possible. On phones switch between Source and Extracted data tabs; never squeeze both panes side by side. Visible totals discrepancy must remain present until resolved or explicitly accepted.

**Advisor**

Combine a compact conversation list with the working conversation and a collapsible evidence panel. Responses use structured finding cards embedded in readable prose, with expandable assumptions and sources. Composer has selected period/card context chips, attach-context controls, multiline input, Send and Stop states. Suggested questions are contextually useful, such as "What changed this month?" rather than filler greetings. While running, show a short stage label and collapsible completed activity list; never expose hidden reasoning. Persist interruption/error state and offer Retry. On phones conversations and evidence open in separate sheets; the composer remains usable above the keyboard.

**Scenarios**

Two-column desktop layout: editable assumptions on the left; computed baseline-versus-proposal on the right. A slider, if used, also has an exact numeric input. Always display calculation period, affected category and source scope. Provide debounced recalculation or an explicit Calculate action and a loading indicator; never imply client-side estimated numbers are confirmed results. Accept target is distinct from running the calculation.

**Import queue**

A restrained drop zone above per-file rows, not a full-page empty upload box. Each row shows filename, detected card/period, progress stage and one relevant next action. Wrong-password entry is scoped to that file/card. Provide batch summary counts and an easy path to the next item requiring review. Duplicate is a distinct neutral result, not a generic error.

**Settings and administration**

Use section navigation, explanatory labels and clear form groupings. LLM setup is a guided connection form: type, endpoint, model, secret, Test connection, capability results, sharing scope and Save. Advanced options are collapsed. Never expose backend jargon such as checkpoint or RLS in routine product flows. Administration uses the same design language but only operational metadata.

**Authentication and onboarding**

Restrained, centred form with comfortable field spacing and a compact original brand treatment. On large screens an optional secondary panel explains local storage and the AI review experience; no stock finance photograph. On mobile the form takes priority. Verification, resend cooldown, invalid/expired reset and provider-unavailable states must be deliberately designed.

### 10.4 Component and interaction requirements

Implement reusable AppShell, PageHeader, ScopeSelector, CoverageIndicator, BriefingPanel, FindingCard, EvidenceDrawer, MoneyValue, ComparisonDelta, AccountBadge, TransactionTable, ImportStatusRow, EmptyState, ErrorState, AgentActivity and ScenarioComparison components. Names are suggestions; shared behaviour is mandatory.

A FindingCard has severity label, specific title, compact explanation, quantified effect only when supported, evidence count and at most two primary visible actions. Secondary actions belong in a menu. Amount colour is semantic: a higher spend is not automatically good; a refund is not salary. An unknown amount renders as Unknown, not 0.00. Charts use a consistent category-to-colour mapping, sensible axis labels, unclipped tooltips and an accessible table alternative. Avoid 3D charts, gauges without meaning, decorative sparklines and pie charts with many unreadable slices.

Empty states explain the next useful action. Skeletons match the final layout to reduce shift. Partial states show which data is missing. Errors offer actionable recovery. Dirty forms warn before discarding edits. Dialogs restore focus; destructive actions have explicit confirmation. Minimum mobile touch targets should be 44px where practical; do not rely on hover alone. All visible interactive controls must work or be explicitly unavailable with an explanation.

### 10.5 Mandatory visual development gate

Visual quality is a delivery requirement independent of compilation and backend correctness.

1. Before expanding all screens, write docs/ui-design-direction.md summarising references, tokens, layout hierarchy and original design choices. Create a reusable component preview route restricted to development.
2. Implement three high-fidelity representative screens first: Overview, Transactions with evidence drawer, and Advisor with structured findings. Use internally consistent labelled synthetic fixtures in a development-only preview. Include a light and dark treatment.
3. Render the actual running interface and inspect screenshots at 1440x900, 1024x768 and 390x844. Do not claim review based solely on JSX inspection or a passing browser assertion. If browser/screenshot tools are unavailable, explicitly mark visual review pending.
4. Review hierarchy, alignment, density, typography, contrast, real text wrapping, chart readability, drawer usability and responsive navigation. Fix observed defects before copying the design to remaining pages. This is a required self-review checkpoint, not a requirement to stop and wait for user approval.
5. Extend the same components to Statement review, Cards and Settings, then inspect their screenshots and key states. Test browser zoom at 200% and keyboard-only flows. Wide data tables may scroll in their own region; the entire page must not overflow horizontally.
6. Capture before/after screenshots when correcting a weak design. Deliver a short UI QA report with screenshot paths, viewport/state coverage, known issues and the fixes made. Functional browser tests do not substitute for this report.

Use the following review rubric, scored 0–2 per item: clear hierarchy; coherent spacing; typography/number legibility; distinctive but restrained composition; purposeful chart design; informative states; consistent controls; responsive behaviour; accessible interaction; fully working drill-downs. Target at least 18/20 with no zero. A self-score is a checklist, not independent proof of quality: screenshot evidence and absence of clipping/contrast/interaction defects are the actual release gate.

Reject these outcomes: unchanged stock dashboard template, a grid of equal-sized cards everywhere, giant empty welcome banner, blue/purple gradient decoration on every panel, excessive glass effects, tiny low-contrast text, charts populated with unexplained demo values, generic chat bubbles without evidence, orphaned buttons, raw browser alerts, or a desktop layout merely shrunk onto mobile. Do not replace a functional product screen with a marketing landing page.


## 11. Retention, backup and restore

Default analytics covers the latest twelve months. Daily retention maintenance applies an eighteen-calendar-month cutoff using a documented financial-date basis. Purge transactions, source files, extraction text, evidence-bearing caches, embeddings if any, agent checkpoints and derived personal narratives that retain expired details. Mixed-period documents may need removal of the entire original file while retaining in-window normalised rows with a Source expired label.

Preserve only minimal active instalment obligation metadata and opening balances needed for continuity, rather than retaining expired itemised spending under the label memory. Mark historical provenance unavailable after expiry. Pending disputed imports get a bounded handling policy; they cannot defeat retention indefinitely. Restores immediately reapply retention before making restored data available.

User backups are owner-scoped encrypted archives with authenticated encryption, a versioned manifest and explicit restore validation. Default excludes provider keys and saved PDF passwords; user can explicitly include them under stronger confirmation and encryption. Restore stages and validates entries, enforces ownership, prevents path traversal and detects duplicates before committing. Corrupt archives leave existing data unchanged. Existing downloaded backups cannot be retroactively purged; state this in backup settings. Installation backups are a separate operator responsibility and contain sensitive data.

## 12. Docker and operations

Compose services: web/gateway, API, document worker, agent worker and PostgreSQL. API and workers may share one backend image with separate entrypoints. Persist database, protected document store and required application keys. Do not expose PostgreSQL publicly by default. Run non-root, provide health/readiness probes, resource/concurrency controls, restart policies and graceful shutdown.

Include .env.example with descriptions and no real secrets. A migration step completes before readiness. Document localhost versus container-host model URLs and remote frontend/backend configuration. Development may download dependencies; runtime assets must be self-contained. A complete air-gapped distributable image bundle/installer remains later work. Email verification/reset requires SMTP/network connectivity and must not be falsely described as available offline.

No fixed hardware requirement is imposed. Measure representative import/review performance and expose concurrency controls. Local LLM hosting, model weights and GPU sizing remain outside this project.

## 13. Delivery sequence and completion gates

| Milestone | Deliverable | Exit gate |
|---|---|---|
| 1. Foundation | Repository, Docker, schema, authentication, isolation, UI design system | Two-user access tests, verification/reset and responsive shell work |
| 2. Financial vertical slice | Cards, encrypted PDFs, extraction/review, ledger, basic analytics | Reconciled synthetic fixtures, no duplicates/double-counting |
| 3. Early AI vertical slice | User local endpoint, scoped tools, one evidence-backed investigation | Real configured model tool call produces a validated finding |
| 4. Deep intelligence | Bounded delegation, risk/scenario roles, monthly briefing, memory | Replay/resume, evidence checks and model-failure tests pass |
| 5. Product completion | Full screens, bank/manual flows, instalments, backup/purge, admin | End-to-end acceptance suite and visual review pass |
| 6. Hardening | Security review, parser support matrix, documentation, packaging checks | No mandatory external AI/telemetry; documented known limits |

Build real agent functionality early; do not spend the whole project producing a dashboard with a mocked advisor. No calendar estimate is imposed before fixture availability and implementation velocity are known.

## 14. Acceptance criteria

1. User A cannot access user B's rows, PDFs, event streams, backups, checkpoint states or secrets by guessing IDs; admin UI cannot view them either.
2. Email verification is required; reset URLs are complete, expire, reject reuse and revoke sessions. Idle lock is server-enforced.
3. One user can register ten active cards; an eleventh is rejected clearly. Shared-account statements do not duplicate balances.
4. Password-protected statements process locally without exposing passwords in prompts/logs. Wrong passwords produce recoverable per-file errors.
5. Verified imports match source balances/totals under documented rules. Ambiguous extraction is visibly reviewed, never silently fabricated.
6. Reimporting the same file and retrying a crashed worker do not duplicate financial records or briefings.
7. Card purchases plus a matching bank payment count as one spending event. Transfers, refunds, cashback and overpayments retain correct semantics.
8. A known AED 6,000 twelve-part plan shows the original purchase once and AED 500 monthly commitments, with adjustments when terms differ.
9. Partial months and missing statements are visible; the advisor does not claim complete coverage.
10. With AI disabled and external networking blocked, supported-format import and basic analytics still work for an already verified account.
11. With a configured capable local LLM, the advisor invokes tools, investigates a change and produces findings linked to real authorised evidence.
12. External payload tests prove passwords, credentials and unnecessary identifiers are removed; no silent external fallback occurs.
13. A complex monthly review delegates selectively, respects limits, can cancel/resume and reports provider failure honestly.
14. Numerical recommendations match deterministic scenario outputs. Missing income prevents definitive affordability statements.
15. Correcting a category updates totals and invalidates affected findings; confirmed correction rules apply to subsequent imports.
16. Purge removes expired derived information as well as ledger rows; active minimal instalment continuity survives. Restore reapplies cutoff.
17. User backup restore handles valid, wrong-password, corrupt and duplicate archives without cross-user leakage or partial corruption.
18. Main flows work on desktop and narrow screens with keyboard navigation, readable contrast and non-colour-only chart meaning.
19. Compose starts from documented configuration; frontend/backend can be separately addressed; assets work without runtime CDNs.
20. A support matrix distinguishes synthetic coverage from validated real bank formats. No untested bank is advertised as supported.

Testing layers: deterministic domain tests, PostgreSQL integration/isolation tests, parser golden fixtures, agent contract/adversarial evaluations, Playwright end-to-end and visual/accessibility checks. Include malicious PDF instructions, fabricated evidence references, model timeouts, rate limits, ambiguous categories and insufficient-history cases. Deterministic mocked-provider tests support CI; at least one real user-configured local-model smoke test is needed before claiming integration success.

## 15. Implementation handover and decisions

Confirmed architecture: Python-first, FastAPI, PostgreSQL, LangChain/LangGraph/Deep Agents, modern React UI, Docker. Recommended defaults to implement/document: cookie sessions, PostgreSQL durable jobs, conservative agent limits, encrypted protected files, user backup secret exclusion and same-site gateway for distributed deployment.

The coding agent must resolve library versions, maintained authentication package, parser licences and exact queue integration from current primary documentation, recording choices in architecture decision records. Real UAE bank fixture coverage and a working local-model endpoint are validation inputs, not reasons to pretend a mocked integration is production-ready. No model name or bank list is hardcoded as user-approved.

## 16. Reference documentation

Reviewed 29 September 2026. These support framework capabilities; product requirements and implementation defaults above are project design decisions.

- [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview): agent harness, controlled tools, context and delegation.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence): persistent execution and thread state.
- [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/): security integration foundations, not a complete account-management implementation.
- [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html): row policies and privileged-role considerations.
- [SQLAlchemy types](https://docs.sqlalchemy.org/en/20/core/type_basics.html): numeric data representation.
- [OCRmyPDF security](https://ocrmypdf.readthedocs.io/en/latest/pdfsecurity.html): PDF processing and encryption considerations.
- [shadcn/ui components](https://ui.shadcn.com/docs/components): UI component foundation.

