"""ADCB LuLu card layout. Synthetic text only. Page 1 is not OCR'd again."""

from __future__ import annotations

import re

from app.ingestion.adapter import ExtractedRow, ExtractedStatement
from app.ingestion.layouts.common import last4, lines_of, parse_money, slash_date
from app.ingestion.synthetic import write_pages_pdf

LAYOUT = "adcb-lulu-card-v1"
TXN = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(.+)$")
BALANCE = re.compile(r"(PREVIOUS BALANCE OUTSTANDING|NEW BALANCE OUTSTANDING)\s+(-?\d{1,3}(?:,\d{3})*\.\d{2})")

PAGE_1 = [
    "ADCB",
    "Statement of account",
    "LuLu credit card",
    "Card ending 1414",
    "Statement date 15/03/26",
    "Payment due 10/04/26",
    "Holder: Synthetic Holder",
    "Address: Drop This Street",
    "Amount in AED",
    "Purchases & Other Charges 200.00",
    "Payments & Other Credits 52.10",
    "Charges -2.10",
    "PREVIOUS BALANCE OUTSTANDING 1,000.00",
    "Reward Points Summary",
    "Points adjusted -15",
    "Available Cash 500.00",
    "Card No : 4000 00XX XXXX 1415 Synthetic Other",
    "16/02/2026 CAFE DUBAI AR 80.00",
    "Card No : 4000 00XX XXXX 1414 Synthetic Holder",
    "02/03/2026 MARKET DUBAI AR 120.00",
    "05/03/2026 PAYMENT RECEIVED, THANK YOU 40.00 CR",
    "06/03/2026 GROCERY REFUND 10.00 CR",
    "07/03/2026 REV FOREIGN TRANSACTION FEE 2.00 CR",
    "07/03/2026 VAT REV ON REV FOREIGN TRANSACTION 0.10 CR",
    "NEW BALANCE OUTSTANDING 1,147.90",
    "PERSONAL PAYMENT PLAN SHOP (11/24) 75.00",
    "PENDING INSTALLMENTS - 13",
]
PAGE_2 = [
    "Page 2 is image-only legal text. No transactions.",
]


def detect(text: str) -> bool:
    return (
        "ADCB" in text
        and "Statement of account" in text
        and "Amount in AED" in text
        and "Card No :" in text
        and "Consolidated Statement of Accounts" not in text
    )


def fixture_pages() -> list[list[str]]:
    return [PAGE_1, PAGE_2]


def build_pdf(*, password: str | None = None) -> bytes:
    return write_pages_pdf(fixture_pages(), password=password)


def extract(text: str) -> ExtractedStatement:
    rows: list[ExtractedRow] = []
    cards: list[str] = []
    current = ""
    opening = None
    closing = None
    period_end = None
    account_last4 = ""
    for line in lines_of(text):
        if line.startswith("Statement date "):
            period_end = slash_date(line.split()[-1])
            continue
        if line.startswith("Card ending "):
            account_last4 = last4(line)
            continue
        if line.startswith("Card No :"):
            current = last4(line)
            cards.append(current)
            continue
        previous = BALANCE.search(line)
        if previous and previous.group(1).startswith("PREVIOUS"):
            opening = parse_money(previous.group(2))
            continue
        if previous and previous.group(1).startswith("NEW"):
            closing = parse_money(previous.group(2))
            continue
        matched = TXN.match(line)
        if matched is None or not current:
            continue
        posted = slash_date(matched.group(1))
        description, amount, credit = _split_credit(matched.group(2))
        if description.startswith("PERSONAL PAYMENT PLAN") or description.startswith("PENDING INSTALLMENTS"):
            continue
        entry_type, category = _classify(description, credit)
        rows.append(
            ExtractedRow(
                line_number=len(rows) + 1,
                posted_on=posted,
                card_last4=current,
                entry_type=entry_type,
                category=category,
                description=description,
                amount=amount,
            )
        )
    if opening is None or closing is None or not rows or not account_last4:
        from app.ingestion.adapter import InvalidFixture

        raise InvalidFixture("The ADCB LuLu fixture is missing a balance or a row.")
    return ExtractedStatement(
        layout=LAYOUT,
        account_alias="ADCB LuLu",
        account_last4=account_last4,
        period_start=min(row.posted_on for row in rows),
        period_end=period_end or max(row.posted_on for row in rows),
        opening_liability=opening,
        closing_liability=closing,
        card_last4s=tuple(cards),
        rows=tuple(rows),
    )


def _split_credit(rest: str):
    credit = rest.endswith(" CR") or rest.endswith("CR")
    body = rest[:-3].strip() if rest.endswith(" CR") else (rest[:-2].strip() if rest.endswith("CR") else rest)
    amount_token = body.split()[-1]
    description = body[: body.rfind(amount_token)].strip()
    return description, parse_money(amount_token), credit


def _classify(description: str, credit: bool) -> tuple[str, str]:
    if not credit:
        return "purchase", "Other"
    if "PAYMENT RECEIVED" in description:
        return "payment", "Transfers"
    if description.startswith("REV ") or " VAT REV " in f" {description} " or description.startswith("VAT REV"):
        return "refund", "Fees and interest"
    return "refund", "Other"
