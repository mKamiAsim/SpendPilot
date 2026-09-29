"""Provider profile, frozen snapshots, and one published finding."""

from alembic import op

revision = "0003_agent"
down_revision = "0002_ledger"
branch_labels = None
depends_on = None

SQL = r"""
CREATE TABLE provider_profiles (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,
    model_name TEXT NOT NULL,
    api_key_ciphertext BYTEA,
    consent TEXT NOT NULL,
    document_assistance BOOLEAN NOT NULL DEFAULT false,
    consent_version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT provider_profiles_consent_check CHECK (
        consent IN ('none', 'summary', 'selected_transactions')
    ),
    CONSTRAINT provider_profiles_document_assistance_check CHECK (document_assistance = false),
    CONSTRAINT provider_profiles_endpoint_check CHECK (char_length(endpoint) BETWEEN 1 AND 300),
    CONSTRAINT provider_profiles_model_check CHECK (char_length(model_name) BETWEEN 1 AND 120)
);

CREATE TABLE snapshots (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    consent TEXT NOT NULL,
    consent_version INTEGER NOT NULL,
    body JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE investigations (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    snapshot_id UUID REFERENCES snapshots (id) ON DELETE CASCADE,
    idempotency_key TEXT,
    question TEXT NOT NULL,
    status TEXT NOT NULL,
    provider_mode TEXT NOT NULL,
    failure_code TEXT,
    failure_message TEXT,
    activity JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT investigations_status_check CHECK (
        status IN ('queued', 'published', 'failed')
    ),
    CONSTRAINT investigations_provider_check CHECK (provider_mode IN ('configured', 'fake'))
);
CREATE UNIQUE INDEX investigations_owner_key_idx
    ON investigations (owner_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE findings (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    investigation_id UUID NOT NULL UNIQUE REFERENCES investigations (id) ON DELETE CASCADE,
    snapshot_id UUID NOT NULL REFERENCES snapshots (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    explanation TEXT NOT NULL,
    severity TEXT NOT NULL,
    evidence_ids JSONB NOT NULL,
    calculation_id TEXT NOT NULL,
    amount TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT findings_severity_check CHECK (severity IN ('note', 'attention', 'watch'))
);

ALTER TABLE provider_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots FORCE ROW LEVEL SECURITY;
ALTER TABLE investigations ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigations FORCE ROW LEVEL SECURITY;
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings FORCE ROW LEVEL SECURITY;

CREATE POLICY provider_profiles_app ON provider_profiles
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY provider_profiles_migrator ON provider_profiles
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY snapshots_app ON snapshots
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY snapshots_migrator ON snapshots
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY investigations_app ON investigations
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY investigations_migrator ON investigations
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY findings_app ON findings
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY findings_migrator ON findings
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    provider_profiles, snapshots, investigations, findings
    TO spendpilot_app;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(SQL)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(
        "DROP TABLE IF EXISTS findings, investigations, snapshots, provider_profiles CASCADE;"
    )
