"""Cards, statement imports, and posted transactions."""

from alembic import op

revision = "0002_ledger"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

SQL = r"""
CREATE TABLE card_accounts (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    last4 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT card_accounts_last4_check CHECK (last4 ~ '^[0-9]{4}$'),
    CONSTRAINT card_accounts_alias_check CHECK (char_length(alias) BETWEEN 1 AND 80),
    UNIQUE (owner_id, last4)
);

CREATE TABLE cards (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES card_accounts (id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    last4 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    password_ciphertext BYTEA,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cards_last4_check CHECK (last4 ~ '^[0-9]{4}$'),
    CONSTRAINT cards_alias_check CHECK (char_length(alias) BETWEEN 1 AND 80),
    CONSTRAINT cards_status_check CHECK (status IN ('active', 'closed')),
    UNIQUE (owner_id, last4)
);
CREATE INDEX cards_owner_status_idx ON cards (owner_id, status);

CREATE TABLE import_batches (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX import_batches_owner_key_idx
    ON import_batches (owner_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE source_documents (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES import_batches (id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL,
    failure_code TEXT,
    failure_message TEXT,
    import_password_ciphertext BYTEA,
    extracted_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT source_documents_status_check CHECK (
        status IN ('queued', 'committed', 'needs_review', 'duplicate', 'failed')
    )
);
CREATE UNIQUE INDEX source_documents_owner_hash_idx
    ON source_documents (owner_id, content_hash)
    WHERE status IN ('committed', 'needs_review');

CREATE TABLE statements (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    document_id UUID NOT NULL UNIQUE REFERENCES source_documents (id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES card_accounts (id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    opening_liability NUMERIC(14, 2) NOT NULL,
    closing_liability NUMERIC(14, 2) NOT NULL,
    computed_closing NUMERIC(14, 2) NOT NULL,
    difference NUMERIC(14, 2) NOT NULL,
    reconciliation TEXT NOT NULL,
    accept_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT statements_reconciliation_check CHECK (
        reconciliation IN ('verified', 'accepted_discrepancy')
    )
);

CREATE TABLE posted_transactions (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    statement_id UUID NOT NULL REFERENCES statements (id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards (id) ON DELETE SET NULL,
    line_number INTEGER NOT NULL,
    posted_on DATE NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    source_page INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT posted_transactions_amount_check CHECK (amount > 0),
    CONSTRAINT posted_transactions_type_check CHECK (
        entry_type IN (
            'purchase', 'payment', 'refund', 'fee', 'interest',
            'transfer', 'cash_withdrawal', 'cashback', 'unknown'
        )
    ),
    UNIQUE (statement_id, line_number)
);
CREATE INDEX posted_transactions_owner_date_idx ON posted_transactions (owner_id, posted_on);

CREATE TABLE cash_entries (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    posted_on DATE NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cash_entries_amount_check CHECK (amount > 0)
);

ALTER TABLE card_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_accounts FORCE ROW LEVEL SECURITY;
ALTER TABLE cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE cards FORCE ROW LEVEL SECURITY;
ALTER TABLE import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_batches FORCE ROW LEVEL SECURITY;
ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE statements ENABLE ROW LEVEL SECURITY;
ALTER TABLE statements FORCE ROW LEVEL SECURITY;
ALTER TABLE posted_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE posted_transactions FORCE ROW LEVEL SECURITY;
ALTER TABLE cash_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_entries FORCE ROW LEVEL SECURITY;

CREATE POLICY card_accounts_app ON card_accounts
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY card_accounts_migrator ON card_accounts
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY cards_app ON cards
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY cards_migrator ON cards
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY import_batches_app ON import_batches
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY import_batches_migrator ON import_batches
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY source_documents_app ON source_documents
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY source_documents_migrator ON source_documents
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY statements_app ON statements
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY statements_migrator ON statements
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY posted_transactions_app ON posted_transactions
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY posted_transactions_migrator ON posted_transactions
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY cash_entries_app ON cash_entries
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY cash_entries_migrator ON cash_entries
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    card_accounts, cards, import_batches, source_documents,
    statements, posted_transactions, cash_entries
    TO spendpilot_app;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(SQL)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        DROP TABLE IF EXISTS cash_entries, posted_transactions, statements,
            source_documents, import_batches, cards, card_accounts CASCADE;
        """
    )
