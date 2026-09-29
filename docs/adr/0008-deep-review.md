# ADR 0008: Deep review checkpoints

Date: 29 September 2026

## Decision

A monthly review is a checkpointed workflow on the agent worker. Each step commits before the next one starts. Cancel and resume keep the step. Resume checks consent again. A second run of a published review does not insert another briefing. Accepting a target updates that row. It does not insert a second accepted target.

Specialists are the behaviour and scenario roles. A short question does not call them. A monthly review calls those two roles together, which is the parallel cap. Depth stops at 2. The call counter stops at 40. The deadline is 10 minutes from creation. Obligations is a role and is not on the monthly path.

Checkpoints live in `review_checkpoints` with the owner column and forced row-level security. LangGraph and Deep Agents stay uninstalled. Their default harness can expose shell, filesystem, and web tools, and their checkpoint tables do not take this schema's row-level policy. Numeric claims come from calculation ids. A missing income total rejects an affordability claim. Category corrections stay staged until the user accepts them, and that acceptance marks the affected briefing, finding, and scenario stale.

`SPENDPILOT_PROVIDER=fake` runs the same calculations without a socket. Configured mode checks the saved endpoint first. It does not switch to the fake provider or a hosted model.

## Unverified

`MODEL_SMOKE_URL` is empty. The live smoke test stays skipped. A fake-provider run is not acceptance of live tool-calling or of a live deep review.
