"""Early agent: fake provider in CI, no silent fallback, evidence must be real."""

from __future__ import annotations

import json
import socket
import uuid

import httpx
import pytest
from sqlalchemy import text

from app.agents.finding import FindingDraft, FindingRejected, validate_finding
from app.agents.investigate import _run_provider
from app.agents.openai_client import investigate_live, probe_endpoint
from app.agents.snapshot import FORBIDDEN_KEYS
from app.core.config import get_settings
from app.core.crypto import parse_key_ring
from app.core.ssrf import SsrfError, SsrfPolicy
from app.ingestion.synthetic import build_fixture_pdf
from app.jobs.queue import investigate
from tests.conftest import csrf_headers, register
from tests.test_ledger import FILE_PASSWORD, PASSWORD, _cards, _owner_id, _run, _verify

API_KEY = "sk-test-secret-value"
ENDPOINT = "https://1.1.1.1/v1"


def _snapshot(amount: str = "430.00", evidence: str = "tx-1") -> dict:
    return {
        "transactions": [
            {
                "id": evidence,
                "posted_on": "2026-09-02",
                "description": "Market",
                "category": "Groceries",
                "entry_type": "purchase",
                "amount": amount,
                "card_last4": "4412",
            }
        ],
        "cash_entries": [],
        "statements": [
            {
                "id": "statement-1",
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "closing_liability": "1215.00",
                "reconciliation": "verified",
            }
        ],
        "totals": {
            "gross_purchases": amount,
            "refunds": "0.00",
            "cash_purchases": "0.00",
            "net_spending": amount,
            "fees": "0.00",
            "payments": "0.00",
            "transfers": "0.00",
            "cash_withdrawals": "0.00",
            "includes_accepted_discrepancy": False,
        },
    }


def test_configured_mode_does_not_fall_back_to_the_fake_provider(database_env, monkeypatch):
    def explode(snapshot):
        raise AssertionError("fake provider was used as a fallback")

    monkeypatch.setattr("app.agents.investigate.fake_finding", explode)
    profile = {"endpoint": "http://127.0.0.1:9/v1", "model_name": "local", "api_key_ciphertext": None}
    with pytest.raises(SsrfError):
        _run_provider("configured", profile, _snapshot())


def test_invented_evidence_is_rejected():
    snapshot = _snapshot()
    draft = FindingDraft(
        title="Posted net spending is 430.00 AED",
        explanation="Cited a row that was not in the snapshot.",
        severity="note",
        evidence_ids=("invented-row",),
        calculation_id="net_spending",
        amount="430.00",
    )
    with pytest.raises(FindingRejected) as caught:
        validate_finding(snapshot, draft)
    assert caught.value.code == "invented_evidence"


def test_redirect_to_metadata_is_not_followed():
    calls: list[str] = []

    def send(url: str, api_key: str | None, body: dict) -> httpx.Response:
        calls.append(url)
        assert api_key == "secret"
        assert body["messages"][0]["content"] == "Reply with ready."
        assert "password" not in json.dumps(body)
        request = httpx.Request("POST", url)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest"}, request=request)

    result = probe_endpoint(
        "https://1.1.1.1/v1",
        "secret",
        "local",
        SsrfPolicy(frozenset()),
        send,
    )
    assert result.ok is False
    assert result.code == "ssrf"
    assert calls == ["https://1.1.1.1/v1/chat/completions"]


def test_scripted_endpoint_can_publish_only_real_evidence():
    snapshot = _snapshot()
    purchase_id = snapshot["transactions"][0]["id"]
    calls: list[dict] = []

    def send(url: str, api_key: str | None, body: dict) -> httpx.Response:
        calls.append(body)
        request = httpx.Request("POST", url)
        if len(calls) == 1:
            message = {
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "spending_total", "arguments": json.dumps({"user_id": "other-user"})},
                    }
                ]
            }
        else:
            message = {
                "content": json.dumps(
                    {
                        "title": "Posted net spending is 430.00 AED",
                        "explanation": "The tool total is the only amount used.",
                        "severity": "note",
                        "evidence_ids": [purchase_id],
                        "calculation_id": "net_spending",
                        "amount": "430.00",
                    }
                )
            }
        return httpx.Response(200, json={"choices": [{"message": message}]}, request=request)

    draft, activity = investigate_live(
        ENDPOINT,
        None,
        "local",
        snapshot,
        SsrfPolicy(frozenset()),
        send,
    )
    validate_finding(snapshot, draft)
    assert draft.amount == "430.00"
    assert draft.evidence_ids == (purchase_id,)
    assert activity == ["Called spending_total."]
    assert calls[0]["messages"][1]["content"].startswith("What is posted net spending")


def test_live_smoke_stays_pending_without_an_endpoint(database_env, monkeypatch):
    monkeypatch.setenv("MODEL_SMOKE_URL", "")
    get_settings.cache_clear()

    def refuse_dns(*_args, **_kwargs):
        raise AssertionError("the pending smoke test opened a connection")

    monkeypatch.setattr(socket, "getaddrinfo", refuse_dns)
    from app.agents.smoke import live_smoke_from_env

    result = live_smoke_from_env()
    assert result == {
        "status": "pending",
        "live": False,
        "checked": False,
        "message": "MODEL_SMOKE_URL is not configured. Live tool-calling is unverified.",
    }
    get_settings.cache_clear()


