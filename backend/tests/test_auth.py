from __future__ import annotations

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.security import hash_token
from tests.conftest import csrf_headers, register

PASSWORD = "correct-horse-1"


def _token(body: str) -> str:
    match = re.search(r"token=([^\s]+)", body)
    assert match, body
    return match.group(1)


def _latest_body(migrator, recipient: str) -> str:
    with migrator.connect() as connection:
        body = connection.execute(
            text(
                "SELECT body FROM mail_outbox WHERE recipient = :recipient "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"recipient": recipient},
        ).scalar()
    assert body
    return body


@pytest.mark.asyncio
async def test_register_login_logout_and_csrf(client):
    name = f"ada{uuid.uuid4().hex[:8]}"
    denied = await client.post(
        "/api/v1/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": PASSWORD},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "csrf_failed"

    created = await register(client, name, f"{name}@example.com")
    assert created["user"]["email_verified"] is False
    assert created["email_delivery"] == "captured"
    session = await client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["username"] == name

    logged_out = await client.post("/api/v1/auth/logout", headers=await csrf_headers(client))
    assert logged_out.status_code == 200
    assert (await client.get("/api/v1/auth/session")).status_code == 401

    logged_in = await client.post(
        "/api/v1/auth/login",
        headers=await csrf_headers(client),
        json={"username": name, "password": PASSWORD},
    )
    assert logged_in.status_code == 200
    wrong = await client.post(
        "/api/v1/auth/login",
        headers=await csrf_headers(client),
        json={"username": name, "password": "not-the-password"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_public_registration_cannot_grant_admin(client):
    name = f"bob{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/v1/auth/register",
        headers=await csrf_headers(client),
        json={
            "username": name,
            "email": f"{name}@example.com",
            "password": PASSWORD,
            "role": "admin",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_not_allowed"


@pytest.mark.asyncio
async def test_verification_expires_and_cannot_be_reused(client, migrator):
    name = f"cara{uuid.uuid4().hex[:8]}"
    email = f"{name}@example.com"
    await register(client, name, email)
    token = _token(_latest_body(migrator, email))
    assert "http://localhost:8080/verify?token=" in _latest_body(migrator, email)
    assert "evil.example" not in _latest_body(migrator, email)

    with migrator.begin() as connection:
        connection.execute(
            text("UPDATE email_tokens SET expires_at = now() - interval '1 minute' WHERE token_hash = :token_hash"),
            {"token_hash": hash_token(token)},
        )
    expired = await client.post(
        "/api/v1/auth/verify",
        headers=await csrf_headers(client),
        json={"token": token},
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "token_expired"

    with migrator.begin() as connection:
        connection.execute(
            text("UPDATE email_tokens SET expires_at = now() + interval '1 hour' WHERE token_hash = :token_hash"),
            {"token_hash": hash_token(token)},
        )
    verified = await client.post(
        "/api/v1/auth/verify",
        headers=await csrf_headers(client),
        json={"token": token},
    )
    assert verified.status_code == 200
    assert verified.json()["user"]["email_verified"] is True
    reused = await client.post(
        "/api/v1/auth/verify",
        headers=await csrf_headers(client),
        json={"token": token},
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "token_used"


@pytest.mark.asyncio
async def test_reset_expires_cannot_be_reused_and_revokes_sessions(client, migrator):
    name = f"dina{uuid.uuid4().hex[:8]}"
    email = f"{name}@example.com"
    await register(client, name, email)
    verify = _token(_latest_body(migrator, email))
    assert (
        await client.post("/api/v1/auth/verify", headers=await csrf_headers(client), json={"token": verify})
    ).status_code == 200

    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        headers=await csrf_headers(client),
        json={"email": email},
    )
    assert forgot.status_code == 200
    assert forgot.json()["password_reset"] == "accepted"
    missing = await client.post(
        "/api/v1/auth/forgot-password",
        headers=await csrf_headers(client),
        json={"email": "nobody@example.com"},
    )
    assert missing.status_code == 200
    assert missing.json()["message"] == forgot.json()["message"]

    token = _token(_latest_body(migrator, email))
    assert "/reset?token=" in _latest_body(migrator, email)
    with migrator.begin() as connection:
        connection.execute(
            text("UPDATE email_tokens SET expires_at = now() - interval '1 minute' WHERE token_hash = :token_hash"),
            {"token_hash": hash_token(token)},
        )
    expired = await client.post(
        "/api/v1/auth/reset-password",
        headers=await csrf_headers(client),
        json={"token": token, "password": "a-new-password-1"},
    )
    assert expired.json()["error"]["code"] == "token_expired"

    with migrator.begin() as connection:
        connection.execute(
            text(
                "UPDATE email_tokens SET expires_at = now() + interval '20 minutes' "
                "WHERE token_hash = :token_hash"
            ),
            {"token_hash": hash_token(token)},
        )
    reset = await client.post(
        "/api/v1/auth/reset-password",
        headers=await csrf_headers(client),
        json={"token": token, "password": "a-new-password-1"},
    )
    assert reset.status_code == 200
    assert (await client.get("/api/v1/auth/session")).status_code == 401
    reused = await client.post(
        "/api/v1/auth/reset-password",
        headers=await csrf_headers(client),
        json={"token": token, "password": "another-password-2"},
    )
    assert reused.json()["error"]["code"] == "token_used"
    signed_in = await client.post(
        "/api/v1/auth/login",
        headers=await csrf_headers(client),
        json={"username": email, "password": "a-new-password-1"},
    )
    assert signed_in.status_code == 200


@pytest.mark.asyncio
async def test_reset_stays_off_without_smtp(database_env):
    from app.core.config import get_settings
    from app.main import create_app

    previous = {key: os_value(key) for key in ("EMAIL_DELIVERY", "SMTP_HOST")}
    import os

    os.environ["EMAIL_DELIVERY"] = "smtp"
    os.environ["SMTP_HOST"] = ""
    get_settings.cache_clear()
    try:
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://localhost:8080") as http:
            options = await http.get("/api/v1/auth/options")
            assert options.json()["password_reset_available"] is False
            assert options.json()["email_delivery"] == "unconfigured"
            response = await http.post(
                "/api/v1/auth/forgot-password",
                headers=await csrf_headers(http),
                json={"email": "someone@example.com"},
            )
            assert response.status_code == 200
            assert response.json()["password_reset"] == "unavailable"
    finally:
        os.environ["EMAIL_DELIVERY"] = previous["EMAIL_DELIVERY"]
        os.environ["SMTP_HOST"] = previous["SMTP_HOST"]
        get_settings.cache_clear()


def os_value(key: str) -> str:
    import os

    return os.environ.get(key, "")


@pytest.mark.asyncio
async def test_idle_lock_is_server_enforced_and_heartbeat_is_not_activity(client, migrator):
    name = f"erin{uuid.uuid4().hex[:8]}"
    email = f"{name}@example.com"
    await register(client, name, email)
    user_id = (await client.get("/api/v1/auth/session")).json()["user"]["id"]
    with migrator.begin() as connection:
        connection.execute(
            text(
                "UPDATE sessions SET last_activity_at = now() - interval '1 minute', locked_at = NULL "
                "WHERE user_id = :user_id AND revoked_at IS NULL"
            ),
            {"user_id": user_id},
        )
    heartbeat = await client.post("/api/v1/auth/heartbeat", headers=await csrf_headers(client))
    assert heartbeat.status_code == 200
    assert heartbeat.json()["activity"] == "ignored"
    with migrator.connect() as connection:
        stale = connection.execute(
            text(
                "SELECT last_activity_at < now() - interval '30 seconds' "
                "FROM sessions WHERE user_id = :user_id AND revoked_at IS NULL"
            ),
            {"user_id": user_id},
        ).scalar()
    assert stale is True

    with migrator.begin() as connection:
        connection.execute(
            text(
                "UPDATE sessions SET last_activity_at = now() - interval '16 minutes' "
                "WHERE user_id = :user_id AND revoked_at IS NULL"
            ),
            {"user_id": user_id},
        )
    locked = await client.get("/api/v1/auth/session")
    assert locked.status_code == 423
    assert locked.json()["error"]["code"] == "session_locked"
    still_locked = await client.post("/api/v1/auth/heartbeat", headers=await csrf_headers(client))
    assert still_locked.status_code == 423
    unlocked = await client.post(
        "/api/v1/auth/unlock",
        headers=await csrf_headers(client),
        json={"password": PASSWORD},
    )
    assert unlocked.status_code == 200
    assert (await client.get("/api/v1/auth/session")).status_code == 200


@pytest.mark.asyncio
async def test_bootstrap_admin_is_one_time_and_verified(database_env, migrator):
    import os

    from app.core.config import get_settings
    from app.identity.bootstrap import main

    with migrator.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE role = 'admin'"))
    username = f"admin{uuid.uuid4().hex[:6]}"
    os.environ["BOOTSTRAP_ADMIN_USERNAME"] = username
    os.environ["BOOTSTRAP_ADMIN_EMAIL"] = f"{username}@example.com"
    os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "bootstrap-secret-1"
    get_settings.cache_clear()
    main()
    with migrator.connect() as connection:
        row = connection.execute(
            text(
                "SELECT role, email_verified_at IS NOT NULL FROM users WHERE username = :username"
            ),
            {"username": username},
        ).one()
    assert row == ("admin", True)
    main()
    with migrator.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM users WHERE role = 'admin'")).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_admin_can_disable_registration_and_members_cannot(client, migrator):
    import os

    from app.core.config import get_settings
    from app.identity.bootstrap import main

    username = f"root{uuid.uuid4().hex[:6]}"
    with migrator.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE role = 'admin'"))
    os.environ["BOOTSTRAP_ADMIN_USERNAME"] = username
    os.environ["BOOTSTRAP_ADMIN_EMAIL"] = f"{username}@example.com"
    os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "bootstrap-secret-1"
    get_settings.cache_clear()
    main()
    member = f"faye{uuid.uuid4().hex[:8]}"
    await register(client, member, f"{member}@example.com")
    forbidden = await client.patch(
        "/api/v1/admin/registration",
        headers=await csrf_headers(client),
        json={"enabled": False},
    )
    assert forbidden.status_code == 403

    await client.post("/api/v1/auth/logout", headers=await csrf_headers(client))
    admin_login = await client.post(
        "/api/v1/auth/login",
        headers=await csrf_headers(client),
        json={"username": username, "password": "bootstrap-secret-1"},
    )
    assert admin_login.status_code == 200, admin_login.text
    disabled = await client.patch(
        "/api/v1/admin/registration",
        headers=await csrf_headers(client),
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    await client.post("/api/v1/auth/logout", headers=await csrf_headers(client))
    blocked = await client.post(
        "/api/v1/auth/register",
        headers=await csrf_headers(client),
        json={"username": f"gina{uuid.uuid4().hex[:6]}", "email": "gina@example.com", "password": PASSWORD},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "registration_disabled"
    await client.post(
        "/api/v1/auth/login",
        headers=await csrf_headers(client),
        json={"username": username, "password": "bootstrap-secret-1"},
    )
    restored = await client.patch(
        "/api/v1/admin/registration",
        headers=await csrf_headers(client),
        json={"enabled": True},
    )
    assert restored.status_code == 200


@pytest.mark.asyncio
async def test_verification_link_ignores_host_header(client, migrator):
    name = f"hana{uuid.uuid4().hex[:8]}"
    email = f"{name}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        headers={**(await csrf_headers(client)), "Host": "evil.example"},
        json={"username": name, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    body = _latest_body(migrator, email)
    assert body.startswith("Confirm this email address for SpendPilot.")
    assert "http://localhost:8080/verify?token=" in body
    assert "evil.example" not in body
