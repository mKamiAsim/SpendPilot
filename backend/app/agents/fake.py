"""Deterministic provider for CI. It does not open a network connection."""

from __future__ import annotations

from app.agents.finding import FindingDraft
from app.agents.tools import call_tool


def fake_finding(snapshot: dict) -> tuple[FindingDraft, list[str]]:
    totals = call_tool(snapshot, "spending_total", {"user_id": "ignored"})
    listed = call_tool(snapshot, "list_transactions", {"owner_id": "ignored"})
    purchases = [row for row in listed["transactions"] if row["entry_type"] == "purchase"]
    amount = totals["net_spending"]
    activity = [
        "Read the spending total.",
        "Listed posted transactions.",
        "Checked the amount against net spending.",
    ]
    if amount == "0.00" and not purchases:
        draft = FindingDraft(
            title="No posted purchases are in this snapshot",
            explanation=(
                "There is no posted purchase to investigate. "
                "This is not a claim about a complete month."
            ),
            severity="note",
            evidence_ids=(),
            calculation_id="net_spending",
            amount=amount,
        )
        return draft, activity
    draft = FindingDraft(
        title=f"Posted net spending is {amount} AED",
        explanation=(
            "Net spending is purchases minus refunds, plus manual cash purchases. "
            "Payments, transfers, and cash withdrawals are not included. "
            "The amount is the spending total tool result."
        ),
        severity="note",
        evidence_ids=tuple(row["id"] for row in purchases),
        calculation_id="net_spending",
        amount=amount,
    )
    return draft, activity
