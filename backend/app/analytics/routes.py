"""Posted totals. Payments, transfers, and cash withdrawals are not spending."""

from __future__ import annotations

import calendar
from datetime import date

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
    cash = await db.scalar(
        text("SELECT COALESCE(SUM(amount) FILTER (WHERE category <> 'Income'), 0) FROM cash_entries")
    )
    instalments = await db.scalar(text("SELECT COALESCE(SUM(principal), 0) FROM instalment_plans"))
    statement_count = int(await db.scalar(text("SELECT count(*) FROM statements")) or 0)
    flagged = bool(
        await db.scalar(
            text("SELECT EXISTS(SELECT 1 FROM statements WHERE reconciliation = 'accepted_discrepancy')")
        )
    )
    purchases = money(totals["gross_purchases"])
    refunds = money(totals["refunds"])
    cash_purchases = money(cash or 0)
    instalment_purchases = money(instalments or 0)
    return {
        "gross_purchases": money_str(purchases),
        "refunds": money_str(refunds),
        "cash_purchases": money_str(cash_purchases),
        "instalment_purchases": money_str(instalment_purchases),
        "net_spending": money_str(purchases - refunds + cash_purchases + instalment_purchases),
        "fees": money_str(totals["fees"]),
        "interest": money_str(totals["interest"]),
        "payments": money_str(totals["payments"]),
        "transfers": money_str(totals["transfers"]),
        "cash_withdrawals": money_str(totals["cash_withdrawals"]),
        "cashback": money_str(totals["cashback"]),
        "statement_count": statement_count,
        "includes_accepted_discrepancy": flagged,
    }


@router.get("/coverage")
async def coverage(request: Request) -> dict:
    """Missing and partial months stay visible. One month is not complete coverage."""

    await current_user(request)
    result = await request.state.db.execute(text("SELECT period_start, period_end FROM statements"))
    periods = list(result.mappings())
    months: set[str] = set()
    partial: list[dict] = []
    for row in periods:
        start = row["period_start"]
        end = row["period_end"]
        cursor = date(start.year, start.month, 1)
        last = date(end.year, end.month, 1)
        while cursor <= last:
            months.add(f"{cursor.year:04d}-{cursor.month:02d}")
            cursor = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)
        month_end = calendar.monthrange(end.year, end.month)[1]
        full = start.day == 1 and end.day == month_end and (start.year, start.month) == (end.year, end.month)
        if not full:
            partial.append({"period_start": start.isoformat(), "period_end": end.isoformat()})
    ordered = sorted(months)
    gaps: list[str] = []
    if ordered:
        year, month = (int(part) for part in ordered[0].split("-"))
        end_year, end_month = (int(part) for part in ordered[-1].split("-"))
        while (year, month) <= (end_year, end_month):
            key = f"{year:04d}-{month:02d}"
            if key not in months:
                gaps.append(key)
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
    complete = len(months) >= 12 and not gaps and not partial
    note = (
        "Twelve continuous full months are posted."
        if complete
        else "Missing months are visible. This is not complete coverage."
    )
    return {
        "complete": complete,
        "months_covered": len(months),
        "gaps": gaps,
        "partial_periods": partial,
        "note": note,
    }
