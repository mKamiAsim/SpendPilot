from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.security import hash_password
from app.identity.service import normalize_email, normalize_username, validate_password


def main() -> None:
    settings = get_settings()
    username = settings.bootstrap_admin_username
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password
    if not username or not email or not password:
        print(
            "Set BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_EMAIL, and "
            "BOOTSTRAP_ADMIN_PASSWORD for the one-time administrator.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    username = normalize_username(username)
    email = normalize_email(email)
    validate_password(password, username)
    engine = create_engine(settings.database_url_migrator)
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        ).first()
        if existing is not None:
            print("An administrator already exists. Bootstrap left the database unchanged.")
            return
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, username, email, password_hash, role, email_verified_at, is_disabled
                )
                VALUES (
                    gen_random_uuid(), :username, :email, :password_hash, 'admin', now(), false
                )
                """
            ),
            {
                "username": username,
                "email": email,
                "password_hash": hash_password(password),
            },
        )
    print("Created the first administrator and marked that email verified.")


if __name__ == "__main__":
    main()
