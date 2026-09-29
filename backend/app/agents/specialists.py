"""Specialist roles. They are not servers, and a short question does not call them."""

from __future__ import annotations

from app.agents.limits import MAX_DELEGATION_DEPTH, MAX_PARALLEL_SPECIALISTS, Budget, ReviewLimit
from app.agents.tools import call_tool
from app.scenarios.calc import largest_reduction

MONTHLY_ROLES = ("behaviour", "scenario")


def plan_roles(kind: str) -> list[str]:
    if kind == "question":
        return []
    if kind == "monthly":
        return list(MONTHLY_ROLES)
    raise ReviewLimit("plan", "That review kind is not available.")


def run_wave(names: list[str], snapshot: dict, budget: Budget, depth: int) -> dict:
    if depth < 1 or depth > MAX_DELEGATION_DEPTH:
        raise ReviewLimit("depth", "Delegation depth cannot pass 2.")
    if len(names) > MAX_PARALLEL_SPECIALISTS:
        raise ReviewLimit("parallel", "Only two specialists can run at once.")
    if not names:
        return {"specialists": [], "scenario": None, "claims": []}
    budget.charge(len(names))
    claims: list[dict] = []
    scenario = None
    for name in names:
        if name == "behaviour":
            claims.append(_behaviour(snapshot, budget))
        elif name == "scenario":
            scenario = _scenario(snapshot, budget)
            if scenario is not None:
                claims.append(
                    {
                        "calculation_id": "category_reduction",
                        "amount": scenario["proposed"],
                        "evidence_ids": scenario["evidence_ids"],
                    }
                )
                if not scenario["affordability_blocked"]:
                    claims.append(
                        {
                            "calculation_id": "affordability",
                            "amount": scenario["affordability_amount"],
                            "evidence_ids": [],
                        }
                    )
        elif name == "obligations":
            budget.charge(1)
        else:
            raise ReviewLimit("plan", "Unknown specialist.")
    if depth < MAX_DELEGATION_DEPTH:
        pass
    return {"specialists": list(names), "scenario": scenario, "claims": claims}


def _behaviour(snapshot: dict, budget: Budget) -> dict:
    budget.charge(2)
    totals = call_tool(snapshot, "spending_total", {"user_id": "ignored"})
    listed = call_tool(snapshot, "list_transactions", {"owner_id": "ignored"})
    evidence = [row["id"] for row in listed["transactions"] if row["entry_type"] == "purchase"]
    return {
        "calculation_id": "net_spending",
        "amount": totals["net_spending"],
        "evidence_ids": evidence,
    }


def _scenario(snapshot: dict, budget: Budget) -> dict | None:
    budget.charge(1)
    return largest_reduction(snapshot)
