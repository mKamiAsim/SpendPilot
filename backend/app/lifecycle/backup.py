"""User-passphrase backups. The server stores ciphertext and cannot read it later."""

from __future__ import annotations

import json
import os
import uuid
from datetime import date

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import EncryptionError, parse_key_ring
from app.ledger.money import money_str
from app.lifecycle.purge import purge_expired

AAD = b"spendpilot-backup-v1"
# 8 MiB of memory, one pass. Slow enough to resist a casual guess, fast enough for a self-hosted restore.
ARGON_TIME = 1
ARGON_MEMORY = 8192
ARGON_PARALLELISM = 1


class BackupError(Exception):
    pass


def seal_backup(payload: dict, passphrase: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext = AESGCM(_derive(passphrase, salt)).encrypt(nonce, raw, AAD)
    return bytes([1]) + salt + nonce + ciphertext


def open_backup(blob: bytes, passphrase: str) -> dict:
    if not isinstance(blob, (bytes, bytearray)) or len(blob) < 1 + 16 + 12 + 16 or blob[0] != 1:
        raise BackupError("This backup could not be read.")
    salt = bytes(blob[1:17])
    nonce = bytes(blob[17:29])
    ciphertext = bytes(blob[29:])
    try:
        raw = AESGCM(_derive(passphrase, salt)).decrypt(nonce, ciphertext, AAD)
    except (InvalidTag, ValueError) as exc:
        raise BackupError("This backup could not be read.") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BackupError("This backup could not be read.") from exc
    if not isinstance(payload, dict) or payload.get("product") != "SpendPilot":
        raise BackupError("This backup could not be read.")
    return payload


def _derive(passphrase: str, salt: bytes) -> bytes:
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=ARGON_TIME,
        memory_cost=ARGON_MEMORY,
        parallelism=ARGON_PARALLELISM,
        hash_len=32,
        type=Type.ID,
    )


async def export_payload(db: AsyncSession, *, include_secrets: bool) -> dict:
    payload = {
        "product": "SpendPilot",
        "include_secrets": include_secrets,
        "user_categories": await _names(db),
        "category_rules": await _rules(db),
        "cards": await _cards(db, include_secrets=include_secrets),
        "statements": await _statements(db),
        "posted_transactions": await _transactions(db),
        "cash_entries": await _cash(db),
        "memories": await _memories(db),
        "instalment_plans": await _plans(db),
        "instalment_repayments": await _repayments(db),
    }
    if include_secrets:
        payload["provider"] = await _provider_secret(db)
    return payload


