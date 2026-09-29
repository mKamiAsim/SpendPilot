"""Import one stored PDF. A second run of the same document does not add rows."""

from __future__ import annotations

import logging
import uuid
from datetime import date
from pathlib import Path

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.core.config import Settings, get_settings
from app.core.crypto import EncryptionError, parse_key_ring
from app.ingestion.adapter import InvalidFixture, UnsupportedLayout, extract
from app.ingestion.extract import DecryptError, OcrError, read_statement_text
from app.jobs.queue import conninfo
from app.ledger.money import TOLERANCE, money, money_str
from app.ledger.semantics import CATEGORIES, LIABILITY_DECREASE, LIABILITY_INCREASE

logger = logging.getLogger("spendpilot.ingestion")


class ReviewError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def process_document(document_id: str, owner_id: str) -> None:
    settings = get_settings()
    with psycopg.connect(conninfo(settings.database_url_app), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.owner_id', %s, true)", (owner_id,))
            document = conn.execute(
                """
                SELECT id, content_hash, storage_path, status, import_password_ciphertext
                FROM source_documents
                WHERE id = %s
                FOR UPDATE
                """,
                (document_id,),
            ).fetchone()
            if document is None or document["status"] != "queued":
                return
            _process_locked(conn, document, settings)


def accept_document(owner_id: str, document_id: str, reason: str) -> dict:
    cleaned = reason.strip()
    if not cleaned or len(cleaned) > 500:
        raise ReviewError(422, "reason_required", "Enter a reason before accepting this file.")
    settings = get_settings()
    with psycopg.connect(conninfo(settings.database_url_app), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.owner_id', %s, true)", (owner_id,))
            document = conn.execute(
                """
                SELECT id, status, extracted_json
                FROM source_documents
                WHERE id = %s
                FOR UPDATE
                """,
                (document_id,),
            ).fetchone()
            if document is None:
                raise ReviewError(404, "not_found", "That file is not in the review queue.")
            existing = _statement_row(conn, document_id)
            if document["status"] == "committed" and existing is not None:
                return _statement_dict(existing)
            if document["status"] != "needs_review" or not document["extracted_json"]:
                raise ReviewError(409, "not_reviewable", "This file cannot be accepted.")
            payload = document["extracted_json"]
            try:
                _commit_payload(
                    conn,
                    document_id=document_id,
                    payload=payload,
                    reconciliation="accepted_discrepancy",
                    accept_reason=cleaned,
                    allow_overlap=True,
                )
            except _NeedsReview as exc:
                raise ReviewError(409, exc.code, exc.message) from exc
            row = _statement_row(conn, document_id)
            if row is None:
                raise ReviewError(409, "not_reviewable", "This file cannot be accepted.")
            return _statement_dict(row)


class _NeedsReview(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _process_locked(conn: psycopg.Connection, document: dict, settings: Settings) -> None:
    document_id = str(document["id"])
    try:
        path = _safe_path(settings, document["storage_path"])
        text = _read_text(conn, path, document["import_password_ciphertext"])
    except DecryptError as exc:
        code = "too_many_pages" if "30 pages" in str(exc) else "wrong_password"
        _fail(conn, document_id, code, _public_failure(code))
        return
    except OcrError:
        _fail(conn, document_id, "no_text", "This scanned page produced no text.")
        return
    except EncryptionError:
        _fail(conn, document_id, "encryption_unconfigured", "The saved password could not be read.")
        return
    except OSError:
        _fail(conn, document_id, "unreadable", "The file could not be read.")
        return
    except Exception:
        logger.exception("extract_failed", extra={"document_id": document_id})
        _fail(conn, document_id, "unreadable", "The file could not be read.")
        return

    if not text.strip():
        _fail(conn, document_id, "no_text", "This scanned page produced no text.")
        return
    try:
        extracted = extract(text)
    except UnsupportedLayout:
        _fail(conn, document_id, "unsupported_layout", "This layout is not supported. No rows were added.")
        return
    except InvalidFixture:
        _fail(conn, document_id, "invalid_fixture", "The synthetic fixture could not be read. No rows were added.")
        return

    duplicate = conn.execute(
        """
        SELECT id FROM source_documents
        WHERE content_hash = %s
          AND id <> %s
          AND status IN ('committed', 'needs_review')
        LIMIT 1
        """,
        (document["content_hash"], document_id),
    ).fetchone()
    if duplicate is not None:
        _mark_duplicate(conn, document_id)
        return

    try:
        payload = _payload(extracted)
    except InvalidFixture:
        _fail(conn, document_id, "invalid_fixture", "The synthetic fixture could not be read. No rows were added.")
        return
    try:
        _commit_payload(
            conn,
            document_id=document_id,
            payload=payload,
            reconciliation="verified",
            accept_reason=None,
            allow_overlap=False,
        )
    except _NeedsReview as exc:
        _review(conn, document_id, exc.code, exc.message, payload)
    except UniqueViolation:
        _mark_duplicate(conn, document_id)


def _commit_payload(
    conn: psycopg.Connection,
    *,
    document_id: str,
    payload: dict,
    reconciliation: str,
    accept_reason: str | None,
    allow_overlap: bool,
) -> None:
    owner = conn.execute("SELECT NULLIF(current_setting('app.owner_id', true), '')::uuid AS owner_id").fetchone()
    owner_value = owner["owner_id"] if owner else None
    if owner_value is None:
        raise _NeedsReview("unreadable", "The file could not be posted.")
    _apply_rules(conn, payload)
    account = conn.execute(
        "SELECT id FROM card_accounts WHERE last4 = %s",
        (payload["account_last4"],),
    ).fetchone()
    if account is None and payload.get("kind") == "bank":
        account_id = uuid.uuid4()
        conn.execute(
            """
            INSERT INTO card_accounts (id, owner_id, alias, last4)
            VALUES (%s, %s, %s, %s)
            """,
            (account_id, owner_value, payload["account_alias"], payload["account_last4"]),
        )
        account = {"id": account_id}
    if account is None:
        raise _NeedsReview("unknown_account", "Add the shared account before accepting this file.")
    cards: dict[str, uuid.UUID] = {}
    if payload.get("kind") != "bank":
        for row in payload["rows"]:
            last4 = row["card_last4"]
            if last4 in cards:
                continue
            card = conn.execute(
                "SELECT id FROM cards WHERE last4 = %s AND account_id = %s",
                (last4, account["id"]),
            ).fetchone()
            if card is None:
                raise _NeedsReview("unknown_card", "Add every card on the file before it can post.")
            cards[last4] = card["id"]
    if not allow_overlap:
        overlap = conn.execute(
            """
            SELECT id FROM statements
            WHERE account_id = %s
              AND period_start <= %s
              AND period_end >= %s
            LIMIT 1
            """,
            (account["id"], payload["period_end"], payload["period_start"]),
        ).fetchone()
        if overlap is not None:
            raise _NeedsReview(
                "overlapping_period",
                "This period is already on the shared account. No second statement was added.",
            )
    difference = money(payload["difference"])
    if reconciliation == "verified" and abs(difference) > TOLERANCE:
        raise _NeedsReview(
            "unreconciled",
            "The stated closing does not match the rows. Nothing was posted.",
        )
    statement_id = uuid.uuid4()
    try:
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO statements (
                    id, owner_id, document_id, account_id, period_start, period_end,
                    opening_liability, closing_liability, computed_closing, difference,
                    reconciliation, accept_reason, kind
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    statement_id,
                    owner_value,
                    document_id,
                    account["id"],
                    payload["period_start"],
                    payload["period_end"],
                    payload["opening_liability"],
                    payload["closing_liability"],
                    payload["computed_closing"],
                    payload["difference"],
                    reconciliation,
                    accept_reason,
                    payload.get("kind") or "card",
                ),
            )
            for row in payload["rows"]:
                conn.execute(
                    """
                    INSERT INTO posted_transactions (
                        id, owner_id, statement_id, card_id, line_number, posted_on,
                        description, category, entry_type, amount, source_page
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                    """,
                    (
                        uuid.uuid4(),
                        owner_value,
                        statement_id,
                        None if payload.get("kind") == "bank" else cards[row["card_last4"]],
                        row["line_number"],
                        row["posted_on"],
                        row["description"],
                        row["category"],
                        row["entry_type"],
                        row["amount"],
                    ),
                )
            conn.execute(
                """
                UPDATE source_documents
                SET status = 'committed',
                    failure_code = NULL,
                    failure_message = NULL,
                    import_password_ciphertext = NULL,
                    extracted_json = %s
                WHERE id = %s
                """,
                (Json(payload), document_id),
            )
            conn.execute(
                "INSERT INTO user_events (owner_id, body) VALUES (%s, %s)",
                (owner_value, "statement_posted"),
            )
    except UniqueViolation:
        _mark_duplicate(conn, document_id)


def _apply_rules(conn: psycopg.Connection, payload: dict) -> None:
    rules = {
        row["description"]: row["category"]
        for row in conn.execute("SELECT description, category FROM category_rules").fetchall()
    }
    custom = {row["name"] for row in conn.execute("SELECT name FROM user_categories").fetchall()}
    allowed = CATEGORIES | custom
    for row in payload["rows"]:
        replacement = rules.get(row["description"])
        if replacement in allowed:
            row["category"] = replacement


def _read_text(conn: psycopg.Connection, path: Path, ciphertext: bytes | None) -> str:
    """A supplied password is the only attempt. Otherwise try the file, then saved card passwords."""

    if ciphertext:
        settings = get_settings()
        ring = parse_key_ring(settings.encryption_keys, settings.encryption_key_id)
        password = ring.decrypt(ciphertext).decode("utf-8")
        return read_statement_text(path, password)
    try:
        return read_statement_text(path, None)
    except DecryptError:
        pass
    saved = conn.execute(
        """
        SELECT password_ciphertext
        FROM cards
        WHERE password_ciphertext IS NOT NULL
        ORDER BY created_at, id
        """
    ).fetchall()
    if not saved:
        raise DecryptError("The password was not accepted.")
    settings = get_settings()
    ring = parse_key_ring(settings.encryption_keys, settings.encryption_key_id)
    for row in saved:
        try:
            candidate = ring.decrypt(row["password_ciphertext"]).decode("utf-8")
        except EncryptionError:
            continue
        try:
            return read_statement_text(path, candidate)
        except DecryptError:
            continue
    raise DecryptError("The password was not accepted.")


def _payload(extracted) -> dict:
    computed = extracted.computed_closing()
    difference = money(extracted.closing_liability - computed)
    rows = []
    for row in extracted.rows:
        if row.entry_type not in LIABILITY_INCREASE | LIABILITY_DECREASE | {"unknown"}:
            raise InvalidFixture("Unknown entry type.")
        if row.category not in CATEGORIES:
            raise InvalidFixture("Unknown category.")
        rows.append(
            {
                "line_number": row.line_number,
                "posted_on": row.posted_on.isoformat(),
                "card_last4": row.card_last4,
                "entry_type": row.entry_type,
                "category": row.category,
                "description": row.description[:500],
                "amount": money_str(row.amount),
            }
        )
    return {
        "layout": extracted.layout,
        "kind": extracted.kind,
        "account_alias": extracted.account_alias,
        "account_last4": extracted.account_last4,
        "period_start": extracted.period_start.isoformat(),
        "period_end": extracted.period_end.isoformat(),
        "opening_liability": money_str(extracted.opening_liability),
        "closing_liability": money_str(extracted.closing_liability),
        "computed_closing": money_str(computed),
        "difference": money_str(difference),
        "rows": rows,
    }


def _fail(conn: psycopg.Connection, document_id: str, code: str, message: str) -> None:
    conn.execute(
        """
        UPDATE source_documents
        SET status = 'failed',
            failure_code = %s,
            failure_message = %s,
            import_password_ciphertext = NULL
        WHERE id = %s
        """,
        (code, message, document_id),
    )


def _review(conn: psycopg.Connection, document_id: str, code: str, message: str, payload: dict) -> None:
    conn.execute(
        """
        UPDATE source_documents
        SET status = 'needs_review',
            failure_code = %s,
            failure_message = %s,
            extracted_json = %s,
            import_password_ciphertext = NULL
        WHERE id = %s
        """,
        (code, message, Json(payload), document_id),
    )


def _mark_duplicate(conn: psycopg.Connection, document_id: str) -> None:
    conn.execute(
        """
        UPDATE source_documents
        SET status = 'duplicate',
            failure_code = 'duplicate',
            failure_message = 'This file was already imported. No rows were added.',
            import_password_ciphertext = NULL
        WHERE id = %s AND status = 'queued'
        """,
        (document_id,),
    )


def _public_failure(code: str) -> str:
    if code == "wrong_password":
        return "The password was not accepted."
    if code == "too_many_pages":
        return "The file has more than 30 pages."
    return "The file could not be read."


def _safe_path(settings: Settings, storage_path: str) -> Path:
    root = Path(settings.file_storage_dir).resolve()
    path = Path(storage_path).resolve()
    if path != root and root not in path.parents:
        raise OSError("storage path is outside the file directory")
    return path


def _statement_row(conn: psycopg.Connection, document_id: str) -> dict | None:
    return conn.execute(
        """
        SELECT statements.id, statements.document_id, statements.period_start, statements.period_end,
               statements.opening_liability, statements.closing_liability, statements.computed_closing,
               statements.difference, statements.reconciliation, statements.accept_reason,
               card_accounts.alias AS account_alias, card_accounts.last4 AS account_last4
        FROM statements
        JOIN card_accounts ON card_accounts.id = statements.account_id
        WHERE statements.document_id = %s
        """,
        (document_id,),
    ).fetchone()


def _statement_dict(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "document_id": str(row["document_id"]),
        "account_alias": row["account_alias"],
        "account_last4": row["account_last4"],
        "period_start": _iso(row["period_start"]),
        "period_end": _iso(row["period_end"]),
        "opening_liability": money_str(row["opening_liability"]),
        "closing_liability": money_str(row["closing_liability"]),
        "computed_closing": money_str(row["computed_closing"]),
        "difference": money_str(row["difference"]),
        "reconciliation": row["reconciliation"],
        "accept_reason": row["accept_reason"],
    }


def _iso(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
