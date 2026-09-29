"""Phase 6: bank layout, instalments, purge, and passphrase backups."""

from __future__ import annotations

import json
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.ingestion.bank import build_bank_pdf
from app.ingestion.synthetic import build_fixture_pdf, write_lines_pdf
from app.jobs.queue import import_document
from app.lifecycle.backup import open_backup
from tests.conftest import csrf_headers, register
from tests.test_ledger import FILE_PASSWORD, PASSWORD, _cards, _owner_id, _run, _verify

PASSPHRASE = "backup-passphrase"


def _count(migrator, table: str, owner_id: str) -> int:
    if table not in {"cash_entries", "memories", "posted_transactions", "snapshots", "instalment_plans", "statements"}:
        raise AssertionError(table)
    with migrator.connect() as connection:
        return int(
            connection.execute(
                text(f"SELECT count(*) FROM {table} WHERE owner_id = :owner"),
                {"owner": owner_id},
            ).scalar_one()
        )


def _activity(migrator, owner_id: str):
    with migrator.connect() as connection:
        return connection.execute(
            text("SELECT last_activity_at FROM sessions WHERE user_id = :owner"),
            {"owner": owner_id},
        ).scalar_one()


async def test_bank_payment_is_not_a_second_spending_event(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"bank{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    await _cards(client)
    _verify(migrator, username)
    owner_id = await _owner_id(client)
    uploaded = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([FILE_PASSWORD, None])},
        files=[
            ("files", ("card.pdf", build_fixture_pdf(password=FILE_PASSWORD), "application/pdf")),
            ("files", ("bank.pdf", build_bank_pdf(), "application/pdf")),
        ],
    )
    assert uploaded.status_code == 202, uploaded.text
    _run(uploaded.json()["documents"], owner_id)
    summary = (await client.get("/api/v1/analytics/summary")).json()
    assert summary["net_spending"] == "430.00"
    assert summary["payments"] == "300.00"
    assert summary["transfers"] == "340.00"
    assert summary["statement_count"] == 2
    cards = await client.get("/api/v1/cards")
    assert "4700.00" not in cards.text
    assert len(cards.json()["cards"]) == 2
    statements = (await client.get("/api/v1/statements")).json()["statements"]
    by_kind = {row["kind"]: row for row in statements}
    assert by_kind["card"]["closing_liability"] == "1215.00"
    assert by_kind["bank"]["closing_liability"] == "4700.00"
    assert by_kind["bank"]["account_last4"] == "2200"
    coverage = (await client.get("/api/v1/analytics/coverage")).json()
    assert coverage["complete"] is False
    assert "not complete coverage" in coverage["note"]