async def restore_payload(db: AsyncSession, owner_id: uuid.UUID, payload: dict) -> None:
    """Apply a decrypted archive, then the retention cutoff. Caller holds one transaction."""

    accounts: dict[str, uuid.UUID] = {}
    cards: dict[tuple[str, str], uuid.UUID] = {}
    for card in _list(payload, "cards"):
        account_last4 = str(card["account_last4"])
        account_id = accounts.get(account_last4)
        if account_id is None:
            account_id = await _account(db, owner_id, str(card["account_alias"]), account_last4)
            accounts[account_last4] = account_id
        card_id = await _card(
            db,
            owner_id,
            account_id,
            str(card["alias"]),
            str(card["last4"]),
            str(card.get("status") or "active"),
            card.get("password") if payload.get("include_secrets") else None,
        )
        cards[(account_last4, str(card["last4"]))] = card_id
    for name in _list(payload, "user_categories"):
        await _insert_ignore(
            db,
            """
            INSERT INTO user_categories (id, owner_id, name)
            VALUES (:id, :owner_id, :name)
            ON CONFLICT (owner_id, name) DO NOTHING
            """,
            {"id": uuid.uuid4(), "owner_id": owner_id, "name": str(name)[:40]},
        )
    for rule in _list(payload, "category_rules"):
        await _insert_ignore(
            db,
            """
            INSERT INTO category_rules (id, owner_id, description, category)
            VALUES (:id, :owner_id, :description, :category)
            ON CONFLICT (owner_id, description) DO NOTHING
            """,
            {
                "id": uuid.uuid4(),
                "owner_id": owner_id,
                "description": str(rule["description"])[:500],
                "category": str(rule["category"])[:40],
            },
        )
    statements: dict[str, uuid.UUID] = {}
    for row in _list(payload, "statements"):
        source = _uuid(row["id"])
        account_id = await _account(db, owner_id, str(row["account_alias"]), str(row["account_last4"]))
        local = await _existing(db, "statements", owner_id, source)
        if local is None:
            local = uuid.uuid4()
            await db.execute(
                text(
                    """
                    INSERT INTO statements (
                        id, owner_id, document_id, account_id, period_start, period_end,
                        opening_liability, closing_liability, computed_closing, difference,
                        reconciliation, accept_reason, kind, source_id
                    ) VALUES (
                        :id, :owner_id, NULL, :account_id, :period_start, :period_end,
                        :opening_liability, :closing_liability, :computed_closing, :difference,
                        :reconciliation, :accept_reason, :kind, :source_id
                    )
                    """
                ),
                {
                    "id": local,
                    "owner_id": owner_id,
                    "account_id": account_id,
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                    "opening_liability": row["opening_liability"],
                    "closing_liability": row["closing_liability"],
                    "computed_closing": row["computed_closing"],
                    "difference": row["difference"],
                    "reconciliation": row["reconciliation"],
                    "accept_reason": row.get("accept_reason"),
                    "kind": row.get("kind") or "card",
                    "source_id": source,
                },
            )
        statements[str(source)] = local
    for row in _list(payload, "posted_transactions"):
        source = _uuid(row["id"])
        if await _existing(db, "posted_transactions", owner_id, source) is not None:
            continue
        statement_id = statements.get(str(row["statement_id"]))
        if statement_id is None:
            continue
        card_id = None
        if row.get("card_last4") and row.get("account_last4"):
            card_id = cards.get((str(row["account_last4"]), str(row["card_last4"])))
        await db.execute(
            text(
                """
                INSERT INTO posted_transactions (
                    id, owner_id, statement_id, card_id, line_number, posted_on,
                    description, category, entry_type, amount, source_page, source_id
                ) VALUES (
                    :id, :owner_id, :statement_id, :card_id, :line_number, :posted_on,
                    :description, :category, :entry_type, :amount, 1, :source_id
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "owner_id": owner_id,
                "statement_id": statement_id,
                "card_id": card_id,
                "line_number": int(row["line_number"]),
                "posted_on": row["posted_on"],
                "description": str(row["description"])[:500],
                "category": str(row["category"])[:40],
                "entry_type": row["entry_type"],
                "amount": row["amount"],
                "source_id": source,
            },
        )
    for row in _list(payload, "cash_entries"):
        await _copy_simple(
            db,
            owner_id,
            "cash_entries",
            _uuid(row["id"]),
            """
            INSERT INTO cash_entries (id, owner_id, posted_on, description, category, amount, source_id)
            VALUES (:id, :owner_id, :posted_on, :description, :category, :amount, :source_id)
            """,
            {
                "posted_on": row["posted_on"],
                "description": str(row["description"])[:200],
                "category": str(row["category"])[:40],
                "amount": row["amount"],
            },
        )
    for row in _list(payload, "memories"):
        await _copy_simple(
            db,
            owner_id,
            "memories",
            _uuid(row["id"]),
            """
            INSERT INTO memories (id, owner_id, kind, body, source_id, created_at)
            VALUES (:id, :owner_id, :kind, :body, :source_id, COALESCE(CAST(:created_at AS timestamptz), now()))
            """,
            {
                "kind": row["kind"],
                "body": str(row["body"])[:500],
                "created_at": row.get("created_at"),
            },
        )
    plans: dict[str, uuid.UUID] = {}
    for row in _list(payload, "instalment_plans"):
        source = _uuid(row["id"])
        local = await _existing(db, "instalment_plans", owner_id, source)
        if local is None:
            local = uuid.uuid4()
            await db.execute(
                text(
                    """
                    INSERT INTO instalment_plans (
                        id, owner_id, source_id, description, category, principal, parts, monthly_amount, posted_on
                    ) VALUES (
                        :id, :owner_id, :source_id, :description, :category, :principal, :parts, :monthly_amount, :posted_on
                    )
                    """
                ),
                {
                    "id": local,
                    "owner_id": owner_id,
                    "source_id": source,
                    "description": str(row["description"])[:200],
                    "category": str(row["category"])[:40],
                    "principal": row["principal"],
                    "parts": int(row["parts"]),
                    "monthly_amount": row["monthly_amount"],
                    "posted_on": row["posted_on"],
                },
            )
        plans[str(source)] = local
    for row in _list(payload, "instalment_repayments"):
        plan_id = plans.get(str(row["plan_id"]))
        if plan_id is None:
            continue
        source = _uuid(row["id"])
        if await _existing(db, "instalment_repayments", owner_id, source) is not None:
            continue
        await db.execute(
            text(
                """
                INSERT INTO instalment_repayments (id, owner_id, plan_id, source_id, posted_on, amount)
                VALUES (:id, :owner_id, :plan_id, :source_id, :posted_on, :amount)
                """
            ),
            {
                "id": uuid.uuid4(),
                "owner_id": owner_id,
                "plan_id": plan_id,
                "source_id": source,
                "posted_on": row["posted_on"],
                "amount": row["amount"],
            },
        )
    if payload.get("include_secrets") and isinstance(payload.get("provider"), dict):
        await _restore_provider(db, owner_id, payload["provider"])
    await purge_expired(db)


async def _names(db: AsyncSession) -> list[str]:
    result = await db.execute(text("SELECT name FROM user_categories ORDER BY name"))
    return [row[0] for row in result]


async def _rules(db: AsyncSession) -> list[dict]:
    result = await db.execute(text("SELECT description, category FROM category_rules ORDER BY description"))
    return [{"description": row[0], "category": row[1]} for row in result]


async def _cards(db: AsyncSession, *, include_secrets: bool) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT cards.alias, cards.last4, cards.status, cards.password_ciphertext,
                   card_accounts.alias AS account_alias, card_accounts.last4 AS account_last4
            FROM cards
            JOIN card_accounts ON card_accounts.id = cards.account_id
            ORDER BY cards.created_at, cards.id
            """
        )
    )
    rows = []
    for row in result.mappings():
        item = {
            "alias": row["alias"],
            "last4": row["last4"],
            "status": row["status"],
            "account_alias": row["account_alias"],
            "account_last4": row["account_last4"],
        }
        if include_secrets and row["password_ciphertext"] is not None:
            item["password"] = _decrypt(row["password_ciphertext"])
        rows.append(item)
    return rows


