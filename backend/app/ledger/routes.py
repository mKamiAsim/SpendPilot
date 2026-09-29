"""Manual cash purchases count once. They are not a second copy of a card withdrawal."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from app.core.errors import ApiError
from app.identity.routes import current_user
from app.ledger.money import money, money_str
from app.lifecycle.routes import category_allowed

router = APIRouter(prefix="/api/v1", tags=["ledger"])


class CashBody(BaseModel):
    posted_on: str
    description: str = Field(min_length=1, max_length=200)
    category: str
    amount: str

    @field_validator("posted_on")
    @classmethod
    def day(cls, value: str) -> str:
        from datetime import date

        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Enter a date as YYYY-MM-DD.") from exc
        return value

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, value: str) -> str:
        try:
            parsed = money(value)
        except Exception as exc:
            raise ValueError("Enter an amount.") from exc
        if parsed <= 0:
            raise ValueError("Enter an amount greater than zero.")
        return money_str(parsed)


@router.get("/transactions")
async def list_transactions(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT posted_transactions.id, posted_transactions.statement_id, posted_transactions.posted_on,
                   posted_transactions.description, posted_transactions.category,
                   posted_transactions.entry_type, posted_transactions.amount,
                   posted_transactions.line_number, cards.last4 AS card_last4
            FROM posted_transactions
            LEFT JOIN cards ON cards.id = posted_transactions.card_id
            ORDER BY posted_transactions.posted_on, posted_transactions.line_number
            LIMIT 200
            """
        )
    )
    rows = []
    for row in result.mappings():
        rows.append(
            {
                "id": str(row["id"]),
                "statement_id": str(row["statement_id"]) if row["statement_id"] else None,
                "posted_on": row["posted_on"].isoformat(),
                "description": row["description"],
                "category": row["category"],
                "entry_type": row["entry_type"],
                "amount": money_str(row["amount"]),
                "line_number": row["line_number"],
                "card_last4": row["card_last4"],
            }
        )
    return {"transactions": rows}


@router.post("/cash-entries", status_code=201)
async def create_cash_entry(body: CashBody, request: Request) -> dict:
    user, _session = await current_user(request)
    if not await category_allowed(request.state.db, body.category):
        raise ApiError(422, "invalid_request", "Choose a category from the v1 list or one you added.")
    entry_id = uuid.uuid4()
    await request.state.db.execute(
        text(
            """
            INSERT INTO cash_entries (id, owner_id, posted_on, description, category, amount)
            VALUES (:id, :owner_id, :posted_on, :description, :category, :amount)
            """
        ),
        {
            "id": entry_id,
            "owner_id": user.id,
            "posted_on": body.posted_on,
            "description": body.description.strip(),
            "category": body.category,
            "amount": body.amount,
        },
    )
    return {
        "id": str(entry_id),
        "posted_on": body.posted_on,
        "description": body.description.strip(),
        "category": body.category,
        "amount": body.amount,
    }
