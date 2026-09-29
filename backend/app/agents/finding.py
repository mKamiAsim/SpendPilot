"""A finding is published only when its amount and evidence match the snapshot."""

from __future__ import annotations

from dataclasses import dataclass


class FindingRejected(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class FindingDraft:
    title: str
    explanation: str
    severity: str
    evidence_ids: tuple[str, ...]
    calculation_id: str
    amount: str


def draft_from_mapping(payload: dict) -> FindingDraft:
    try:
        evidence = payload["evidence_ids"]
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise TypeError
        return FindingDraft(
            title=str(payload["title"])[:200],
            explanation=str(payload["explanation"])[:2000],
            severity=str(payload["severity"]),
            evidence_ids=tuple(evidence),
            calculation_id=str(payload["calculation_id"]),
            amount=str(payload["amount"]),
        )
    except (KeyError, TypeError) as exc:
        raise FindingRejected("invalid_finding", "The finding did not match the required shape.") from exc


def validate_finding(snapshot: dict, draft: FindingDraft) -> None:
    if draft.severity not in {"note", "attention", "watch"}:
        raise FindingRejected("invalid_finding", "The finding severity was not recognised.")
    if draft.calculation_id != "net_spending":
        raise FindingRejected("invalid_finding", "The finding did not use the net spending calculation.")
    if draft.amount != snapshot["totals"]["net_spending"]:
        raise FindingRejected("invalid_finding", "The finding amount does not match net spending.")
    if not draft.title.strip() or not draft.explanation.strip():
        raise FindingRejected("invalid_finding", "The finding was empty.")
    known = {row["id"] for row in snapshot["transactions"]} | {row["id"] for row in snapshot["cash_entries"]}
    if any(item not in known for item in draft.evidence_ids):
        raise FindingRejected("invented_evidence", "The finding cited evidence that is not in the snapshot.")
    purchases = [row for row in snapshot["transactions"] if row["entry_type"] == "purchase"]
    if draft.amount != "0.00" and not draft.evidence_ids:
        raise FindingRejected("invalid_finding", "A non-zero spending finding needs evidence from the snapshot.")
    if draft.amount == "0.00" and not purchases and draft.evidence_ids:
        raise FindingRejected("invalid_finding", "An empty snapshot cannot cite evidence.")
