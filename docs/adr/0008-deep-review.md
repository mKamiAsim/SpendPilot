# ADR 0008: Deep review checkpoints

Date: 29 September 2026

## Decision

A monthly review is a checkpointed workflow on the agent worker. Each step commits before the next one starts. Cancel and resume keep the step. Resume checks consent again. A second run of a published review does not insert another briefing. Accepting a target updates that row. It does not insert a second accepted target.

Specialists are the behaviour and scenario roles. They are roles inside one process, not extra servers. A short question does not call them and does not build the monthly graph. A monthly review calls those two roles together, which is the parallel cap. Depth stops at 2. The call counter stops at 40. The deadline is 10 minutes from creation. Obligations is a role and is not on the monthly path. Category corrections and other mutations stay staged until the user accepts them. That acceptance marks the affected briefing, finding, and scenario stale.

`review_checkpoints` stays the step log. It has an owner column and forced row-level security. LangGraph state is a second pair of tables, `langgraph_checkpoints` and `langgraph_checkpoint_writes`. The migrator role cannot create a schema, so these tables are in `public`. Every row has `owner_id` and forced row-level security on `app.owner_id`. `OwnerCheckpointSaver` also refuses a config whose `owner_id` does not match that session setting, so one user cannot read another user's checkpoint rows.

The monthly path builds a Deep Agents graph with shell, code execution, host filesystem, and open-web tools excluded. The builder rejects a request to turn those tools on, and the in-process model refuses to bind them. The graph uses in-state files only, with read and write denied. The general-purpose subagent is off. Behaviour and scenario are the only specialist roles, and they have no tools of their own. Numeric claims still come from the calculation ids. A missing income total rejects an affordability claim.

`SPENDPILOT_PROVIDER=fake` runs the same calculations without a socket. Configured mode checks the saved endpoint first. It does not switch to the fake provider or a hosted model. Document assistance stays off, so page text and OCR text are not placed in a model payload.

## Unverified

`MODEL_SMOKE_URL` is empty. The live smoke test stays skipped. A fake-provider run is not acceptance of live tool-calling or of a live deep review.
