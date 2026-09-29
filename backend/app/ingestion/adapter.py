"""Generic AED card layout. No bank is named or certified."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.ingestion.synthetic import LAYOUT
from app.ledger.money import money
from app.ledger.semantics import CATEGORIES, LIABILITY_DECREASE, LIABILITY_INCREASE


@dataclass(frozen=True)
class ExtractedRow:
    line_number: int
    posted_on: date
    card_last4: str
    entry_type: str
    category: str
    description: str
    amount: Decimal


@dataclass(frozen=True)
class ExtractedStatement:
    layout: str
    account_alias: str
    account_last4: str
    period_start: date
    period_end: date
    opening_liability: Decimal
    closing_liability: Decimal
    card_last4s: tuple[str, ...]
    rows: tuple[ExtractedRow, ...]
    kind: str = "card"

    def computed_closing(self) -> Decimal:
        total = self.opening_liability
        for row in self.rows:
            if row.entry_type in LIABILITY_INCREASE:
                total += row.amount
            elif row.entry_type in LIABILITY_DECREASE:
                total -= row.amount
        return money(total)


class UnsupportedLayout(Exception):
    pass


class InvalidFixture(Exception):
    pass


def detect(text: str) -> bool:
    return f"Layout: {LAYOUT}" in text


def extract(text: str) -> ExtractedStatement:
    if not detect(text):
        from app.ingestion.bank import detect as bank_detect
        from app.ingestion.bank import extract as bank_extract

        if bank_detect(text):
            return bank_extract(text)
        raise UnsupportedLayout("This file is not a supported synthetic layout.")
    fields: dict[str, str] = {}
    rows: list[ExtractedRow] = []
    cards: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("ROW |"):
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 7:
                raise InvalidFixture("A fixture row is incomplete.")
            _, posted, last4, entry_type, category, description, amount = parts
            if category not in CATEGORIES:
                raise InvalidFixture(f"Unknown category {category}.")
            if entry_type not in LIABILITY_INCREASE | LIABILITY_DECREASE:
                raise InvalidFixture(f"Unknown entry type {entry_type}.")
            rows.append(
                ExtractedRow(
                    line_number=len(rows) + 1,
                    posted_on=date.fromisoformat(posted),
                    card_last4=last4,
                    entry_type=entry_type,
                    category=category,
                    description=description,
                    amount=money(amount),
                )
            )
            continue
        if line.startswith("Card:"):
            cards.append(line.split("|")[1].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    try:
        return ExtractedStatement(
            layout=LAYOUT,
            account_alias=fields["Account alias"],
            account_last4=fields["Account last4"],
            period_start=date.fromisoformat(fields["Period start"]),
            period_end=date.fromisoformat(fields["Period end"]),
            opening_liability=money(fields["Opening liability"]),
            closing_liability=money(fields["Closing liability"]),
            card_last4s=tuple(cards),
            rows=tuple(rows),
        )
    except KeyError as exc:
        raise InvalidFixture("The fixture is missing a required total.") from exc