async def _statements(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT statements.id, statements.kind, statements.period_start, statements.period_end,
                   statements.opening_liability, statements.closing_liability, statements.computed_closing,
                   statements.difference, statements.reconciliation, statements.accept_reason,
                   card_accounts.alias AS account_alias, card_accounts.last4 AS account_last4
            FROM statements
            JOIN card_accounts ON card_accounts.id = statements.account_id
            ORDER BY statements.period_start, statements.id
            """
        )
    )
    return [_statement(row) for row in result.mappings()]


async def _transactions(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT posted_transactions.id, posted_transactions.statement_id, posted_transactions.line_number,
                   posted_transactions.posted_on, posted_transactions.description, posted_transactions.category,
                   posted_transactions.entry_type, posted_transactions.amount, cards.last4 AS card_last4,
                   card_accounts.last4 AS account_last4
            FROM posted_transactions
            JOIN statements ON statements.id = posted_transactions.statement_id
            JOIN card_accounts ON card_accounts.id = statements.account_id
            LEFT JOIN cards ON cards.id = posted_transactions.card_id
            ORDER BY posted_transactions.posted_on, posted_transactions.line_number
            """
        )
    )
    rows = []
    for row in result.mappings():
        rows.append(
            {
                "id": str(row["id"]),
                "statement_id": str(row["statement_id"]),
                "account_last4": row["account_last4"],
                "card_last4": row["card_last4"],
                "line_number": row["line_number"],
                "posted_on": _iso(row["posted_on"]),
                "description": row["description"],
                "category": row["category"],
                "entry_type": row["entry_type"],
                "amount": money_str(row["amount"]),
            }
        )
    return rows


