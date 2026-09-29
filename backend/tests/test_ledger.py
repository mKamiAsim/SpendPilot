"""Ledger slice: ten-card limit, one-file password failure, and no double counting."""

from __future__ import annotations

import json
import uuid
from io import BytesIO

from pikepdf import Dictionary, Name, Pdf
from sqlalchemy import text

from app.core.config import get_settings
from app.core.crypto import parse_key_ring
from app.ingestion.synthetic import build_fixture_pdf
from app.jobs.queue import import_document
from tests.conftest import csrf_headers, register

PASSWORD = "correct-horse-1"
FILE_PASSWORD = "fixture-password"
CARD_PASSWORD = "card-password-value"


def _plain_pdf(line: str) -> bytes:
    pdf = Pdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Contents = pdf.make_stream(f"BT /F1 12 Tf 72 720 Td ({line}) Tj ET".encode("ascii"))
    page.Resources = Dictionary(Font=Dictionary(F1=font))
    raw = BytesIO()
    pdf.save(raw)
    return raw.getvalue()


def _verify(migrator, username: str) -> None:
    with migrator.begin() as connection:
        connection.execute(
            text("UPDATE users SET email_verified_at = now() WHERE username = :username"),
            {"username": username},
        )


async def _cards(client, account_last4: str = "4410") -> None:
    for alias, last4, password in (
        ("Everyday", "4412", CARD_PASSWORD),
        ("Supplementary", "4413", None),
    ):
        created = await client.post(
            "/api/v1/cards",
            headers=await csrf_headers(client),
            json={
                "alias": alias,
                "last4": last4,
                "account_alias": "Shared liability",
                "account_last4": account_last4,
                "password": password,
            },
        )
        assert created.status_code == 201, created.text


async def _owner_id(client) -> str:
    session = await client.get("/api/v1/auth/session")
    assert session.status_code == 200, session.text
    return session.json()["user"]["id"]


def _run(documents: list[dict], owner_id: str) -> None:
    for document in documents:
        if document["status"] == "queued":
            import_document(document["id"], owner_id)
            import_document(document["id"], owner_id)


