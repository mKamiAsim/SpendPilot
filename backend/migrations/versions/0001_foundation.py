"""Foundation schema, owner column, and runtime role policies."""

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None

SQL = r"""
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username CITEXT NOT NULL UNIQUE,
    email CITEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    email_verified_at TIMESTAMPTZ,
    is_disabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT users_role_check CHECK (role IN ('member', 'admin'))
);

CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);
CREATE INDEX sessions_user_id_idx ON sessions (user_id);

CREATE TABLE email_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT email_tokens_purpose_check CHECK (purpose IN ('verification', 'reset'))
);
CREATE INDEX email_tokens_user_purpose_idx ON email_tokens (user_id, purpose);

CREATE TABLE private_records (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT private_records_label_check CHECK (char_length(label) BETWEEN 1 AND 200)
);
CREATE INDEX private_records_owner_idx ON private_records (owner_id);

CREATE TABLE app_settings (
    id SMALLINT PRIMARY KEY DEFAULT 1,
    registration_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT app_settings_singleton CHECK (id = 1)
);
INSERT INTO app_settings (id, registration_enabled) VALUES (1, TRUE);

CREATE TABLE auth_attempts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action TEXT NOT NULL,
    subject TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX auth_attempts_lookup_idx ON auth_attempts (action, subject, attempted_at);

CREATE TABLE mail_outbox (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE FUNCTION users_guard() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.role IS DISTINCT FROM OLD.role THEN
        IF current_user = 'spendpilot_app'
           AND current_setting('app.actor_role', true) IS DISTINCT FROM 'admin' THEN
            RAISE EXCEPTION 'role change requires an administrator';
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.email_verified_at IS DISTINCT FROM OLD.email_verified_at THEN
        IF current_user = 'spendpilot_app'
           AND COALESCE(current_setting('app.token_hash', true), '') = '' THEN
            RAISE EXCEPTION 'email verification requires a token';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER users_guard BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION users_guard();

CREATE FUNCTION app_settings_guard() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF current_user = 'spendpilot_app'
       AND current_setting('app.actor_role', true) IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'registration settings require an administrator';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER app_settings_guard BEFORE UPDATE ON app_settings
FOR EACH ROW EXECUTE FUNCTION app_settings_guard();

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE email_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_tokens FORCE ROW LEVEL SECURITY;
ALTER TABLE private_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE private_records FORCE ROW LEVEL SECURITY;
ALTER TABLE mail_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE mail_outbox FORCE ROW LEVEL SECURITY;

CREATE POLICY users_select ON users
    FOR SELECT TO spendpilot_app
    USING (
        id = NULLIF(current_setting('app.owner_id', true), '')::uuid
        OR (
            current_setting('app.login_name', true) <> ''
            AND (
                username = current_setting('app.login_name', true)
                OR email = current_setting('app.login_name', true)
            )
        )
    );

CREATE POLICY users_insert ON users
    FOR INSERT TO spendpilot_app
    WITH CHECK (role = 'member');

CREATE POLICY users_update ON users
    FOR UPDATE TO spendpilot_app
    USING (id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.owner_id', true), '')::uuid);

CREATE POLICY users_migrator ON users
    FOR ALL TO spendpilot_migrator
    USING (true)
    WITH CHECK (true);

CREATE POLICY sessions_app ON sessions
    FOR ALL TO spendpilot_app
    USING (
        user_id = NULLIF(current_setting('app.owner_id', true), '')::uuid
        OR (
            current_setting('app.session_token_hash', true) <> ''
            AND token_hash = current_setting('app.session_token_hash', true)
        )
    )
    WITH CHECK (user_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);

CREATE POLICY sessions_migrator ON sessions
    FOR ALL TO spendpilot_migrator
    USING (true)
    WITH CHECK (true);

CREATE POLICY email_tokens_app ON email_tokens
    FOR ALL TO spendpilot_app
    USING (
        user_id = NULLIF(current_setting('app.owner_id', true), '')::uuid
        OR (
            current_setting('app.token_hash', true) <> ''
            AND token_hash = current_setting('app.token_hash', true)
        )
    )
    WITH CHECK (user_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);

CREATE POLICY email_tokens_migrator ON email_tokens
    FOR ALL TO spendpilot_migrator
    USING (true)
    WITH CHECK (true);

CREATE POLICY private_records_app ON private_records
    FOR ALL TO spendpilot_app
    USING (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid)
    WITH CHECK (owner_id = NULLIF(current_setting('app.owner_id', true), '')::uuid);

CREATE POLICY private_records_migrator ON private_records
    FOR ALL TO spendpilot_migrator
    USING (true)
    WITH CHECK (true);

CREATE POLICY mail_outbox_insert ON mail_outbox
    FOR INSERT TO spendpilot_app
    WITH CHECK (true);

CREATE POLICY mail_outbox_migrator ON mail_outbox
    FOR ALL TO spendpilot_migrator
    USING (true)
    WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions, email_tokens, private_records TO spendpilot_app;
GRANT SELECT, UPDATE ON app_settings TO spendpilot_app;
GRANT SELECT, INSERT, DELETE ON auth_attempts TO spendpilot_app;
GRANT INSERT ON mail_outbox TO spendpilot_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO spendpilot_app;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mail_outbox, auth_attempts, private_records, email_tokens, sessions, app_settings, users CASCADE")
