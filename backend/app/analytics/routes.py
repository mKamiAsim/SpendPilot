"""Posted totals. Payments, transfers, and cash withdrawals are not spending."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.identity.routes import current_user
from app.ledger.money import money, money_str

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary")
async def summary(request: Request) -> dict:
    await current_user(request)
    db = request.state.db
    totals = (
        await db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(amount) FILTER (WHERE entry_type = 'purchase'), 0) AS gross_purchases,
                    COALESCE(SUM(amount) FILTER (WHERE entry_type = 'refund'), 0) AS refunds,
                    COALESCE(SUM(amount) FILTER (WHERE entry_type = 'fee'), 0) AS fees,
                    COALESCE(SUM(amount) FILTER (WHERE entry_type = 'interest'), 0) AS interest,
                    COALESCE(SUM(amount) FILTER (WHERE entry_type = 'payment'), 0) AS payments,
                    COALESCE(SUM(amount) FILTER (WHERE entry_type = 'transfer'), 0) AS transfers,
                    COALESCE(SUM(amount) FILTER (WHERE entry_type = 'cash_withdrawal'), 0) AS cash_withdrawals,
                    COALESCE(SUM(amount) FILTER (WHERE entry_type = 'cashback'), 0) AS cashback
                FROM posted_transactions
                """
            )
        )
    ).mappings().one()
    cash = await db.scalar(text("SELECT COALESCE(SUM(amount), 0) FROM cash_entries"))
    statement_count = int(await db.scalar(text("SELECT count(*) FROM statements")) or 0)
    flagged = bool(
        await db.scalar(
            text("SELECT EXISTS(SELECT 1 FROM statements WHERE reconciliation = 'accepted_discrepancy')")
        )
    )
    purchases = money(totals["gross_purchases"])
    refunds = money(totals["refunds"])
    cash_purchases = money(cash or 0)
    return {
        "gross_purchases": money_str(purchases),
        "refunds": money_str(refunds),
        "cash_purchases": money_str(cash_purchases),
        "net_spending": money_str(purchases - refunds + cash_purchases),
        "fees": money_str(totals["fees"]),
        "interest": money_str(totals["interest"]),
        "payments": money_str(totals["payments"]),
        "transfers": money_str(totals["transfers"]),
        "cash_withdrawals": money_str(totals["cash_withdrawals"]),
        "cashback": money_str(totals["cashback"]),
        "statement_count": statement_count,
        "includes_accepted_discrepancy": flagged,
    }
