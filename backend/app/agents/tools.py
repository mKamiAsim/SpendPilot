"""Read-only tools. The model cannot choose an owner."""

from __future__ import annotations


def call_tool(snapshot: dict, name: str, arguments: dict | None) -> dict:
    payload = dict(arguments or {})
    payload.pop("user_id", None)
    payload.pop("owner_id", None)
    if payload:
        raise ValueError("This tool does not take arguments.")
    if name == "spending_total":
        return dict(snapshot["totals"])
    if name == "list_transactions":
        return {"transactions": list(snapshot["transactions"])}
    raise ValueError("Unknown tool.")
