from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.db import create_engine
from tests.conftest import csrf_headers, register

PASSWORD = "correct-horse-1"


async def _user_client(application, username: str, email: str):
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    await register(client, username, email)
    return client


async def test_two_users_cannot_read_each_others_rows(application, migrator):
    suffix = uuid.uuid4().hex[:8]
    alice = await _user_client(application, f"alice{suffix}", f"alice{suffix}@example.com")
    bob = await _user_client(application, f"bob{suffix}", f"bob{suffix}@example.com")
    try:
        created = await alice.post(
            "/api/v1/private-records",
            headers=await csrf_headers(alice),
            json={"label": "alice-only"},
        )
        assert created.status_code == 201, created.text
        record_id = created.json()["id"]
        alice_list = await alice.get("/api/v1/private-records")
        assert [row["label"] for row in alice_list.json()["records"]] == ["alice-only"]
        bob_list = await bob.get("/api/v1/private-records")
        assert bob_list.json()["records"] == []
        missing = await bob.get(f"/api/v1/private-records/{record_id}")
        assert missing.status_code == 404

        alice_id = (await alice.get("/api/v1/auth/session")).json()["user"]["id"]
        bob_id = (await bob.get("/api/v1/auth/session")).json()["user"]["id"]
        engine = create_engine(get_settings(), pool_size=1, max_overflow=0)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            await session.execute(
                text("SELECT set_config('app.owner_id', :owner, true)"),
                {"owner": bob_id},
            )
            visible = (await session.execute(text("SELECT label FROM private_records"))).all()
            assert visible == []
            await session.execute(
                text("SELECT set_config('app.owner_id', :owner, true)"),
                {"owner": alice_id},
            )
            visible = (await session.execute(text("SELECT label FROM private_records"))).all()
            assert visible == [("alice-only",)]
            await session.commit()
        async with factory() as session:
            leaked = (
                await session.execute(text("SELECT current_setting('app.owner_id', true)"))
            ).scalar()
            assert leaked in ("", None)
            rows = (await session.execute(text("SELECT label FROM private_records"))).all()
            assert rows == []
            await session.commit()
        await engine.dispose()
    finally:
        await alice.aclose()
        await bob.aclose()


def test_runtime_role_is_not_owner_superuser_or_bypassrls(migrator):
    with migrator.connect() as connection:
        role = connection.execute(
            text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'spendpilot_app'"
            )
        ).one()
        owner = connection.execute(
            text("SELECT tableowner FROM pg_tables WHERE tablename = 'private_records'")
        ).scalar()
    assert role == (False, False)
    assert owner == "spendpilot_migrator"