async def test_active_card_limit_and_saved_password_is_not_returned(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"limit{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    headers = await csrf_headers(client)
    for index in range(10):
        created = await client.post(
            "/api/v1/cards",
            headers=headers,
            json={
                "alias": f"Card {index}",
                "last4": f"{index:04d}",
                "account_alias": "Shared liability",
                "account_last4": "8800",
                "password": CARD_PASSWORD if index == 0 else None,
            },
        )
        assert created.status_code == 201, created.text
        assert "password" not in created.json()
        assert created.json()["password_saved"] is (index == 0)
        assert CARD_PASSWORD not in created.text
        assert "closing_liability" not in created.json()
    rejected = await client.post(
        "/api/v1/cards",
        headers=headers,
        json={
            "alias": "Eleventh",
            "last4": "0010",
            "account_alias": "Shared liability",
            "account_last4": "8800",
        },
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"]["code"] == "card_limit"
    listed = await client.get("/api/v1/cards")
    assert len(listed.json()["cards"]) == 10
    assert CARD_PASSWORD not in listed.text
    first = listed.json()["cards"][0]
    closed = await client.patch(
        f"/api/v1/cards/{first['id']}",
        headers=headers,
        json={"status": "closed"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    allowed = await client.post(
        "/api/v1/cards",
        headers=headers,
        json={
            "alias": "Replacement",
            "last4": "0010",
            "account_alias": "Shared liability",
            "account_last4": "8800",
        },
    )
    assert allowed.status_code == 201, allowed.text
    with migrator.connect() as connection:
        blob = connection.execute(
            text("SELECT password_ciphertext FROM cards WHERE last4 = '0000'")
        ).scalar_one()
    raw = bytes(blob)
    assert CARD_PASSWORD.encode() not in raw
    ring = parse_key_ring(get_settings().encryption_keys, get_settings().encryption_key_id)
    assert ring.decrypt(raw).decode() == CARD_PASSWORD


async def test_batch_password_failure_reimport_and_shared_total(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"batch{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    await _cards(client)
    _verify(migrator, username)
    owner_id = await _owner_id(client)
    good = build_fixture_pdf(password=FILE_PASSWORD)
    bad = build_fixture_pdf(password=FILE_PASSWORD, note="wrong-password-copy")
    other = _plain_pdf("This is not a statement")
    uploaded = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([FILE_PASSWORD, "not-the-password", None])},
        files=[
            ("files", ("good.pdf", good, "application/pdf")),
            ("files", ("bad.pdf", bad, "application/pdf")),
            ("files", ("other.pdf", other, "application/pdf")),
        ],
    )
    assert uploaded.status_code == 202, uploaded.text
    documents = uploaded.json()["documents"]
    assert [row["status"] for row in documents] == ["queued", "queued", "queued"]
    _run(documents, owner_id)
    _run(documents, owner_id)
    listed = await client.get("/api/v1/documents")
    by_name = {row["original_name"]: row for row in listed.json()["documents"]}
    assert by_name["good.pdf"]["status"] == "committed"
    assert by_name["bad.pdf"]["status"] == "failed"
    assert by_name["bad.pdf"]["failure_code"] == "wrong_password"
    assert FILE_PASSWORD not in by_name["bad.pdf"]["failure_message"]
    assert by_name["other.pdf"]["status"] == "failed"
    assert by_name["other.pdf"]["failure_code"] == "unsupported_layout"
    transactions = (await client.get("/api/v1/transactions")).json()["transactions"]
    assert len(transactions) == 8
    carrefour = [row for row in transactions if row["description"] == "Carrefour" and row["amount"] == "200.00"]
    assert len(carrefour) == 2
    assert {row["entry_type"] for row in transactions} >= {"purchase", "payment", "refund", "transfer", "cash_withdrawal"}
    cards = await client.get("/api/v1/cards")
    assert cards.status_code == 200
    assert "1215.00" not in cards.text
    assert "closing_liability" not in cards.text
    assert len(cards.json()["cards"]) == 2
    statements = (await client.get("/api/v1/statements")).json()["statements"]
    assert len(statements) == 1
    assert statements[0]["closing_liability"] == "1215.00"
    assert statements[0]["reconciliation"] == "verified"
    assert statements[0]["account_last4"] == "4410"
    summary = (await client.get("/api/v1/analytics/summary")).json()
    assert summary == {
        "gross_purchases": "450.00",
        "refunds": "20.00",
        "cash_purchases": "0.00",
        "net_spending": "430.00",
        "fees": "25.00",
        "interest": "0.00",
        "payments": "300.00",
        "transfers": "40.00",
        "cash_withdrawals": "100.00",
        "cashback": "0.00",
        "statement_count": 1,
        "includes_accepted_discrepancy": False,
    }
    cash = await client.post(
        "/api/v1/cash-entries",
        headers=await csrf_headers(client),
        json={
            "posted_on": "2026-09-10",
            "description": "Market",
            "category": "Groceries",
            "amount": "10.00",
        },
    )
    assert cash.status_code == 201, cash.text
    after_cash = (await client.get("/api/v1/analytics/summary")).json()
    assert after_cash["net_spending"] == "440.00"
    assert after_cash["cash_purchases"] == "10.00"
    assert after_cash["cash_withdrawals"] == "100.00"
    assert after_cash["payments"] == "300.00"
    assert len((await client.get("/api/v1/transactions")).json()["transactions"]) == 8
    again = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([FILE_PASSWORD])},
        files=[("files", ("good.pdf", good, "application/pdf"))],
    )
    assert again.status_code == 202, again.text
    assert again.json()["documents"][0]["status"] == "duplicate"
    _run(again.json()["documents"], owner_id)
    assert len((await client.get("/api/v1/transactions")).json()["transactions"]) == 8
    assert len((await client.get("/api/v1/statements")).json()["statements"]) == 1
    overlap = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([FILE_PASSWORD])},
        files=[("files", ("overlap.pdf", build_fixture_pdf(password=FILE_PASSWORD, note="second-copy"), "application/pdf"))],
    )
    assert overlap.status_code == 202, overlap.text
    _run(overlap.json()["documents"], owner_id)
    review = (await client.get("/api/v1/review")).json()["review"]
    assert len(review) == 1
    assert review[0]["failure_code"] == "overlapping_period"
    assert len((await client.get("/api/v1/transactions")).json()["transactions"]) == 8
    with migrator.connect() as connection:
        leftover = connection.execute(
            text(
                """
                SELECT count(*) FROM source_documents
                WHERE import_password_ciphertext IS NOT NULL
                  AND owner_id = :owner
                """
            ),
            {"owner": owner_id},
        ).scalar_one()
    assert leftover == 0


