"""Owner-scoped LangGraph checkpoint tables.

The migrator role can create tables and cannot create schemas. These tables
are the LangGraph store: each row has an owner and forced row-level security.
"""

from alembic import op

revision = "0006_langgraph"
down_revision = "0005_product"
branch_labels = None
depends_on = None

SQL = r"""
CREATE TABLE langgraph_checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    review_id UUID REFERENCES reviews (id) ON DELETE CASCADE,
    parent_checkpoint_id TEXT,
    checkpoint_type TEXT NOT NULL,
    checkpoint_blob BYTEA NOT NULL,
    metadata_type TEXT NOT NULL,
    metadata_blob BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE langgraph_checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    write_idx INTEGER NOT NULL,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    value_type TEXT NOT NULL,
    value_blob BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx)
);

ALTER TABLE langgraph_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE langgraph_checkpoints FORCE ROW LEVEL SECURITY;
ALTER TABLE langgraph_checkpoint_writes ENABLE ROW LEVEL SECURITY;
ALTER TABLE langgraph_checkpoint_writes FORCE ROW LEVEL SECURITY;

CREATE POLICY langgraph_checkpoints_app ON langgraph_checkpoints
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY langgraph_checkpoints_migrator ON langgraph_checkpoints
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

CREATE POLICY langgraph_checkpoint_writes_app ON langgraph_checkpoint_writes
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);
CREATE POLICY langgraph_checkpoint_writes_migrator ON langgraph_checkpoint_writes
    FOR ALL TO spendpilot_migrator USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON langgraph_checkpoints, langgraph_checkpoint_writes TO spendpilot_app;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(SQL)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(
        "DROP TABLE IF EXISTS langgraph_checkpoint_writes, langgraph_checkpoints CASCADE;"
    )
