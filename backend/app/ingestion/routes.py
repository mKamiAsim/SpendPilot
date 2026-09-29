"""Batch upload. One bad password fails that file and leaves the rest of the batch alone."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.config import get_settings
from app.core.crypto import parse_key_ring
from app.core.errors import ApiError
from app.identity.routes import current_user
from app.ingestion.process import ReviewError, accept_document
from app.jobs.queue import defer_import
from app.ledger.money import money_str

router = APIRouter(prefix="/api/v1", tags=["imports"])
logger = logging.getLogger("spendpilot.ingestion")

MAX_BYTES = 15 * 1024 * 1024
MAX_FILES = 10


class AcceptBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def defer_quietly(document_id: str, owner_id: str) -> None:
    try:
        defer_import(document_id, owner_id)
    except Exception:
        logger.exception("import_defer_failed", extra={"document_id": document_id})


def _document_dict(row) -> dict:
    return {
        "id": str(row["id"]),
        "batch_id": str(row["batch_id"]),
        "original_name": row["original_name"],
        "status": row["status"],
        "failure_code": row["failure_code"],
        "failure_message": row["failure_message"],
    }


@router.post("/imports", status_code=202)
async def create_import(
    request: Request,
    files: list[UploadFile] = File(),
    passwords: str | None = Form(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    user, _session = await current_user(request)
    if user.email_verified_at is None:
        raise ApiError(403, "email_unverified", "Verify your email before importing a statement.")
    if not files or len(files) > MAX_FILES:
        raise ApiError(422, "invalid_request", "Upload between 1 and 10 PDF files.")
    parsed_passwords = _passwords(passwords, len(files))
    key = (idempotency_key or "").strip()[:200] or None
    db = request.state.db
    if key:
        existing = await db.scalar(
            text("SELECT id FROM import_batches WHERE idempotency_key = :key"),
            {"key": key},
        )
        if existing is not None:
            return await _batch_payload(db, existing)
    batch_id = uuid.uuid4()
    await db.execute(
        text("INSERT INTO import_batches (id, owner_id, idempotency_key) VALUES (:id, :owner_id, :key)"),
        {"id": batch_id, "owner_id": user.id, "key": key},
    )
    queued: list[str] = []
    for upload, password in zip(files, parsed_passwords, strict=True):
        payload = await _read_limited(upload)
        digest = hashlib.sha256(payload).hexdigest()
        document_id = uuid.uuid4()
        prior = await db.scalar(
            text(
                """
                SELECT id FROM source_documents
                WHERE content_hash = :digest AND status IN ('committed', 'needs_review')
                LIMIT 1
                """
            ),
            {"digest": digest},
        )
        status = "duplicate" if prior is not None else "queued"
        ciphertext = None
        if status == "queued" and password:
            ciphertext = _encrypt_password(password)
        name = Path(upload.filename or "statement.pdf").name[:180] or "statement.pdf"
        storage = _storage_path(user.id, document_id)
        storage.parent.mkdir(parents=True, exist_ok=True)
        storage.write_bytes(payload)
        await db.execute(
            text(
                """
                INSERT INTO source_documents (
                    id, owner_id, batch_id, original_name, content_hash, storage_path,
                    status, failure_code, failure_message, import_password_ciphertext
                ) VALUES (
                    :id, :owner_id, :batch_id, :name, :digest, :path,
                    :status, :failure_code, :failure_message, :password
                )
                """
            ),
            {
                "id": document_id,
                "owner_id": user.id,
                "batch_id": batch_id,
                "name": name,
                "digest": digest,
                "path": str(storage),
                "status": status,
                "failure_code": "duplicate" if status == "duplicate" else None,
                "failure_message": "This file was already imported. No rows were added." if status == "duplicate" else None,
                "password": ciphertext,
            },
        )
        if status == "queued":
            queued.append(str(document_id))
    request.state.pending_imports = [(document_id, str(user.id)) for document_id in queued]
    return await _batch_payload(db, batch_id)


@router.get("/imports/{batch_id}")
async def read_batch(batch_id: uuid.UUID, request: Request) -> dict:
    await current_user(request)
    found = await request.state.db.scalar(text("SELECT id FROM import_batches WHERE id = :id"), {"id": batch_id})
    if found is None:
        raise ApiError(404, "not_found", "That import batch does not exist.")
    return await _batch_payload(request.state.db, batch_id)


@router.get("/documents")
async def list_documents(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT id, batch_id, original_name, status, failure_code, failure_message
            FROM source_documents
            ORDER BY created_at DESC
            LIMIT 50
            """
        )
    )
    return {"documents": [_document_dict(row) for row in result.mappings()]}


