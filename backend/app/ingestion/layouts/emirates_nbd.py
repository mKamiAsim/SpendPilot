"""Emirates NBD Mastercard Platinum. The filename is not the issuer."""

from __future__ import annotations

import re

from app.ingestion.adapter import ExtractedRow, ExtractedStatement, InvalidFixture
from app.ingestion.layouts.common import last4, lines_of, mon_yy, parse_money, slash_date
from app.ingestion.synthetic import write_pages_pdf

LAYOUT = "emirates-nbd-mastercard-platinum-v1"
ROW = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(.+)$")
PERIOD = re.compile(r"(\d{2}-[A-Za-z]{3}-\d{2})\s+to\s+(\d{2}-[A-Za-z]{3}-\d{2})")

PAGE_1 = [
    "Credit Card Statement",
    "Emirates NBD Bank (P.J.S.C.)",
    "emiratesnbd.com",
    "Card Number: 4000 00XX XXXX 3636",
    "Card Type: MASTERCARD PLATINUM",
    "Statement Period: 10-Aug-26 to 09-Sep-26",
    "Page 1 of 2",
    "TRN 100259835700003",
    "Holder: Synthetic Holder",
    "Address: Drop This Avenue",
    "Primary Card Number",
    "Synthetic Holder 4000 00XX XXXX 3636",
    "Transaction Date Posting Date Description Amount",
    "08/09/2026 09/09/2026 MARKET DUBAI ARE 40.00",
    "01/09/2026 01/09/2026 TRANSFER PAYMENT RECEIVED THANK YOU 80.00CR",
    "05/09/2026 05/09/2026 Ajyal Internatil Sc Plus Points Redeemed 15.00CR",
    "STATEMENT SUMMARY",
    "Previous Statement Due (AED) 200.00",
    "Purchase / Cash Advance (AED) 40.00",
    "Interest/Other Charges (AED) 0.00",
    "Payments/Credits (AED) 95.00",
    "Total Payment Due (AED) 145.00",
    "Current Balance (AED) 145.00",
    "PLUS POINTS SUMMARY",
    "Plus Points Opening Balance 1000",
    "Plus Points Earned 10",
    "Plus Points Adjusted -1350",
    "Plus Points Redeemed 15",
    "Plus Points Closing Balance 0",
]
PAGE_2 = [
    "Emirates NBD",
    "WARNING STATEMENTS",
    "Foreign Currency transaction fees",
    "Annual Membership Fees",
    "Installment (including finance charges and principle amount)",
    "Cash Advances",
]


def detect(text: str) -> bool:
    return "Emirates NBD" in text and "Credit Card Statement" in text and "PLUS POINTS SUMMARY" in text


def fixture_pages() -> list[list[str]]:
    return [PAGE_1, PAGE_2]


def build_pdf(*, password: str | None = None) -> bytes:
    return write_pages_pdf(fixture_pages(), password=password)


def extract(text: str) -> ExtractedStatement:
    period = PERIOD.search(text)
    if period is None:
        raise InvalidFixture("The Emirates NBD fixture is missing a period.")
    opening = _labeled(text, "Previous Statement Due (AED)")
    closing = _labeled(text, "Current Balance (AED)")
    card = ""
    for line in lines_of(text):
        if line.startswith("Card Number:"):
            card = last4(line)
            break
    rows: list[ExtractedRow] = []
    for line in lines_of(text):
        if line.startswith("STATEMENT SUMMARY") or line.startswith("PLUS POINTS"):
            break
        if line.startswith("TRN "):
            continue
        matched = ROW.match(line)
        if matched is None:
            continue
        description, amount, credit = _split(matched.group(3))
        if "Plus Points Adjusted" in description:
            continue
        if credit and "Plus Points Redeemed" in description:
            entry_type, category = "cashback", "Other"
        elif credit or "TRANSFER PAYMENT RECEIVED" in description:
            entry_type, category = "payment", "Transfers"
        else:
            entry_type, category = "purchase", "Other"
        rows.append(
            ExtractedRow(
                line_number=len(rows) + 1,
                posted_on=slash_date(matched.group(2)),
                card_last4=card,
                entry_type=entry_type,
                category=category,
                description=description,
                amount=amount,
            )
        )
    if not rows or not card:
        raise InvalidFixture("The Emirates NBD fixture is missing a row.")
    return ExtractedStatement(
        layout=LAYOUT,
        account_alias="Emirates NBD Mastercard Platinum",
        account_last4=card,
        period_start=mon_yy(period.group(1)),
        period_end=mon_yy(period.group(2)),
        opening_liability=opening,
        closing_liability=closing,
        card_last4s=(card,),
        rows=tuple(rows),
    )


def _labeled(text: str, label: str):
    for line in lines_of(text):
        if line.startswith(label):
            return parse_money(line.split()[-1])
    raise InvalidFixture(f"Missing {label}.")


def _split(rest: str):
    credit = rest.endswith("CR")
    body = rest[:-2].strip() if credit else rest
    token = body.split()[-1]
    description = body[: body.rfind(token)].strip()
    return description, parse_money(token), credit
