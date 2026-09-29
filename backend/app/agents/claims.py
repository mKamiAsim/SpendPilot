"""Numeric claims publish only when they match a calculation id."""

from __future__ import annotations

from app.agents.finding import FindingRejected
from app.ledger.money import money


def validate_claims(snapshot: dict, claims: list[dict], scenario: dict | None) -> None:
    if not claims:
        raise FindingRejected("invalid_finding", "The briefing has no calculation.")
    seen = set()
    known = {row["id"] for row in snapshot["transactions"]} | {row["id"] for row in snapshot["cash_entries"]}
    income = money(snapshot["totals"]["income_total"])
    for claim in claims:
        calculation_id = claim.get("calculation_id")
        amount = claim.get("amount")
        evidence = claim.get("evidence_ids") or []
        if calculation_id in seen:
            raise FindingRejected("invalid_finding", "The briefing repeated a calculation.")
        seen.add(calculation_id)
        if not isinstance(evidence, list) or any(item not in known for item in evidence):
            raise FindingRejected("invented_evidence", "The briefing cited evidence that is not in the snapshot.")
        if calculation_id == "net_spending":
            if amount != snapshot["totals"]["net_spending"]:
                raise FindingRejected("invalid_finding", "Net spending does not match the snapshot.")
            if amount != "0.00" and not evidence:
                raise FindingRejected("invalid_finding", "A non-zero spending claim needs evidence.")
            continue
        if calculation_id == "category_reduction":
            if scenario is None or amount != scenario["proposed"]:
                raise FindingRejected("invalid_finding", "The category reduction does not match the calculation.")
            continue
        if calculation_id == "affordability":
            if income == 0 or scenario is None or scenario.get("affordability_blocked"):
                raise FindingRejected(
                    "income_missing",
                    "Missing income blocks an affordability claim.",
                )
            if amount != scenario["affordability_amount"]:
                raise FindingRejected("invalid_finding", "The affordability amount does not match the calculation.")
            continue
        raise FindingRejected("invalid_finding", "The briefing used an unknown calculation.")
