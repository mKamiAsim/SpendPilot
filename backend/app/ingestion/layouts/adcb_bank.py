"""ADCB consolidated bank statement. A text fixture shaped like the OCR target."""

from __future__ import annotations

import re

from app.ingestion.adapter import ExtractedRow, ExtractedStatement, InvalidFixture
from app.ingestion.layouts.common import lines_of, parse_money, slash_date
from app.ingestion.synthetic import write_pages_pdf

LAYOUT = "adcb-privilege-bank-v1"
PERIOD = re.compile(r"from (\d{2}/\d{2}/\d{4}) to (\d{2}/\d{2}/\d{4})")
IBAN = re.compile(r"\bAE\d{12,}\b", re.IGNORECASE)
LONG_DIGITS = re.compile(r"\d{8,}")
ACCOUNT = "1234567890123"
IBAN_VALUE = "AE070331234567890123456"
CUSTOMER = "99887766"

PAGE_1 = [
    "ADCB",
    "Consolidated Statement of Accounts",
    "PRIVILEGE CLUB",
    "Synthetic Customer",
    f"Customer ID: {CUSTOMER}",
    "Address: 1 Drop Street",
    "Summary of Accounts as on 30/06/2026",
    "Savings/Current/Call Accounts",
    f"Account number {ACCOUNT}",
    "Description Current",
    "Currency AED",
    "Balance (AED) 1,500.00",
    "Loans",
    "Credit Cards",
    "Card 4000 00XX XXXX 1414",
    "Minimum Amount Due 10.00",
    "Last Statement Balance 200.00",
    "Last Statement Date 19/03/2026",
    "Payment Due Date 14/04/2026",
    "Card 4000 00XX XXXX 1415",
    "TouchPoints Rewards Summary as on 30/06/2026",
]
PAGE_2 = [
    "ADCB",
    "Consolidated Statement of Accounts",
    "PRIVILEGE CLUB",
    "TouchPoints Earned by Products",
    "LuLuPoints Rewards Summary as on 30/06/2026",
    "Transactions Details for the period from 01/06/2026 to 30/06/2026",
    f"Account {ACCOUNT}",
    "Currency: AED",
    f"IBAN: {IBAN_VALUE}",
    "Branch: Drop Branch",
    "Account title: Synthetic Current",
    "Date | Value Date | Description | Debit | Credit | Balance",
    "01/06/2026 | 01/06/2026 | B/F | | | 1000.00",
    "05/06/2026 | 05/06/2026 | SALARY | | 800.00 | 1800.00",
    "08/06/2026 | 08/06/2026 | MBTRF TRF OUT TO | 100.00 | | 1700.00",
    "SYNTHETIC PERSON",
    "21/06/2026 | 21/06/2026 | CREDIT CARD PAYMNT | 250.00 | | 1450.00",
    f"22/06/2026 | 22/06/2026 | LOANRECOVERY-EMI:{CUSTOMER} | 50.00 | | 1400.00",
    "25/06/2026 | 25/06/2026 | Send Money via Aani to | 40.00 | | 1360.00",
    "Synthetic Friend",
    "Total | | | 440.00 | 800.00 |",
    "End Of Statement",
]


def detect(text: str) -> bool:
    return "Consolidated Statement of Accounts" in text and "Transactions Details for the period from" in text


def fixture_pages() -> list[list[str]]:
    return [PAGE_1, PAGE_2]


def build_pdf(*, password: str | None = None) -> bytes:
    return write_pages_pdf(fixture_pages(), password=password)


def extract(text: str) -> ExtractedStatement:
    period = PERIOD.search(text)
    if period is None:
        raise InvalidFixture("The ADCB bank fixture is missing a period.")
    rows: list[ExtractedRow] = []
    opening = None
    closing = None
    in_table = False
    for line in lines_of(text):
        if line.startswith("Date |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("Total") or line.startswith("End Of Statement"):
            break
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 6 or not re.match(r"\d{2}/\d{2}/\d{4}", parts[0]):
            if rows and not re.match(r"\d{2}/\d{2}/\d{4}", line):
                previous = rows[-1]
                rows[-1] = ExtractedRow(
                    line_number=previous.line_number,
                    posted_on=previous.posted_on,
                    card_last4="",
                    entry_type=previous.entry_type,
                    category=previous.category,
                    description=_scrub(f"{previous.description} {line}"),
                    amount=previous.amount,
                    flow=previous.flow,
                )
            continue
        posted, _value, description, debit, credit, balance = parts
        description = _scrub(description)
        if description == "B/F":
            opening = parse_money(balance)
            continue
        if debit and not credit:
            flow = "out"
            category = "Transfers"
        elif credit and not debit:
            flow = "in"
            category = "Income" if description == "SALARY" else "Transfers"
        else:
            continue
        amount = parse_money(debit or credit)
        rows.append(
            ExtractedRow(
                line_number=len(rows) + 1,
                posted_on=slash_date(posted),
                card_last4="",
                entry_type="transfer",
                category=category,
                description=description,
                amount=amount,
                flow=flow,
            )
        )
        closing = parse_money(balance)
    if opening is None or closing is None or not rows:
        raise InvalidFixture("The ADCB bank fixture is missing the transaction table.")
    return ExtractedStatement(
        layout=LAYOUT,
        kind="bank",
        account_alias="ADCB current",
        account_last4=ACCOUNT[-4:],
        period_start=slash_date(period.group(1)),
        period_end=slash_date(period.group(2)),
        opening_liability=opening,
        closing_liability=closing,
        card_last4s=(),
        rows=tuple(rows),
    )


def _scrub(value: str) -> str:
    cleaned = IBAN.sub("", value)
    cleaned = LONG_DIGITS.sub("", cleaned)
    cleaned = cleaned.replace(CUSTOMER, "")
    return re.sub(r"\s+", " ", cleaned).replace("- :", "").replace("EMI:", "EMI").strip(" -:")
