"""Monthly reviews, memories, scenarios, and staged targets."""

from alembic import op

revision = "0004_review"
down_revision = "0003_agent"
branch_labels = None
depends_on = None

SQL = r"""
CREATE TABLE reviews (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    snapshot_id UUID REFERENCES snapshots (id) ON DELETE CASCADE,
    snapshot_hash TEXT,
    duplicate_of UUID REFERENCES reviews (id) ON DELETE SET NULL,
    idempotency_key TEXT,
    status TEXT NOT NULL,
    provider_mode TEXT NOT NULL,
    step TEXT NOT NULL DEFAULT 'authorise',
    call_count INTEGER NOT NULL DEFAULT 0,
    deadline_at TIMESTAMPTZ NOT NULL,
    consent_version INTEGER,
    failure_code TEXT,
    failure_message TEXT,
    activity JSONB NOT NULL DEFAULT '[]'::jsonb,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT reviews_status_check CHECK (
        status IN ('queued', 'running', 'paused', 'cancelled', 'published', 'failed', 'linked')
    ),
    CONSTRAINT reviews_provider_check CHECK (provider_mode IN ('configured', 'fake'))
);
CREATE UNIQUE INDEX reviews_owner_key_idx
    ON reviews (owner_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX reviews_owner_hash_idx
    ON reviews (owner_id, snapshot_hash)
    WHERE status = 'published' AND snapshot_hash IS NOT NULL;

CREATE TABLE review_checkpoints (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    review_id UUID NOT NULL REFERENCES reviews (id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (review_id, step)
);

CREATE TABLE briefings (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    review_id UUID NOT NULL UNIQUE REFERENCES reviews (id) ON DELETE CASCADE,
    snapshot_id UUID NOT NULL REFERENCES snapshots (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    explanation TEXT NOT NULL,
    stale BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memories (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT memories_kind_check CHECK (kind IN ('confirmed_preference', 'hypothesis')),
    CONSTRAINT memories_body_check CHECK (char_length(body) BETWEEN 1 AND 500)
);

CREATE TABLE scenarios (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    review_id UUID REFERENCES reviews (id) ON DELETE CASCADE,
    snapshot_id UUID REFERENCES snapshots (id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    baseline TEXT NOT NULL,
    reduction TEXT NOT NULL,
    proposed TEXT NOT NULL,
    calculation_id TEXT NOT NULL,
    income_total TEXT NOT NULL,
    affordability_amount TEXT,
    affordability_blocked BOOLEAN NOT NULL,
    stale BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE targets (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    review_id UUID REFERENCES reviews (id) ON DELETE CASCADE,
    scenario_id UUID REFERENCES scenarios (id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    baseline TEXT NOT NULL,
    reduction TEXT NOT NULL,
    proposed TEXT NOT NULL,
    calculation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at TIMESTAMPTZ,
    CONSTRAINT targets_status_check CHECK (status IN ('staged', 'accepted'))
);
CREATE UNIQUE INDEX targets_review_idx ON targets (review_id) WHERE review_id IS NOT NULL;
CREATE UNIQUE INDEX targets_owner_key_idx
    ON targets (owner_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE category_corrections (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES posted_transactions (id) ON DELETE CASCADE,
    original_category TEXT NOT NULL,
    proposed_category TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at TIMESTAMPTZ,
    CONSTRAINT category_corrections_status_check CHECK (status IN ('staged', 'accepted', 'rejected'))
);

ALTER TABLE findings ALTER COLUMN investigation_id DROP NOT NULL;
ALTER TABLE findings ADD COLUMN review_id UUID REFERENCES reviews (id) ON DELETE CASCADE;
ALTER TABLE findings ADD COLUMN stale BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE findings ADD CONSTRAINT findings_one_parent CHECK (
    (investigation_id IS NOT NULL)::integer + (review_id IS NOT NULL)::integer = 1
);
CREATE UNIQUE INDEX findings_review_id_idx ON findings (review_id) WHERE review_id IS NOT NULL;

ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews FORCE ROW LEVEL SECURITY;
ALTER TABLE review_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_checkpoints FORCE ROW LEVEL SECURITY;
ALTER TABLE briefings ENABLE ROW LEVEL SECURITY;
ALTER TABLE briefings FORCE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories FORCE ROW LEVEL SECURITY;
ALTER TABLE scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE scenarios FORCE ROW LEVEL SECURITY;
ALTER TABLE targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE targets FORCE ROW LEVEL SECURITY;
ALTER TABLE category_corrections ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_corrections FORCE ROW LEVEL SECURITY;

CREATE POLICY reviews_app ON reviews
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY reviews_migrator ON reviews FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY review_checkpoints_app ON review_checkpoints
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY review_checkpoints_migrator ON review_checkpoints
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY briefings_app ON briefings
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY briefings_migrator ON briefings FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY memories_app ON memories
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY memories_migrator ON memories FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY scenarios_app ON scenarios
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY scenarios_migrator ON scenarios FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY targets_app ON targets
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY targets_migrator ON targets FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY category_corrections_app ON category_corrections
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY category_corrections_migrator ON category_corrections
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    reviews, review_checkpoints, briefings, memories, scenarios, targets, category_corrections
    TO spendpilot_app;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(SQL)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        ALTER TABLE findings DROP CONSTRAINT IF EXISTS findings_one_parent;
        ALTER TABLE findings DROP COLUMN IF EXISTS stale;
        ALTER TABLE findings DROP COLUMN IF EXISTS review_id;
        ALTER TABLE findings ALTER COLUMN investigation_id SET NOT NULL;
        DROP TABLE IF EXISTS category_corrections, targets, scenarios, memories,
            briefings, review_checkpoints, reviews CASCADE;
        """
    )
