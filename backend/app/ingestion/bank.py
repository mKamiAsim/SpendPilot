"""Generic AED bank layout. It does not name or certify a bank."""

from __future__ import annotations

from datetime import date

from app.ingestion.adapter import ExtractedRow, ExtractedStatement, InvalidFixture
from app.ingestion.synthetic import write_lines_pdf
from app.ledger.money import money
from app.ledger.semantics import CATEGORIES, LIABILITY_DECREASE, LIABILITY_INCREASE

BANK_LAYOUT = "generic-aed-bank-v1"

BANK_LINES = [
    "SPENDPILOT SYNTHETIC FIXTURE",
    f"Layout: {BANK_LAYOUT}",
    "This is not a named bank.",
    "Account alias: Everyday current",
    "Account last4: 2200",
    "Period start: 2026-09-01",
    "Period end: 2026-09-30",
    "Opening liability: 5000.00",
    "Closing liability: 4700.00",
    "ROW | 2026-09-06 | transfer | Transfers | Card payment | 300.00",
]


def detect(text: str) -> bool:
    return f"Layout: {BANK_LAYOUT}" in text


def extract(text: str) -> ExtractedStatement:
    fields: dict[str, str] = {}
    rows: list[ExtractedRow] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("ROW |"):
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 6:
                raise InvalidFixture("A bank fixture row is incomplete.")
            _, posted, entry_type, category, description, amount = parts
            if category not in CATEGORIES:
                raise InvalidFixture(f"Unknown category {category}.")
            if entry_type not in LIABILITY_INCREASE | LIABILITY_DECREASE:
                raise InvalidFixture(f"Unknown entry type {entry_type}.")
            rows.append(
                ExtractedRow(
                    line_number=len(rows) + 1,
                    posted_on=date.fromisoformat(posted),
                    card_last4="",
                    entry_type=entry_type,
                    category=category,
                    description=description,
                    amount=money(amount),
                )
            )
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    try:
        return ExtractedStatement(
            layout=BANK_LAYOUT,
            kind="bank",
            account_alias=fields["Account alias"],
            account_last4=fields["Account last4"],
            period_start=date.fromisoformat(fields["Period start"]),
            period_end=date.fromisoformat(fields["Period end"]),
            opening_liability=money(fields["Opening liability"]),
            closing_liability=money(fields["Closing liability"]),
            card_last4s=(),
            rows=tuple(rows),
        )
    except KeyError as exc:
        raise InvalidFixture("The bank fixture is missing a required total.") from exc


def build_bank_pdf(*, password: str | None = None) -> bytes:
    return write_lines_pdf(BANK_LINES, password=password)