@pytest.mark.skipif(
    not __import__("os").environ.get("MODEL_SMOKE_URL"),
    reason="MODEL_SMOKE_URL is not configured. Live tool-calling stays unverified.",
)
def test_live_openai_compatible_smoke():
    from app.agents.smoke import live_smoke_from_env

    result = live_smoke_from_env()
    assert result["checked"] is True
    assert result["live"] is True
    assert result["status"] == "ok"


async def test_fake_investigation_publishes_one_validated_finding(client, migrator, monkeypatch):
    def refuse_network(*_args, **_kwargs):
        raise AssertionError("the fake provider opened a network client")

    monkeypatch.setattr(httpx.Client, "__init__", refuse_network)
    suffix = uuid.uuid4().hex[:8]
    username = f"agent{suffix}"
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
        json={
            "endpoint": ENDPOINT,
            "model": "local-test",
            "api_key": API_KEY,
            "consent": "selected_transactions",
        },
    )
    assert saved.status_code == 200, saved.text
    assert API_KEY not in saved.text
    assert saved.json()["provider"]["api_key_saved"] is True
    assert saved.json()["provider"]["document_assistance"] is False
    assert saved.json()["live_provider"] is False
    listed = await client.get("/api/v1/provider")
    assert API_KEY not in listed.text
    tested = await client.post("/api/v1/provider/test", headers=await csrf_headers(client))
    assert tested.status_code == 200, tested.text
    assert tested.json()["live"] is False
    assert tested.json()["provider"] == "fake"
    blocked = await client.put(
        "/api/v1/provider",
        headers=await csrf_headers(client),
        json={"endpoint": "http://169.254.169.254/latest", "model": "local-test", "consent": "selected_transactions"},
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "ssrf"
    created = await client.post(
        "/api/v1/investigations",
        headers={**await csrf_headers(client), "Idempotency-Key": f"spend-{suffix}"},
        json={},
    )
    assert created.status_code == 202, created.text
    investigation_id = created.json()["id"]
    investigate(investigation_id, owner_id)
    investigate(investigation_id, owner_id)
    again = await client.post(
        "/api/v1/investigations",
        headers={**await csrf_headers(client), "Idempotency-Key": f"spend-{suffix}"},
        json={},
    )
    assert again.json()["id"] == investigation_id
    body = (await client.get(f"/api/v1/investigations/{investigation_id}")).json()
    assert body["status"] == "published"
    assert body["live"] is False
    assert body["provider_mode"] == "fake"
    assert body["finding"]["amount"] == "430.00"
    assert body["finding"]["calculation_id"] == "net_spending"
    assert len(body["finding"]["evidence"]) == 3
    assert {row["amount"] for row in body["finding"]["evidence"]} == {"200.00", "50.00"}
    assert all(row["entry_type"] == "purchase" for row in body["finding"]["evidence"])
    assert all("closing_liability" not in row for row in body["finding"]["evidence"])
    assert len(body["statements"]) == 1
    assert body["statements"][0]["closing_liability"] == "1215.00"
    assert API_KEY not in json.dumps(body)
    assert FILE_PASSWORD not in json.dumps(body)
    for key in FORBIDDEN_KEYS:
        assert key not in json.dumps(body)
    with migrator.connect() as connection:
        blob = connection.execute(
            text("SELECT api_key_ciphertext FROM provider_profiles WHERE owner_id = :owner"),
            {"owner": owner_id},
        ).scalar_one()
        finding_count = connection.execute(
            text("SELECT count(*) FROM findings WHERE owner_id = :owner"),
            {"owner": owner_id},
        ).scalar_one()
    assert API_KEY.encode() not in bytes(blob)
    ring = parse_key_ring(get_settings().encryption_keys, get_settings().encryption_key_id)
    assert ring.decrypt(bytes(blob)).decode() == API_KEY
    assert finding_count == 1


async def test_narrow_consent_sends_nothing_and_other_users_see_nothing(application, migrator):
    from httpx import ASGITransport, AsyncClient

    suffix = uuid.uuid4().hex[:8]
    owner = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    other = AsyncClient(transport=ASGITransport(app=application), base_url="http://localhost:8080")
    try:
        await register(owner, f"scope{suffix}", f"scope{suffix}@example.com", PASSWORD)
        await register(other, f"outsider{suffix}", f"outsider{suffix}@example.com", PASSWORD)
        await owner.put(
            "/api/v1/provider",
            headers=await csrf_headers(owner),
            json={"endpoint": ENDPOINT, "model": "local-test", "consent": "none"},
        )
        refused = await owner.post("/api/v1/investigations", headers=await csrf_headers(owner), json={})
        assert refused.status_code == 403
        assert refused.json()["error"]["code"] == "no_consent"
        await owner.put(
            "/api/v1/provider",
            headers=await csrf_headers(owner),
            json={"endpoint": ENDPOINT, "model": "local-test", "consent": "summary"},
        )
        narrow = await owner.post("/api/v1/investigations", headers=await csrf_headers(owner), json={})
        assert narrow.status_code == 409
        assert narrow.json()["error"]["code"] == "consent_scope"
        owner_id = await _owner_id(owner)
        with migrator.connect() as connection:
            snapshots = connection.execute(
                text("SELECT count(*) FROM snapshots WHERE owner_id = :owner"),
                {"owner": owner_id},
            ).scalar_one()
        assert snapshots == 0
        missing = await other.get("/api/v1/investigations")
        assert missing.json()["investigations"] == []
        secret = await other.get("/api/v1/provider")
        assert secret.json()["provider"] is None
    finally:
        await owner.aclose()
        await other.aclose()