async def _cash(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT id, posted_on, description, category, amount
            FROM cash_entries
            ORDER BY posted_on, id
            """
        )
    )
    return [
        {
            "id": str(row["id"]),
            "posted_on": _iso(row["posted_on"]),
            "description": row["description"],
            "category": row["category"],
            "amount": money_str(row["amount"]),
        }
        for row in result.mappings()
    ]


async def _memories(db: AsyncSession) -> list[dict]:
    result = await db.execute(text("SELECT id, kind, body, created_at FROM memories ORDER BY created_at, id"))
    return [
        {
            "id": str(row["id"]),
            "kind": row["kind"],
            "body": row["body"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in result.mappings()
    ]


async def _plans(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT id, description, category, principal, parts, monthly_amount, posted_on
            FROM instalment_plans
            ORDER BY posted_on, id
            """
        )
    )
    return [
        {
            "id": str(row["id"]),
            "description": row["description"],
            "category": row["category"],
            "principal": money_str(row["principal"]),
            "parts": row["parts"],
            "monthly_amount": money_str(row["monthly_amount"]),
            "posted_on": _iso(row["posted_on"]),
        }
        for row in result.mappings()
    ]


async def _repayments(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT id, plan_id, posted_on, amount
            FROM instalment_repayments
            ORDER BY posted_on, id
            """
        )
    )
    return [
        {
            "id": str(row["id"]),
            "plan_id": str(row["plan_id"]),
            "posted_on": _iso(row["posted_on"]),
            "amount": money_str(row["amount"]),
        }
        for row in result.mappings()
    ]


async def _provider_secret(db: AsyncSession) -> dict | None:
    row = (
        await db.execute(
            text("SELECT endpoint, model_name, api_key_ciphertext, consent FROM provider_profiles")
        )
    ).mappings().first()
    if row is None:
        return None
    return {
        "endpoint": row["endpoint"],
        "model": row["model_name"],
        "consent": row["consent"],
        "api_key": _decrypt(row["api_key_ciphertext"]) if row["api_key_ciphertext"] else None,
    }


async def _restore_provider(db: AsyncSession, owner_id: uuid.UUID, provider: dict) -> None:
    api_key = provider.get("api_key")
    ciphertext = _encrypt(api_key) if api_key else None
    await db.execute(
        text(
            """
            INSERT INTO provider_profiles (
                id, owner_id, endpoint, model_name, api_key_ciphertext, consent
            ) VALUES (
                :id, :owner_id, :endpoint, :model, :api_key, :consent
            )
            ON CONFLICT (owner_id) DO UPDATE SET
                endpoint = EXCLUDED.endpoint,
                model_name = EXCLUDED.model_name,
                api_key_ciphertext = EXCLUDED.api_key_ciphertext,
                consent = EXCLUDED.consent,
                updated_at = now()
            """
        ),
        {
            "id": uuid.uuid4(),
            "owner_id": owner_id,
            "endpoint": str(provider.get("endpoint") or "")[:300],
            "model": str(provider.get("model") or "")[:120],
            "api_key": ciphertext,
            "consent": provider.get("consent") if provider.get("consent") in {"none", "summary", "selected_transactions"} else "none",
        },
    )


def _decrypt(blob: bytes) -> str:
    settings = get_settings()
    ring = parse_key_ring(settings.encryption_keys, settings.encryption_key_id)
    return ring.decrypt(bytes(blob)).decode("utf-8")


def _encrypt(value: str) -> bytes:
    settings = get_settings()
    try:
        ring = parse_key_ring(settings.encryption_keys, settings.encryption_key_id)
    except EncryptionError as exc:
        raise BackupError("Saved secrets cannot be restored until an encryption key is configured.") from exc
    return ring.encrypt(value.encode("utf-8"))


async def _account(db: AsyncSession, owner_id: uuid.UUID, alias: str, last4: str) -> uuid.UUID:
    found = (
        await db.execute(text("SELECT id FROM card_accounts WHERE last4 = :last4"), {"last4": last4})
    ).scalar_one_or_none()
    if found is not None:
        return found
    account_id = uuid.uuid4()
    await db.execute(
        text(
            """
            INSERT INTO card_accounts (id, owner_id, alias, last4)
            VALUES (:id, :owner_id, :alias, :last4)
            """
        ),
        {"id": account_id, "owner_id": owner_id, "alias": alias[:80], "last4": last4},
    )
    return account_id


async def _card(
    db: AsyncSession,
    owner_id: uuid.UUID,
    account_id: uuid.UUID,
    alias: str,
    last4: str,
    status: str,
    password: str | None,
) -> uuid.UUID:
    found = (
        await db.execute(
            text("SELECT id FROM cards WHERE last4 = :last4 AND account_id = :account_id"),
            {"last4": last4, "account_id": account_id},
        )
    ).scalar_one_or_none()
    ciphertext = _encrypt(password) if password else None
    if found is not None:
        if ciphertext is not None:
            await db.execute(
                text("UPDATE cards SET password_ciphertext = :password WHERE id = :id"),
                {"password": ciphertext, "id": found},
            )
        return found
    card_id = uuid.uuid4()
    await db.execute(
        text(
            """
            INSERT INTO cards (id, owner_id, account_id, alias, last4, status, password_ciphertext)
            VALUES (:id, :owner_id, :account_id, :alias, :last4, :status, :password)
            """
        ),
        {
            "id": card_id,
            "owner_id": owner_id,
            "account_id": account_id,
            "alias": alias[:80],
            "last4": last4,
            "status": status if status in {"active", "closed"} else "active",
            "password": ciphertext,
        },
    )
    return card_id


async def _existing(db: AsyncSession, table: str, owner_id: uuid.UUID, source: uuid.UUID) -> uuid.UUID | None:
    if table not in {"statements", "posted_transactions", "cash_entries", "memories", "instalment_plans", "instalment_repayments"}:
        raise BackupError("This backup could not be read.")
    row = (
        await db.execute(
            text(
                f"""
                SELECT id FROM {table}
                WHERE owner_id = :owner_id AND (id = :source OR source_id = :source)
                """
            ),
            {"owner_id": owner_id, "source": source},
        )
    ).scalar_one_or_none()
    if row is not None and table != "posted_transactions":
        await db.execute(
            text(f"UPDATE {table} SET source_id = :source WHERE id = :id AND source_id IS NULL"),
            {"source": source, "id": row},
        )
    return row


async def _copy_simple(db: AsyncSession, owner_id: uuid.UUID, table: str, source: uuid.UUID, sql: str, values: dict) -> None:
    if await _existing(db, table, owner_id, source) is not None:
        return
    await db.execute(
        text(sql),
        {"id": uuid.uuid4(), "owner_id": owner_id, "source_id": source, **values},
    )


async def _insert_ignore(db: AsyncSession, sql: str, values: dict) -> None:
    await db.execute(text(sql), values)


def _statement(row) -> dict:
    return {
        "id": str(row["id"]),
        "kind": row["kind"],
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


def _list(payload: dict, key: str) -> list:
    value = payload.get(key) or []
    if not isinstance(value, list):
        raise BackupError("This backup could not be read.")
    return value


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise BackupError("This backup could not be read.") from exc


def _iso(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
