"""Deep review contracts. The fake provider is not a live model."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from app.agents.claims import validate_claims
from app.agents.finding import FindingRejected
from app.agents.limits import Budget, ReviewLimit
from app.agents.review import delegate_wave, process_review
from app.agents.specialists import plan_roles, run_wave
from app.core.ssrf import SsrfError
from app.ingestion.synthetic import build_fixture_pdf
from tests.conftest import csrf_headers, register
from tests.test_ledger import FILE_PASSWORD, PASSWORD, _cards, _owner_id, _run, _verify

ENDPOINT = "https://1.1.1.1/v1"


def _snapshot(income: str = "0.00") -> dict:
    return {
        "transactions": [
            {
                "id": "tx-1",
                "posted_on": "2026-09-02",
                "description": "Market",
                "category": "Groceries",
                "entry_type": "purchase",
                "amount": "430.00",
                "card_last4": "4412",
            }
        ],
        "cash_entries": [],
        "statements": [],
        "totals": {
            "gross_purchases": "430.00",
            "refunds": "0.00",
            "cash_purchases": "0.00",
            "income_total": income,
            "net_spending": "430.00",
            "fees": "0.00",
            "payments": "0.00",
            "transfers": "0.00",
            "cash_withdrawals": "0.00",
            "includes_accepted_discrepancy": False,
        },
    }


def test_short_questions_do_not_delegate_and_caps_hold():
    assert plan_roles("question") == []
    assert plan_roles("monthly") == ["behaviour", "scenario"]
    budget = Budget()
    budget.calls = 40
    with pytest.raises(ReviewLimit) as limited:
        budget.charge(1)
    assert limited.value.code == "budget"
    with pytest.raises(ReviewLimit) as deep:
        run_wave(["behaviour"], _snapshot(), Budget(), depth=3)
    assert deep.value.code == "depth"
    with pytest.raises(ReviewLimit) as wide:
        run_wave(["behaviour", "scenario", "obligations"], _snapshot(), Budget(), depth=1)
    assert wide.value.code == "parallel"


def test_missing_income_blocks_an_affordability_claim():
    snapshot = _snapshot()
    with pytest.raises(FindingRejected) as caught:
        validate_claims(
            snapshot,
            [{"calculation_id": "affordability", "amount": "100.00", "evidence_ids": []}],
            {"proposed": "420.00", "affordability_blocked": True, "affordability_amount": None},
        )
    assert caught.value.code == "income_missing"
    with pytest.raises(FindingRejected):
        validate_claims(
            snapshot,
            [{"calculation_id": "net_spending", "amount": "1.00", "evidence_ids": ["tx-1"]}],
            None,
        )


def test_configured_review_does_not_fall_back(database_env, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("the fake review ran as a fallback")

    monkeypatch.setattr("app.agents.review.run_wave", explode)
    profile = {"endpoint": "http://127.0.0.1:9/v1", "model_name": "local", "api_key_ciphertext": None}
    with pytest.raises(SsrfError):
        delegate_wave("configured", profile, _snapshot())


async def test_replay_publishes_one_briefing_and_one_accepted_target(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"review{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    await _cards(client)
    _verify(migrator, username)
    owner_id = await _owner_id(client)
    uploaded = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([FILE_PASSWORD])},
        files=[("files", ("good.pdf", build_fixture_pdf(password=FILE_PASSWORD), "application/pdf"))],
    )
    assert uploaded.status_code == 202, uploaded.text
    _run(uploaded.json()["documents"], owner_id)
    saved = await client.put(
        "/api/v1/provider",
        headers=await csrf_headers(client),
        json={"endpoint": ENDPOINT, "model": "local-test", "consent": "selected_transactions"},
    )
    assert saved.status_code == 200, saved.text
    memory = await client.post(
        "/api/v1/memories",
        headers=await csrf_headers(client),
        json={"body": "Keep the monthly review on posted rows."},
    )
    assert memory.status_code == 201, memory.text
    created = await client.post(
        "/api/v1/reviews",
        headers={**await csrf_headers(client), "Idempotency-Key": f"month-{suffix}"},
        json={},
    )
    assert created.status_code == 202, created.text
    review_id = created.json()["id"]
    paused = await client.post(f"/api/v1/reviews/{review_id}/pause", headers=await csrf_headers(client))
    assert paused.status_code == 200, paused.text
    process_review(review_id, owner_id)
    assert (await client.get(f"/api/v1/reviews/{review_id}")).json()["briefing"] is None
    resumed = await client.post(f"/api/v1/reviews/{review_id}/resume", headers=await csrf_headers(client))
    assert resumed.status_code == 200, resumed.text
    process_review(review_id, owner_id, max_steps=1)
    cancelled = await client.post(f"/api/v1/reviews/{review_id}/cancel", headers=await csrf_headers(client))
    assert cancelled.status_code == 200, cancelled.text
    process_review(review_id, owner_id)
    assert (await client.get(f"/api/v1/reviews/{review_id}")).json()["status"] == "cancelled"
    await client.post(f"/api/v1/reviews/{review_id}/resume", headers=await csrf_headers(client))
    process_review(review_id, owner_id)
    process_review(review_id, owner_id)
    body = (await client.get(f"/api/v1/reviews/{review_id}")).json()
    assert body["status"] == "published"
    assert body["live"] is False
    assert body["provider_mode"] == "fake"
    assert body["specialists"] == ["behaviour", "scenario"]
    assert "obligations" not in body["specialists"]
    assert body["call_count"] <= 40
    assert body["memories"] == ["Keep the monthly review on posted rows."]
    assert body["briefing"]["title"] == "Posted net spending is 430.00 AED"
    assert "not an affordability claim" in body["briefing"]["explanation"]
    assert body["scenario"]["calculation_id"] == "category_reduction"
    assert body["scenario"]["category"] == "Groceries"
    assert body["scenario"]["baseline"] == "400.00"
    assert body["scenario"]["reduction"] == "10.00"
    assert body["scenario"]["proposed"] == "390.00"
    assert body["scenario"]["affordability_blocked"] is True
    assert body["scenario"]["affordability_amount"] is None
    assert body["target"]["status"] == "staged"
    assert FILE_PASSWORD not in json.dumps(body)
    again = await client.post(
        "/api/v1/reviews",
        headers={**await csrf_headers(client), "Idempotency-Key": f"month-{suffix}"},
        json={},
    )
    assert again.json()["id"] == review_id
    second = await client.post(
        "/api/v1/reviews",
        headers={**await csrf_headers(client), "Idempotency-Key": f"replay-{suffix}"},
        json={},
    )
    process_review(second.json()["id"], owner_id)
    accepted = await client.post(
        f"/api/v1/targets/{body['target']['id']}/accept",
        headers=await csrf_headers(client),
    )
    assert accepted.status_code == 200, accepted.text
    repeated = await client.post(
        f"/api/v1/targets/{body['target']['id']}/accept",
        headers=await csrf_headers(client),
    )
    assert repeated.json()["id"] == accepted.json()["id"]
    assert repeated.json()["status"] == "accepted"
    rows = (await client.get("/api/v1/transactions")).json()["transactions"]
    grocery = next(row for row in rows if row["description"] == "Carrefour" and row["category"] == "Groceries")
    staged = await client.post(
        "/api/v1/corrections",
        headers=await csrf_headers(client),
        json={"transaction_id": grocery["id"], "category": "Dining"},
    )
    assert staged.status_code == 201, staged.text
    assert staged.json()["original_category"] == "Groceries"
    assert staged.json()["status"] == "staged"
    unchanged = next(row for row in (await client.get("/api/v1/transactions")).json()["transactions"] if row["id"] == grocery["id"])
    assert unchanged["category"] == "Groceries"
    assert unchanged["description"] == "Carrefour"
    confirmed = await client.post(
        f"/api/v1/corrections/{staged.json()['id']}/accept",
        headers=await csrf_headers(client),
    )
    assert confirmed.json()["status"] == "accepted"
    assert confirmed.json()["original_category"] == "Groceries"
    changed = next(row for row in (await client.get("/api/v1/transactions")).json()["transactions"] if row["id"] == grocery["id"])
    assert changed["category"] == "Dining"
    assert changed["description"] == "Carrefour"
    stale = (await client.get(f"/api/v1/reviews/{review_id}")).json()
    assert stale["briefing"]["stale"] is True
    assert stale["scenario"]["stale"] is True
    with migrator.connect() as connection:
        briefings = connection.execute(
            text("SELECT count(*) FROM briefings WHERE owner_id = :owner"),
            {"owner": owner_id},
        ).scalar_one()
        targets = connection.execute(
            text("SELECT count(*) FROM targets WHERE owner_id = :owner AND status = 'accepted'"),
            {"owner": owner_id},
        ).scalar_one()
        checkpoints = connection.execute(
            text("SELECT count(*) FROM review_checkpoints WHERE owner_id = :owner AND review_id = :review"),
            {"owner": owner_id, "review": review_id},
        ).scalar_one()
        findings = connection.execute(
            text("SELECT stale FROM findings WHERE owner_id = :owner AND review_id = :review"),
            {"owner": owner_id, "review": review_id},
        ).scalar_one()
    assert briefings == 1
    assert targets == 1
    assert checkpoints == 6
    assert findings is True


async def test_income_allows_only_the_calculated_leftover(client, migrator):
    suffix = uuid.uuid4().hex[:8]
    username = f"income{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    await _cards(client)
    _verify(migrator, username)
    owner_id = await _owner_id(client)
    uploaded = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        data={"passwords": json.dumps([FILE_PASSWORD])},
        files=[("files", ("good.pdf", build_fixture_pdf(password=FILE_PASSWORD), "application/pdf"))],
    )
    _run(uploaded.json()["documents"], owner_id)
    await client.put(
        "/api/v1/provider",
        headers=await csrf_headers(client),
        json={"endpoint": ENDPOINT, "model": "local-test", "consent": "selected_transactions"},
    )
    await client.post(
        "/api/v1/cash-entries",
        headers=await csrf_headers(client),
        json={"posted_on": "2026-09-01", "description": "Salary", "category": "Income", "amount": "1000.00"},
    )
    created = await client.post("/api/v1/reviews", headers=await csrf_headers(client), json={})
    process_review(created.json()["id"], owner_id)
    body = (await client.get(f"/api/v1/reviews/{created.json()['id']}")).json()
    assert body["scenario"]["affordability_blocked"] is False
    assert body["scenario"]["affordability_amount"] == "580.00"
    assert "not an affordability claim" not in body["briefing"]["explanation"]
    manual = await client.post(
        "/api/v1/scenarios",
        headers=await csrf_headers(client),
        json={"category": "Groceries", "reduction": "10.00", "user_id": "other"},
    )
    assert manual.status_code == 201, manual.text
    assert manual.json()["proposed"] == "390.00"
    assert manual.json()["affordability_amount"] == "580.00"
    assert "user_id" not in manual.text


async def test_other_users_cannot_read_a_review_or_memory(application):
    from httpx import ASGITransport, AsyncClient

    suffix = uuid.uuid4().hex[:8]
    owner = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    other = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    try:
        await register(owner, f"memo{suffix}", f"memo{suffix}@example.com", PASSWORD)
        await register(other, f"hide{suffix}", f"hide{suffix}@example.com", PASSWORD)
        await owner.put(
            "/api/v1/provider",
            headers=await csrf_headers(owner),
            json={"endpoint": ENDPOINT, "model": "local-test", "consent": "none"},
        )
        refused = await owner.post("/api/v1/reviews", headers=await csrf_headers(owner), json={})
        assert refused.status_code == 403
        created = await owner.post(
            "/api/v1/memories",
            headers=await csrf_headers(owner),
            json={"body": "A private preference."},
        )
        assert (await other.get("/api/v1/memories")).json()["memories"] == []
        assert (await other.get("/api/v1/reviews")).json()["reviews"] == []
        missing = await other.get(f"/api/v1/memories")
        assert created.json()["body"] not in missing.text
        await owner.delete(f"/api/v1/memories/{created.json()['id']}", headers=await csrf_headers(owner))
        assert (await owner.get("/api/v1/memories")).json()["memories"] == []
    finally:
        await owner.aclose()
        await other.aclose()
