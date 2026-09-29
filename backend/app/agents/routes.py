"""Provider profile and one evidence-backed investigation."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agents.openai_client import probe_endpoint
from app.core.config import get_settings
from app.core.crypto import parse_key_ring
from app.core.errors import ApiError
from app.core.ssrf import SsrfError, SsrfPolicy, validate_endpoint
from app.identity.routes import current_user
from app.jobs.queue import defer_investigation

router = APIRouter(prefix="/api/v1", tags=["advisor"])
logger = logging.getLogger("spendpilot.agents")

QUESTION = "What is posted net spending, and which purchases support it?"


class ProviderBody(BaseModel):
    endpoint: str = Field(min_length=1, max_length=300)
    model: str = Field(min_length=1, max_length=120)
    api_key: str | None = Field(default=None, max_length=256)
    consent: str


class InvestigationBody(BaseModel):
    question: str | None = Field(default=None, max_length=500)


def defer_investigation_quietly(investigation_id: str, owner_id: str) -> None:
    try:
        defer_investigation(investigation_id, owner_id)
    except Exception:
        logger.exception("investigation_defer_failed", extra={"investigation_id": investigation_id})


@router.get("/provider")
async def read_provider(request: Request) -> dict:
    await current_user(request)
    row = (
        await request.state.db.execute(
            text(
                """
                SELECT endpoint, model_name, api_key_ciphertext IS NOT NULL AS api_key_saved,
                       consent, consent_version, document_assistance
                FROM provider_profiles
                """
            )
        )
    ).mappings().first()
    if row is None:
        return {"provider": None, "live_provider": _live_flag()}
    return {"provider": _provider_dict(row), "live_provider": _live_flag()}


@router.put("/provider")
async def save_provider(body: ProviderBody, request: Request) -> dict:
    user, _session = await current_user(request)
    if body.consent not in {"none", "summary", "selected_transactions"}:
        raise ApiError(422, "invalid_request", "Choose a consent level.")
    endpoint = body.endpoint.strip()
    try:
        validate_endpoint(endpoint, SsrfPolicy(get_settings().private_model_hosts))
    except SsrfError as exc:
        raise ApiError(422, "ssrf", str(exc)) from exc
    db = request.state.db
    existing = (
        await db.execute(
            text("SELECT id, consent, consent_version, api_key_ciphertext FROM provider_profiles")
        )
    ).mappings().first()
    ciphertext = existing["api_key_ciphertext"] if existing else None
    if body.api_key is not None:
        ciphertext = _encrypt_key(body.api_key) if body.api_key else None
    version = 1
    if existing is not None:
        version = existing["consent_version"] + (1 if existing["consent"] != body.consent else 0)
    profile_id = existing["id"] if existing else uuid.uuid4()
    await db.execute(
        text(
            """
            INSERT INTO provider_profiles (
                id, owner_id, endpoint, model_name, api_key_ciphertext, consent, consent_version
            ) VALUES (
                :id, :owner_id, :endpoint, :model, :api_key, :consent, :version
            )
            ON CONFLICT (owner_id) DO UPDATE SET
                endpoint = EXCLUDED.endpoint,
                model_name = EXCLUDED.model_name,
                api_key_ciphertext = EXCLUDED.api_key_ciphertext,
                consent = EXCLUDED.consent,
                consent_version = EXCLUDED.consent_version,
                updated_at = now()
            """
        ),
        {
            "id": profile_id,
            "owner_id": user.id,
            "endpoint": endpoint,
            "model": body.model.strip(),
            "api_key": ciphertext,
            "consent": body.consent,
            "version": version,
        },
    )
    row = (
        await db.execute(
            text(
                """
                SELECT endpoint, model_name, api_key_ciphertext IS NOT NULL AS api_key_saved,
                       consent, consent_version, document_assistance
                FROM provider_profiles
                """
            )
        )
    ).mappings().one()
    return {"provider": _provider_dict(row), "live_provider": _live_flag()}


@router.post("/provider/test")
async def test_provider(request: Request) -> dict:
    await current_user(request)
    settings = get_settings()
    if settings.provider_mode == "fake":
        return {
            "status": "ok",
            "live": False,
            "provider": "fake",
            "message": "Deterministic test provider. This is not a live model.",
        }
    row = (
        await request.state.db.execute(
            text("SELECT endpoint, model_name, api_key_ciphertext FROM provider_profiles")
        )
    ).mappings().first()
    if row is None:
        raise ApiError(409, "provider_required", "Save an endpoint before testing the connection.")
    api_key = _decrypt_key(row["api_key_ciphertext"])
    import httpx

    def send(url: str, key: str | None, body: dict) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            return client.post(url, headers=headers, json=body)

    result = probe_endpoint(
        row["endpoint"],
        api_key,
        row["model_name"],
        SsrfPolicy(settings.private_model_hosts),
        send,
    )
    return {"status": "ok" if result.ok else "failed", "live": True, "provider": "configured", "message": result.message}


@router.post("/investigations", status_code=202)
async def create_investigation(
    body: InvestigationBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    user, _session = await current_user(request)
    settings = get_settings()
    profile = (
        await request.state.db.execute(text("SELECT consent, endpoint FROM provider_profiles"))
    ).mappings().first()
    if profile is None:
        raise ApiError(409, "provider_required", "Save a provider and a consent level first.")
    if profile["consent"] == "none":
        raise ApiError(403, "no_consent", "SpendPilot will not send ledger details while consent is off.")
    if profile["consent"] != "selected_transactions":
        raise ApiError(
            409,
            "consent_scope",
            "This investigation needs consent for selected transaction details. Summary consent does not send rows.",
        )
    key = (idempotency_key or "").strip()[:200] or None
    if key:
        existing = await request.state.db.scalar(
            text("SELECT id FROM investigations WHERE idempotency_key = :key"),
            {"key": key},
        )
        if existing is not None:
            return await _investigation_payload(request.state.db, existing)
    investigation_id = uuid.uuid4()
    question = (body.question or QUESTION).strip() or QUESTION
    await request.state.db.execute(
        text(
            """
            INSERT INTO investigations (
                id, owner_id, idempotency_key, question, status, provider_mode
            ) VALUES (
                :id, :owner_id, :key, :question, 'queued', :mode
            )
            """
        ),
        {
            "id": investigation_id,
            "owner_id": user.id,
            "key": key,
            "question": question,
            "mode": settings.provider_mode,
        },
    )
    request.state.pending_investigations = [(str(investigation_id), str(user.id))]
    return await _investigation_payload(request.state.db, investigation_id)


@router.get("/investigations")
async def list_investigations(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT id FROM investigations
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
    )
    items = []
    for row in result.mappings():
        items.append(await _investigation_payload(request.state.db, row["id"]))
    return {"investigations": items}


@router.get("/investigations/{investigation_id}")
async def read_investigation(investigation_id: uuid.UUID, request: Request) -> dict:
    await current_user(request)
    found = await request.state.db.scalar(
        text("SELECT id FROM investigations WHERE id = :id"),
        {"id": investigation_id},
    )
    if found is None:
        raise ApiError(404, "not_found", "That investigation does not exist.")
    return await _investigation_payload(request.state.db, investigation_id)


def _provider_dict(row) -> dict:
    return {
        "endpoint": row["endpoint"],
        "model": row["model_name"],
        "api_key_saved": bool(row["api_key_saved"]),
        "consent": row["consent"],
        "consent_version": row["consent_version"],
        "document_assistance": False,
    }


def _live_flag() -> bool:
    return get_settings().provider_mode == "configured"


def _encrypt_key(api_key: str) -> bytes:
    settings = get_settings()
    if not settings.encryption_keys or not settings.encryption_key_id:
        raise ApiError(503, "encryption_unconfigured", "An API key cannot be saved until an encryption key is configured.")
    return parse_key_ring(settings.encryption_keys, settings.encryption_key_id).encrypt(api_key.encode("utf-8"))


def _decrypt_key(ciphertext: bytes | None) -> str | None:
    if not ciphertext:
        return None
    settings = get_settings()
    return parse_key_ring(settings.encryption_keys, settings.encryption_key_id).decrypt(ciphertext).decode("utf-8")


async def _investigation_payload(db, investigation_id) -> dict:
    row = (
        await db.execute(
            text(
                """
                SELECT investigations.id, investigations.question, investigations.status,
                       investigations.provider_mode, investigations.failure_code,
                       investigations.failure_message, investigations.activity, investigations.snapshot_id,
                       findings.id AS finding_id, findings.title, findings.explanation, findings.severity,
                       findings.evidence_ids, findings.calculation_id, findings.amount,
                       snapshots.body AS snapshot_body
                FROM investigations
                LEFT JOIN findings ON findings.investigation_id = investigations.id
                LEFT JOIN snapshots ON snapshots.id = investigations.snapshot_id
                WHERE investigations.id = :id
                """
            ),
            {"id": investigation_id},
        )
    ).mappings().one()
    finding = None
    statements = []
    if row["snapshot_body"]:
        statements = row["snapshot_body"].get("statements") or []
    if row["finding_id"] is not None:
        evidence_ids = set(row["evidence_ids"] or [])
        rows = (row["snapshot_body"] or {}).get("transactions") or []
        evidence = [item for item in rows if item["id"] in evidence_ids]
        finding = {
            "id": str(row["finding_id"]),
            "title": row["title"],
            "explanation": row["explanation"],
            "severity": row["severity"],
            "amount": row["amount"],
            "calculation_id": row["calculation_id"],
            "evidence": evidence,
        }
    return {
        "id": str(row["id"]),
        "question": row["question"],
        "status": row["status"],
        "provider_mode": row["provider_mode"],
        "live": row["provider_mode"] == "configured",
        "failure_code": row["failure_code"],
        "failure_message": row["failure_message"],
        "activity": row["activity"] or [],
        "statements": statements,
        "finding": finding,
    }
