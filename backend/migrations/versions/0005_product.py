"""Bank statements, instalments, categories, backups, and purge keys."""

from alembic import op

revision = "0005_product"
down_revision = "0004_review"
branch_labels = None
depends_on = None

SQL = r"""
ALTER TABLE statements ADD COLUMN kind TEXT NOT NULL DEFAULT 'card';
ALTER TABLE statements ADD COLUMN source_id UUID;
ALTER TABLE statements ALTER COLUMN document_id DROP NOT NULL;
ALTER TABLE statements ADD CONSTRAINT statements_kind_check CHECK (kind IN ('card', 'bank'));
CREATE UNIQUE INDEX statements_owner_source_idx
    ON statements (owner_id, source_id)
    WHERE source_id IS NOT NULL;

ALTER TABLE posted_transactions ADD COLUMN source_id UUID;
CREATE UNIQUE INDEX posted_transactions_owner_source_idx
    ON posted_transactions (owner_id, source_id)
    WHERE source_id IS NOT NULL;

ALTER TABLE cash_entries ADD COLUMN source_id UUID;
CREATE UNIQUE INDEX cash_entries_owner_source_idx
    ON cash_entries (owner_id, source_id)
    WHERE source_id IS NOT NULL;

ALTER TABLE memories ADD COLUMN source_id UUID;
CREATE UNIQUE INDEX memories_owner_source_idx
    ON memories (owner_id, source_id)
    WHERE source_id IS NOT NULL;

CREATE TABLE user_categories (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_categories_name_check CHECK (char_length(name) BETWEEN 1 AND 40),
    UNIQUE (owner_id, name)
);

CREATE TABLE category_rules (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, description)
);

CREATE TABLE instalment_plans (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    source_id UUID,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    principal NUMERIC(14, 2) NOT NULL,
    parts INTEGER NOT NULL,
    monthly_amount NUMERIC(14, 2) NOT NULL,
    posted_on DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT instalment_plans_principal_check CHECK (principal > 0),
    CONSTRAINT instalment_plans_parts_check CHECK (parts BETWEEN 2 AND 60),
    UNIQUE (owner_id, source_id)
);

CREATE TABLE instalment_repayments (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES instalment_plans (id) ON DELETE CASCADE,
    source_id UUID,
    posted_on DATE NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT instalment_repayments_amount_check CHECK (amount > 0)
);
CREATE UNIQUE INDEX instalment_repayments_owner_source_idx
    ON instalment_repayments (owner_id, source_id)
    WHERE source_id IS NOT NULL;

CREATE TABLE backups (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    ciphertext BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE user_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_categories FORCE ROW LEVEL SECURITY;
ALTER TABLE category_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_rules FORCE ROW LEVEL SECURITY;
ALTER TABLE instalment_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE instalment_plans FORCE ROW LEVEL SECURITY;
ALTER TABLE instalment_repayments ENABLE ROW LEVEL SECURITY;
ALTER TABLE instalment_repayments FORCE ROW LEVEL SECURITY;
ALTER TABLE backups ENABLE ROW LEVEL SECURITY;
ALTER TABLE backups FORCE ROW LEVEL SECURITY;
ALTER TABLE user_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_events FORCE ROW LEVEL SECURITY;

CREATE POLICY user_categories_app ON user_categories
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY user_categories_migrator ON user_categories
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY category_rules_app ON category_rules
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY category_rules_migrator ON category_rules
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY instalment_plans_app ON instalment_plans
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY instalment_plans_migrator ON instalment_plans
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY instalment_repayments_app ON instalment_repayments
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY instalment_repayments_migrator ON instalment_repayments
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY backups_app ON backups
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY backups_migrator ON backups
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY user_events_app ON user_events
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY user_events_migrator ON user_events
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    user_categories, category_rules, instalment_plans, instalment_repayments, backups, user_events
    TO spendpilot_app;
GRANT USAGE, SELECT ON SEQUENCE user_events_id_seq TO spendpilot_app;

CREATE FUNCTION app_user_count() RETURNS bigint
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$ SELECT count(*) FROM users $$;
REVOKE ALL ON FUNCTION app_user_count() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_user_count() TO spendpilot_app;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(SQL)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        DROP TABLE IF EXISTS user_events, backups, instalment_repayments, instalment_plans,
            category_rules, user_categories CASCADE;
        ALTER TABLE statements DROP COLUMN IF EXISTS kind;
        ALTER TABLE statements DROP COLUMN IF EXISTS source_id;
        ALTER TABLE posted_transactions DROP COLUMN IF EXISTS source_id;
        ALTER TABLE cash_entries DROP COLUMN IF EXISTS source_id;
        ALTER TABLE memories DROP COLUMN IF EXISTS source_id;
        DROP FUNCTION IF EXISTS app_user_count();
        """
    )