async def test_instalment_is_one_purchase_and_terms_can_change(client):
    suffix = uuid.uuid4().hex[:8]
    await register(client, f"plan{suffix}", f"plan{suffix}@example.com", PASSWORD)
    headers = await csrf_headers(client)
    created = await client.post(
        "/api/v1/instalments",
        headers=headers,
        json={
            "description": "Laptop",
            "category": "Shopping",
            "principal": "6000.00",
            "parts": 12,
            "posted_on": "2026-09-01",
        },
    )
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["principal"] == "6000.00"
    assert plan["monthly_amount"] == "500.00"
    assert plan["remaining"] == "6000.00"
    summary = (await client.get("/api/v1/analytics/summary")).json()
    assert summary["instalment_purchases"] == "6000.00"
    assert summary["net_spending"] == "6000.00"
    changed = await client.patch(
        f"/api/v1/instalments/{plan['id']}",
        headers=headers,
        json={"parts": 10},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["monthly_amount"] == "600.00"
    restored = await client.patch(
        f"/api/v1/instalments/{plan['id']}",
        headers=headers,
        json={"parts": 12},
    )
    assert restored.json()["monthly_amount"] == "500.00"
    repayment = await client.post(
        f"/api/v1/instalments/{plan['id']}/repayments",
        headers=headers,
        json={"posted_on": "2026-10-01", "amount": "500.00"},
    )
    assert repayment.status_code == 201, repayment.text
    assert repayment.json()["plan"]["remaining"] == "5500.00"
    assert repayment.json()["plan"]["monthly_amount"] == "500.00"
    after = (await client.get("/api/v1/analytics/summary")).json()
    assert after["net_spending"] == "6000.00"
    assert after["instalment_purchases"] == "6000.00"
    obligations = (await client.get("/api/v1/obligations")).json()
    assert obligations["monthly_commitment"] == "500.00"
    assert obligations["plans"][0]["principal"] == "6000.00"


async def test_confirmed_category_rule_applies_on_the_next_file(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"rule{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    await _cards(client)
    _verify(migrator, username)
    owner_id = await _owner_id(client)
    uploaded = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([FILE_PASSWORD])},
        files=[("files", ("sept.pdf", build_fixture_pdf(password=FILE_PASSWORD), "application/pdf"))],
    )
    _run(uploaded.json()["documents"], owner_id)
    transactions = (await client.get("/api/v1/transactions")).json()["transactions"]
    carrefour = next(row for row in transactions if row["description"] == "Carrefour")
    staged = await client.post(
        "/api/v1/corrections",
        headers=await csrf_headers(client),
        json={"transaction_id": carrefour["id"], "category": "Dining"},
    )
    assert staged.status_code == 201, staged.text
    accepted = await client.post(
        f"/api/v1/corrections/{staged.json()['id']}/accept",
        headers=await csrf_headers(client),
    )
    assert accepted.status_code == 200, accepted.text
    october = write_lines_pdf(
        [
            "SPENDPILOT SYNTHETIC FIXTURE",
            "Layout: generic-aed-card-v1",
            "This is not a bank statement.",
            "Account alias: Shared liability",
            "Account last4: 4410",
            "Period start: 2026-10-01",
            "Period end: 2026-10-31",
            "Opening liability: 0.00",
            "Closing liability: 8.00",
            "Card: Everyday | 4412",
            "ROW | 2026-10-02 | 4412 | purchase | Groceries | Carrefour | 10.00",
            "ROW | 2026-10-03 | 4412 | refund | Groceries | Carrefour refund | 2.00",
        ]
    )
    follow = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([None])},
        files=[("files", ("oct.pdf", october, "application/pdf"))],
    )
    assert follow.status_code == 202, follow.text
    import_document(follow.json()["documents"][0]["id"], owner_id)
    rows = (await client.get("/api/v1/transactions")).json()["transactions"]
    later = next(row for row in rows if row["description"] == "Carrefour" and row["amount"] == "10.00")
    refund = next(row for row in rows if row["description"] == "Carrefour refund")
    assert later["category"] == "Dining"
    assert refund["category"] == "Groceries"


async def test_custom_category_counts_and_analytics_works_with_consent_off(client):
    suffix = uuid.uuid4().hex[:8]
    await register(client, f"cat{suffix}", f"cat{suffix}@example.com", PASSWORD)
    headers = await csrf_headers(client)
    created = await client.post("/api/v1/categories", headers=headers, json={"name": "School"})
    assert created.status_code == 201, created.text
    listed = (await client.get("/api/v1/categories")).json()
    assert "Groceries" in listed["categories"]
    assert listed["custom"] == ["School"]
    cash = await client.post(
        "/api/v1/cash-entries",
        headers=headers,
        json={"posted_on": "2026-09-12", "description": "Books", "category": "School", "amount": "15.00"},
    )
    assert cash.status_code == 201, cash.text
    income = await client.post(
        "/api/v1/cash-entries",
        headers=headers,
        json={"posted_on": "2026-09-12", "description": "Salary", "category": "Income", "amount": "1000.00"},
    )
    assert income.status_code == 201, income.text
    summary = (await client.get("/api/v1/analytics/summary")).json()
    assert summary["cash_purchases"] == "15.00"
    assert summary["net_spending"] == "15.00"
    assert (await client.get("/api/v1/provider")).json()["provider"] is None


