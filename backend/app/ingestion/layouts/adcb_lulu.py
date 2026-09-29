"""ADCB LuLu card layout. Synthetic text only. Page 1 is not OCR'd again."""

from __future__ import annotations

import re

from app.ingestion.adapter import ExtractedRow, ExtractedStatement
from app.ingestion.layouts.common import AMOUNT, last4, lines_of, parse_money, slash_date
from app.ingestion.synthetic import write_pages_pdf

LAYOUT = "adcb-lulu-card-v1"
TXN = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(.+)$")
MASKED_CARD = re.compile(r"^[Xx]{4,}(?:\s*[Xx]+)*\s*\d{4}$")
NOT_A_PURCHASE = (
    "NEW BALANCE OUTSTANDING",
    "PREVIOUS BALANCE OUTSTANDING",
    "PERSONAL PAYMENT PLAN",
    "PENDING INSTALLMENTS",
)

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
# Masthead labels stay in the image. Amounts have no commas. The new balance is dated.
TEXT_LAYER = [
    "XXXXXXXXXXXX1414",
    "15/03/26",
    "Synthetic Holder 10/04/26",
    "Drop This Street 1,000.00",
    "Charges -2.10",
    "Reward Points Summary",
    "Points adjusted -15",
    "Available Cash 500.00",
    "PREVIOUS BALANCE OUTSTANDING 1000.00",
    "Card No : XXXXXXXXXXXX1415 Synthetic Other",
    "16/02/2026 CAFE DUBAI AR 80.00",
    "Card No : XXXXXXXXXXXX1414 Synthetic Holder",
    "02/03/2026 MARKET DUBAI AR 120.00",
    "05/03/2026 PAYMENT RECEIVED, THANK YOU 40.00 CR",
    "06/03/2026 GROCERY REFUND 10.00 CR",
    "07/03/2026 REV FOREIGN TRANSACTION FEE 2.00 CR",
    "07/03/2026 VAT REV ON REV FOREIGN TRANSACTION 0.10 CR",
    "19/03/2026 NEW BALANCE OUTSTANDING 1147.90",
    "PERSONAL PAYMENT PLAN SHOP (11/24) 75.00",
    "PENDING INSTALLMENTS - 13",
    "Page 1 of 2",
    "Page 2 of 2",
]


def detect(text: str) -> bool:
    return (
        "Card No :" in text
        and "PREVIOUS BALANCE OUTSTANDING" in text
        and "NEW BALANCE OUTSTANDING" in text
        and "PAYMENT RECEIVED, THANK YOU" in text
        and "Consolidated Statement of Accounts" not in text
    )


def text_layer_fixture() -> str:
    return "\n".join(TEXT_LAYER)


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
        if current == "" and period_end is None and re.fullmatch(r"\d{2}/\d{2}/\d{2}", line):
            period_end = slash_date(line)
            continue
        if line.startswith("Card ending "):
            account_last4 = last4(line)
            continue
        if MASKED_CARD.match(line):
            account_last4 = account_last4 or last4(line)
            continue
        if line.startswith("Card No :"):
            current = last4(line)
            cards.append(current)
            continue
        if "PREVIOUS BALANCE OUTSTANDING" in line:
            found = _amount_after(line, "PREVIOUS BALANCE OUTSTANDING")
            if found is not None:
                opening = found
            continue
        if "NEW BALANCE OUTSTANDING" in line:
            found = _amount_after(line, "NEW BALANCE OUTSTANDING")
            if found is not None:
                closing = found
            continue
        if any(phrase in line for phrase in NOT_A_PURCHASE):
            continue
        matched = TXN.match(line)
        if matched is None or not current:
            continue
        posted = slash_date(matched.group(1))
        description, amount, credit = _split_credit(matched.group(2))
        if any(phrase in description for phrase in NOT_A_PURCHASE):
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


def _amount_after(line: str, label: str):
    tail = line.split(label, 1)[1]
    match = AMOUNT.search(tail)
    if match is None:
        return None
    return parse_money(match.group(0))


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
