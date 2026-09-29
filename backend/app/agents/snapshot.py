"""Freeze the rows an investigation may cite. Later writes do not change it."""

from __future__ import annotations

import uuid
from decimal import Decimal

import psycopg
from psycopg.types.json import Json

from app.ledger.money import money, money_str

FORBIDDEN_KEYS = frozenset(
    {
        "password",
        "password_ciphertext",
        "import_password_ciphertext",
        "api_key",
        "api_key_ciphertext",
        "storage_path",
        "content_hash",
        "owner_id",
        "user_id",
    }
)


def freeze_snapshot(conn: psycopg.Connection, *, consent: str, consent_version: int) -> tuple[str, dict]:
    transactions = [
        _transaction(row)
        for row in conn.execute(
            """
            SELECT posted_transactions.id, posted_transactions.posted_on, posted_transactions.description,
                   posted_transactions.category, posted_transactions.entry_type, posted_transactions.amount,
                   cards.last4 AS card_last4
            FROM posted_transactions
            LEFT JOIN cards ON cards.id = posted_transactions.card_id
            ORDER BY posted_transactions.posted_on, posted_transactions.line_number
            """
        ).fetchall()
    ]
    cash_entries = [
        {
            "id": str(row["id"]),
            "posted_on": row["posted_on"].isoformat(),
            "description": row["description"],
            "category": row["category"],
            "amount": money_str(row["amount"]),
        }
        for row in conn.execute(
            """
            SELECT id, posted_on, description, category, amount
            FROM cash_entries
            ORDER BY posted_on, created_at
            """
        ).fetchall()
    ]
    statements = [
        {
            "id": str(row["id"]),
            "period_start": row["period_start"].isoformat(),
            "period_end": row["period_end"].isoformat(),
            "closing_liability": money_str(row["closing_liability"]),
            "reconciliation": row["reconciliation"],
        }
        for row in conn.execute(
            """
            SELECT id, period_start, period_end, closing_liability, reconciliation
            FROM statements
            ORDER BY period_start, created_at
            """
        ).fetchall()
    ]
    body = {
        "transactions": transactions,
        "cash_entries": cash_entries,
        "statements": statements,
        "totals": totals_for(transactions, cash_entries, statements),
    }
    _reject_forbidden(body)
    owner = conn.execute(
        "SELECT NULLIF(current_setting('app.owner_id', true), '')::uuid AS owner_id"
    ).fetchone()
    snapshot_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO snapshots (id, owner_id, consent, consent_version, body)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (snapshot_id, owner["owner_id"], consent, consent_version, Json(body)),
    )
    return str(snapshot_id), body


def totals_for(transactions: list[dict], cash_entries: list[dict], statements: list[dict]) -> dict:
    def summed(entry_type: str) -> Decimal:
        return money(sum((money(row["amount"]) for row in transactions if row["entry_type"] == entry_type), Decimal("0")))

    purchases = summed("purchase")
    refunds = summed("refund")
    cash = money(sum((money(row["amount"]) for row in cash_entries), Decimal("0")))
    flagged = any(row["reconciliation"] == "accepted_discrepancy" for row in statements)
    return {
        "gross_purchases": money_str(purchases),
        "refunds": money_str(refunds),
        "cash_purchases": money_str(cash),
        "net_spending": money_str(purchases - refunds + cash),
        "fees": money_str(summed("fee")),
        "payments": money_str(summed("payment")),
        "transfers": money_str(summed("transfer")),
        "cash_withdrawals": money_str(summed("cash_withdrawal")),
        "includes_accepted_discrepancy": flagged,
    }


def _transaction(row) -> dict:
    return {
        "id": str(row["id"]),
        "posted_on": row["posted_on"].isoformat(),
        "description": row["description"],
        "category": row["category"],
        "entry_type": row["entry_type"],
        "amount": money_str(row["amount"]),
        "card_last4": row["card_last4"],
    }


def _reject_forbidden(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                raise RuntimeError("The snapshot included a forbidden field.")
            _reject_forbidden(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden(item)