@router.get("/review")
async def review_queue(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT id, original_name, failure_code, failure_message, extracted_json
            FROM source_documents
            WHERE status = 'needs_review'
            ORDER BY created_at
            """
        )
    )
    items = []
    for row in result.mappings():
        extracted = row["extracted_json"] or {}
        items.append(
            {
                "id": str(row["id"]),
                "original_name": row["original_name"],
                "failure_code": row["failure_code"],
                "failure_message": row["failure_message"],
                "closing_liability": extracted.get("closing_liability"),
                "computed_closing": extracted.get("computed_closing"),
                "difference": extracted.get("difference"),
                "row_count": len(extracted.get("rows") or []),
            }
        )
    return {"review": items}


@router.post("/review/{document_id}/accept")
async def accept_review(document_id: uuid.UUID, body: AcceptBody, request: Request) -> dict:
    user, _session = await current_user(request)
    try:
        return accept_document(str(user.id), str(document_id), body.reason)
    except ReviewError as exc:
        raise ApiError(exc.status_code, exc.code, exc.message) from exc


@router.get("/statements")
async def list_statements(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT statements.id, statements.document_id, statements.period_start, statements.period_end,
                   statements.opening_liability, statements.closing_liability, statements.computed_closing,
                   statements.difference, statements.reconciliation, statements.accept_reason,
                   card_accounts.alias AS account_alias, card_accounts.last4 AS account_last4
            FROM statements
            JOIN card_accounts ON card_accounts.id = statements.account_id
            ORDER BY statements.period_start, statements.created_at
            """
        )
    )
    statements = []
    for row in result.mappings():
        statements.append(
            {
                "id": str(row["id"]),
                "document_id": str(row["document_id"]),
                "account_alias": row["account_alias"],
                "account_last4": row["account_last4"],
                "period_start": row["period_start"].isoformat(),
                "period_end": row["period_end"].isoformat(),
                "opening_liability": money_str(row["opening_liability"]),
                "closing_liability": money_str(row["closing_liability"]),
                "computed_closing": money_str(row["computed_closing"]),
                "difference": money_str(row["difference"]),
                "reconciliation": row["reconciliation"],
                "accept_reason": row["accept_reason"],
            }
        )
    return {"statements": statements}


async def _batch_payload(db, batch_id) -> dict:
    result = await db.execute(
        text(
            """
            SELECT id, batch_id, original_name, status, failure_code, failure_message
            FROM source_documents
            WHERE batch_id = :batch_id
            ORDER BY created_at, original_name
            """
        ),
        {"batch_id": batch_id},
    )
    return {"batch_id": str(batch_id), "documents": [_document_dict(row) for row in result.mappings()]}


def _passwords(raw: str | None, count: int) -> list[str | None]:
    if raw is None or raw.strip() == "":
        return [None] * count
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(422, "invalid_request", "Passwords must be a JSON list aligned with the files.") from exc
    if not isinstance(parsed, list) or len(parsed) != count:
        raise ApiError(422, "invalid_request", "Passwords must be a JSON list aligned with the files.")
    cleaned: list[str | None] = []
    for item in parsed:
        if item is None or item == "":
            cleaned.append(None)
            continue
        if not isinstance(item, str) or len(item) > 128:
            raise ApiError(422, "invalid_request", "A PDF password must be 128 characters or fewer.")
        cleaned.append(item)
    return cleaned


async def _read_limited(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        block = await upload.read(1024 * 1024)
        if not block:
            break
        size += len(block)
        if size > MAX_BYTES:
            raise ApiError(413, "file_too_large", "Each PDF must be 15 MB or smaller.")
        chunks.append(block)
    if size == 0:
        raise ApiError(422, "invalid_request", "An uploaded file was empty.")
    return b"".join(chunks)


def _encrypt_password(password: str) -> bytes:
    settings = get_settings()
    if not settings.encryption_keys or not settings.encryption_key_id:
        raise ApiError(
            503,
            "encryption_unconfigured",
            "A PDF password cannot be saved until an encryption key is configured.",
        )
    return parse_key_ring(settings.encryption_keys, settings.encryption_key_id).encrypt(password.encode("utf-8"))


def _storage_path(owner_id: uuid.UUID, document_id: uuid.UUID) -> Path:
    root = Path(get_settings().file_storage_dir).resolve()
    path = (root / str(owner_id) / f"{document_id}.bin").resolve()
    if root not in path.parents:
        raise ApiError(500, "internal_error", "The file could not be stored.")
    return path