async def test_unreconciled_stays_out_of_analytics_until_accepted(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"review{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    await _cards(client, "4410")
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
    assert uploaded.status_code == 202, uploaded.text
    _run(uploaded.json()["documents"], owner_id)
    document_id = uploaded.json()["documents"][0]["id"]
    review = (await client.get("/api/v1/review")).json()["review"]
    assert review[0]["id"] == document_id
    assert review[0]["failure_code"] == "unreconciled"
    assert review[0]["closing_liability"] == "9999.00"
    assert review[0]["computed_closing"] == "1215.00"
    before = (await client.get("/api/v1/analytics/summary")).json()
    assert before["statement_count"] == 0
    assert before["net_spending"] == "0.00"
    assert (await client.get("/api/v1/transactions")).json()["transactions"] == []
    accepted = await client.post(
        f"/api/v1/review/{document_id}/accept",
        headers=await csrf_headers(client),
        json={"reason": "The stated closing does not match the printed rows."},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["reconciliation"] == "accepted_discrepancy"
    assert accepted.json()["closing_liability"] == "9999.00"
    repeated = await client.post(
        f"/api/v1/review/{document_id}/accept",
        headers=await csrf_headers(client),
        json={"reason": "The stated closing does not match the printed rows."},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["id"] == accepted.json()["id"]
    after = (await client.get("/api/v1/analytics/summary")).json()
    assert after["includes_accepted_discrepancy"] is True
    assert after["net_spending"] == "430.00"
    assert after["statement_count"] == 1
    assert len((await client.get("/api/v1/statements")).json()["statements"]) == 1
    assert len((await client.get("/api/v1/transactions")).json()["transactions"]) == 8


async def test_unverified_user_cannot_import_and_rows_stay_private(application, migrator):
    from httpx import ASGITransport, AsyncClient

    suffix = uuid.uuid4().hex[:8]
    owner_name = f"owner{suffix}"
    other_name = f"other{suffix}"
    owner = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    other = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    fresh = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    try:
        await register(owner, owner_name, f"{owner_name}@example.com", PASSWORD)
        await register(other, other_name, f"{other_name}@example.com", PASSWORD)
        await register(fresh, f"fresh{suffix}", f"fresh{suffix}@example.com", PASSWORD)
        blocked = await fresh.post(
            "/api/v1/imports",
            headers=await csrf_headers(fresh),
            files=[("files", ("good.pdf", build_fixture_pdf(password=FILE_PASSWORD), "application/pdf"))],
            data={"passwords": json.dumps([FILE_PASSWORD])},
        )
        assert blocked.status_code == 403, blocked.text
        assert blocked.json()["error"]["code"] == "email_unverified"
        await _cards(owner)
        _verify(migrator, owner_name)
        uploaded = await owner.post(
            "/api/v1/imports",
            headers=await csrf_headers(owner),
            data={"passwords": json.dumps([None])},
            files=[("files", ("saved.pdf", build_fixture_pdf(password=CARD_PASSWORD), "application/pdf"))],
        )
        assert uploaded.status_code == 202, uploaded.text
        import_document(uploaded.json()["documents"][0]["id"], await _owner_id(owner))
        assert (await owner.get("/api/v1/analytics/summary")).json()["net_spending"] == "430.00"
        assert (await other.get("/api/v1/cards")).json()["cards"] == []
        assert (await other.get("/api/v1/transactions")).json()["transactions"] == []
        assert (await other.get("/api/v1/statements")).json()["statements"] == []
        assert (await other.get("/api/v1/analytics/summary")).json()["statement_count"] == 0
        assert (await other.get("/api/v1/review")).json()["review"] == []
    finally:
        await owner.aclose()
        await other.aclose()
        await fresh.aclose()