async def test_purge_removes_old_rows_and_derived_memory(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"purge{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    headers = await csrf_headers(client)
    owner_id = await _owner_id(client)
    await client.post(
        "/api/v1/cash-entries",
        headers=headers,
        json={"posted_on": "2026-09-12", "description": "Recent", "category": "Cash", "amount": "4.00"},
    )
    old_cash = await client.post(
        "/api/v1/cash-entries",
        headers=headers,
        json={"posted_on": "2026-09-12", "description": "Old market", "category": "Cash", "amount": "3.00"},
    )
    memory = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={"body": "Keep fruit on the weekly list."},
    )
    active = await client.post(
        "/api/v1/instalments",
        headers=headers,
        json={
            "description": "Active phone",
            "category": "Shopping",
            "principal": "6000.00",
            "parts": 12,
            "posted_on": "2026-09-01",
        },
    )
    repaid = await client.post(
        "/api/v1/instalments",
        headers=headers,
        json={
            "description": "Finished chair",
            "category": "Shopping",
            "principal": "100.00",
            "parts": 2,
            "posted_on": "2026-09-01",
        },
    )
    await client.post(
        f"/api/v1/instalments/{repaid.json()['id']}/repayments",
        headers=headers,
        json={"posted_on": "2026-09-02", "amount": "100.00"},
    )
    snapshot_id = uuid.uuid4()
    with migrator.begin() as connection:
        connection.execute(
            text("UPDATE cash_entries SET posted_on = DATE '2020-01-01' WHERE id = :id"),
            {"id": old_cash.json()["id"]},
        )
        connection.execute(
            text("UPDATE memories SET created_at = now() - interval '19 months' WHERE id = :id"),
            {"id": memory.json()["id"]},
        )
        connection.execute(
            text("UPDATE instalment_plans SET posted_on = DATE '2020-01-01' WHERE owner_id = :owner"),
            {"owner": owner_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO snapshots (id, owner_id, consent, consent_version, body, created_at)
                VALUES (:id, :owner, 'none', 1, '{}'::jsonb, now() - interval '19 months')
                """
            ),
            {"id": snapshot_id, "owner": owner_id},
        )
    purged = await client.post("/api/v1/lifecycle/purge", headers=headers)
    assert purged.status_code == 200, purged.text
    assert _count(migrator, "cash_entries", owner_id) == 1
    assert _count(migrator, "memories", owner_id) == 0
    assert _count(migrator, "snapshots", owner_id) == 0
    plans = (await client.get("/api/v1/obligations")).json()["plans"]
    assert [plan["description"] for plan in plans] == ["Active phone"]
    assert plans[0]["principal"] == "6000.00"
    assert plans[0]["monthly_amount"] == "500.00"


async def test_corrupt_backup_does_not_change_existing_data(client, migrator, application):
    suffix = uuid.uuid4().hex[:8]
    owner_name = f"keep{suffix}"
    other_name = f"else{suffix}"
    await register(client, owner_name, f"{owner_name}@example.com", PASSWORD)
    owner_id = await _owner_id(client)
    await _cards(client)
    _verify(migrator, owner_name)
    headers = await csrf_headers(client)
    await client.put(
        "/api/v1/provider",
        headers=headers,
        json={
            "endpoint": "https://1.1.1.1/v1",
            "model": "local",
            "api_key": "provider-key-should-stay-out",
            "consent": "none",
        },
    )
    await client.post(
        "/api/v1/cash-entries",
        headers=headers,
        json={"posted_on": "2026-09-11", "description": "Recent tea", "category": "Dining", "amount": "8.00"},
    )
    old = await client.post(
        "/api/v1/cash-entries",
        headers=headers,
        json={"posted_on": "2026-09-11", "description": "Ancient tea", "category": "Dining", "amount": "2.00"},
    )
    assert old.status_code == 201, old.text
    await client.post("/api/v1/memories", headers=headers, json={"body": "Prefer tea to a second coffee."})
    uploaded = await client.post(
        "/api/v1/imports",
        headers=headers,
        data={"passwords": json.dumps([FILE_PASSWORD])},
        files=[("files", ("card.pdf", build_fixture_pdf(password=FILE_PASSWORD), "application/pdf"))],
    )
    assert uploaded.status_code == 202, uploaded.text
    _run(uploaded.json()["documents"], owner_id)
    assert _count(migrator, "statements", owner_id) == 1
    with migrator.begin() as connection:
        connection.execute(
            text("UPDATE cash_entries SET posted_on = DATE '2020-01-01' WHERE id = :id"),
            {"id": old.json()["id"]},
        )
    created = await client.post(
        "/api/v1/lifecycle/backups",
        headers=headers,
        json={"passphrase": PASSPHRASE, "include_secrets": False},
    )
    assert created.status_code == 201, created.text
    downloaded = await client.get(f"/api/v1/lifecycle/backups/{created.json()['id']}")
    assert downloaded.status_code == 200, downloaded.text
    blob = downloaded.content
    assert b"provider-key-should-stay-out" not in blob
    assert PASSPHRASE.encode() not in blob
    opened = open_backup(blob, PASSPHRASE)
    packed = str(opened)
    assert "provider-key-should-stay-out" not in packed
    assert "card-password-value" not in packed
    assert "ciphertext" not in packed
    assert opened["include_secrets"] is False
    explicit = await client.post(
        "/api/v1/lifecycle/backups",
        headers=headers,
        json={"passphrase": PASSPHRASE, "include_secrets": True},
    )
    explicit_blob = (await client.get(f"/api/v1/lifecycle/backups/{explicit.json()['id']}")).content
    assert open_backup(explicit_blob, PASSPHRASE)["provider"]["api_key"] == "provider-key-should-stay-out"
    before = _count(migrator, "cash_entries", owner_id)
    corrupt = bytearray(blob)
    corrupt[-1] ^= 0xFF
    rejected = await client.post(
        "/api/v1/lifecycle/restore",
        headers=headers,
        data={"passphrase": PASSPHRASE},
        files={"file": ("backup.bin", bytes(corrupt), "application/octet-stream")},
    )
    assert rejected.status_code == 400, rejected.text
    assert _count(migrator, "cash_entries", owner_id) == before
    wrong = await client.post(
        "/api/v1/lifecycle/restore",
        headers=headers,
        data={"passphrase": "not-the-passphrase"},
        files={"file": ("backup.bin", blob, "application/octet-stream")},
    )
    assert wrong.status_code == 400, wrong.text
    assert _count(migrator, "cash_entries", owner_id) == before
    with migrator.begin() as connection:
        connection.execute(text("DELETE FROM cash_entries WHERE owner_id = :owner"), {"owner": owner_id})
        connection.execute(text("DELETE FROM memories WHERE owner_id = :owner"), {"owner": owner_id})
    restored = await client.post(
        "/api/v1/lifecycle/restore",
        headers=headers,
        data={"passphrase": PASSPHRASE},
        files={"file": ("backup.bin", blob, "application/octet-stream")},
    )
    assert restored.status_code == 200, restored.text
    assert _count(migrator, "cash_entries", owner_id) == 1
    assert _count(migrator, "memories", owner_id) == 1
    again = await client.post(
        "/api/v1/lifecycle/restore",
        headers=headers,
        data={"passphrase": PASSPHRASE},
        files={"file": ("backup.bin", blob, "application/octet-stream")},
    )
    assert again.status_code == 200, again.text
    assert _count(migrator, "cash_entries", owner_id) == 1
    assert _count(migrator, "memories", owner_id) == 1
    assert _count(migrator, "statements", owner_id) == 1
    assert _count(migrator, "posted_transactions", owner_id) == 8
    other = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    try:
        await register(other, other_name, f"{other_name}@example.com", PASSWORD)
        hidden = await other.get(f"/api/v1/lifecycle/backups/{created.json()['id']}")
        assert hidden.status_code == 404, hidden.text
        copied = await other.post(
            "/api/v1/lifecycle/restore",
            headers=await csrf_headers(other),
            data={"passphrase": PASSPHRASE},
            files={"file": ("backup.bin", blob, "application/octet-stream")},
        )
        assert copied.status_code == 200, copied.text
        other_id = await _owner_id(other)
        assert _count(migrator, "cash_entries", owner_id) == 1
        assert _count(migrator, "cash_entries", other_id) == 1
    finally:
        await other.aclose()


async def test_events_reconnect_does_not_count_as_activity(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    await register(client, f"live{suffix}", f"live{suffix}@example.com", PASSWORD)
    headers = await csrf_headers(client)
    owner_id = await _owner_id(client)
    for name in ("First", "Second"):
        created = await client.post(
            "/api/v1/instalments",
            headers=headers,
            json={
                "description": name,
                "category": "Shopping",
                "principal": "100.00",
                "parts": 2,
                "posted_on": "2026-09-01",
            },
        )
        assert created.status_code == 201, created.text
    with migrator.begin() as connection:
        connection.execute(
            text("UPDATE sessions SET last_activity_at = now() - interval '5 minutes' WHERE user_id = :owner"),
            {"owner": owner_id},
        )
    before = _activity(migrator, owner_id)
    streamed = await client.get("/api/v1/events")
    assert streamed.status_code == 200, streamed.text
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert ": heartbeat" in streamed.text
    assert _activity(migrator, owner_id) == before
    ids = [int(line.split(":", 1)[1].strip()) for line in streamed.text.splitlines() if line.startswith("id:")]
    assert len(ids) >= 2
    replay = await client.get("/api/v1/events", headers={"Last-Event-ID": str(ids[0])})
    replay_ids = [int(line.split(":", 1)[1].strip()) for line in replay.text.splitlines() if line.startswith("id:")]
    assert ids[0] not in replay_ids
    assert ids[1] in replay_ids
    await client.get("/api/v1/categories")
    assert _activity(migrator, owner_id) != before


async def test_review_split_lists_extracted_rows(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"split{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    await _cards(client)
    _verify(migrator, username)
    owner_id = await _owner_id(client)
    uploaded = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([FILE_PASSWORD])},
        files=[
            (
                "files",
                ("off.pdf", build_fixture_pdf(password=FILE_PASSWORD, closing="9999.00"), "application/pdf"),
            )
        ],
    )
    _run(uploaded.json()["documents"], owner_id)
    review = (await client.get("/api/v1/review")).json()["review"][0]
    assert len(review["rows"]) == 8
    assert review["rows"][0]["description"] == "Carrefour"
    assert FILE_PASSWORD not in str(review)
    assert "password" not in review
