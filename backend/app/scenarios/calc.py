"""Scenario arithmetic. The model does not supply the numbers."""

from __future__ import annotations

from decimal import Decimal

from app.ledger.money import money, money_str
from app.ledger.semantics import CATEGORIES


def _clean(arguments: dict | None) -> dict:
    payload = dict(arguments or {})
    payload.pop("user_id", None)
    payload.pop("owner_id", None)
    payload.pop("status", None)
    return payload


def calculate_scenario(snapshot: dict, arguments: dict | None) -> dict:
    payload = _clean(arguments)
    category = payload.get("category")
    if category not in CATEGORIES or category == "Income":
        raise ValueError("Choose a spending category.")
    try:
        requested = money(str(payload.get("reduction")))
    except Exception as exc:
        raise ValueError("Enter a reduction amount.") from exc
    if requested <= 0:
        raise ValueError("Enter a reduction greater than zero.")
    baseline = _category_baseline(snapshot, category)
    reduction = requested if requested <= baseline else baseline
    proposed = money(baseline - reduction)
    income = money(snapshot["totals"]["income_total"])
    net = money(snapshot["totals"]["net_spending"])
    blocked = income == 0
    affordability = None if blocked else money_str(money(income - (net - reduction)))
    evidence = [
        row["id"]
        for row in snapshot["transactions"]
        if row["entry_type"] == "purchase" and row["category"] == category
    ]
    evidence.extend(row["id"] for row in snapshot["cash_entries"] if row["category"] == category)
    return {
        "category": category,
        "baseline": money_str(baseline),
        "reduction": money_str(reduction),
        "proposed": money_str(proposed),
        "calculation_id": "category_reduction",
        "income_total": money_str(income),
        "affordability_amount": affordability,
        "affordability_blocked": blocked,
        "evidence_ids": evidence,
    }


def largest_reduction(snapshot: dict) -> dict | None:
    totals: dict[str, Decimal] = {}
    for row in snapshot["transactions"]:
        if row["entry_type"] != "purchase":
            continue
        totals[row["category"]] = totals.get(row["category"], Decimal("0")) + money(row["amount"])
    for row in snapshot["cash_entries"]:
        if row["category"] == "Income":
            continue
        totals[row["category"]] = totals.get(row["category"], Decimal("0")) + money(row["amount"])
    if not totals:
        return None
    best = max(totals.values())
    category = sorted(name for name, amount in totals.items() if amount == best)[0]
    requested = money("10.00") if best >= money("10.00") else best
    return calculate_scenario(snapshot, {"category": category, "reduction": money_str(requested)})


def _category_baseline(snapshot: dict, category: str) -> Decimal:
    total = Decimal("0")
    for row in snapshot["transactions"]:
        if row["entry_type"] == "purchase" and row["category"] == category:
            total += money(row["amount"])
    for row in snapshot["cash_entries"]:
        if row["category"] == category:
            total += money(row["amount"])
    return money(total)
