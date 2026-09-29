"""ADCB consolidated bank statement. A text fixture shaped like the OCR target."""

from __future__ import annotations

import re

from app.ingestion.adapter import ExtractedRow, ExtractedStatement, InvalidFixture
from app.ingestion.layouts.common import AMOUNT, lines_of, parse_money, slash_date
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
# Column gaps disappear in OCR, so direction comes from the description.
OCR_LINES = [
    "ADCB",
    "Consolidated Statement of Accounts",
    "PRIVILEGE CLUB",
    "Transactions Details for the period from 01/06/2026 to 30/06/2026",
    f"Account Details: {ACCOUNT} - Current Account Personal Currency: AED",
    f"IBAN: {IBAN_VALUE} Branch: Drop Branch",
    "Date Description Chq/Ref No. Value Date Debit Credit Balance",
    "01/06/2026 B/F 1000.00",
    "05/06/2026 SALARY 48 05/06/2026 800.00 1800.00",
    "06/06/2026 Synthetic Person 12 06/06/2026 9.00 1791.00",
    f"08/06/2026 MBTRF TRF OUT TO 12345678 08/06/2026 100.00 1700.00",
    "not-a-date leftover 999.99 1.00",
    "21/06/2026 CREDIT CARD PAYMNT 11112222 21/06/2026 250.00 1450.00",
    f"22/06/2026 LOANRECOVERY-EMI:{CUSTOMER} 22/06/2026 50.00 1400.00",
    "25/06/2026 Send Money via Aani to Synthetic Friend 25/06/2026 40.00 1360.00",
    "Total 440.00 800.00",
    "End Of Statement",
]


def detect(text: str) -> bool:
    return "Consolidated Statement of Accounts" in text and "Transactions Details for the period from" in text


def fixture_pages() -> list[list[str]]:
    return [PAGE_1, PAGE_2]


def build_pdf(*, password: str | None = None) -> bytes:
    return write_pages_pdf(fixture_pages(), password=password)


def ocr_fixture_text() -> str:
    return "\n".join(OCR_LINES)


def extract(text: str) -> ExtractedStatement:
    period = PERIOD.search(text)
    if period is None:
        raise InvalidFixture("The ADCB bank fixture is missing a period.")
    if any(line.startswith("Date |") for line in lines_of(text)):
        rows, opening, closing = _pipe_table(text)
    else:
        rows, opening, closing = _ocr_table(text)
    if opening is None or closing is None or not rows:
        raise InvalidFixture("The ADCB bank fixture is missing the transaction table.")
    return ExtractedStatement(
        layout=LAYOUT,
        kind="bank",
        account_alias="ADCB current",
        account_last4=_account_last4(text),
        period_start=slash_date(period.group(1)),
        period_end=slash_date(period.group(2)),
        opening_liability=opening,
        closing_liability=closing,
        card_last4s=(),
        rows=tuple(rows),
    )


def _pipe_table(text: str):
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
        rows.append(
            _transfer(
                len(rows) + 1,
                slash_date(posted),
                description,
                parse_money(debit or credit),
                flow,
                category,
            )
        )
        closing = parse_money(balance)
    return rows, opening, closing


def _ocr_table(text: str):
    """Keep a row only when the description says which column the amount came from."""

    lines = lines_of(text)
    start = None
    for index, line in enumerate(lines):
        upper = line.upper()
        if "DEBIT" in upper and "CREDIT" in upper and "BALANCE" in upper:
            start = index + 1
            break
    if start is None:
        raise InvalidFixture("The ADCB bank fixture is missing the transaction table.")
    rows: list[ExtractedRow] = []
    opening = None
    closing = None
    for line in lines[start:]:
        if line.startswith("Total") or line.startswith("End Of Statement"):
            break
        if re.search(r"\bB/F\b", line):
            amounts = AMOUNT.findall(line)
            if amounts:
                opening = parse_money(amounts[-1])
            continue
        parsed = _safe_ocr_row(line, len(rows) + 1)
        if parsed is None:
            continue
        row, balance = parsed
        rows.append(row)
        closing = balance
    return rows, opening, closing


_STRONG = (
    ("CREDIT CARD PAYMNT", "out", "Transfers", "CREDIT CARD PAYMNT"),
    ("SALARY", "in", "Income", "SALARY"),
    ("LOANRECOVERY-EMI", "out", "Transfers", "LOANRECOVERY-EMI"),
)
_DIRECTIONAL = (
    ("MBTRF", "out", "Transfers"),
    ("TRF OUT", "out", "Transfers"),
    ("SEND MONEY VIA AANI", "out", "Transfers"),
)


def _safe_ocr_row(line: str, line_number: int):
    dates = re.findall(r"\d{2}/\d{2}/\d{4}", line)
    amounts = AMOUNT.findall(line)
    if len(dates) < 1 or len(amounts) != 2:
        return None
    upper = line.upper()
    for needle, flow, category, label in _STRONG:
        if needle in upper:
            row = _transfer(
                line_number,
                slash_date(dates[0]),
                label,
                parse_money(amounts[0]),
                flow,
                category,
            )
            return row, parse_money(amounts[1])
    if not re.match(r"\d{2}/\d{2}/\d{4}", line):
        return None
    for needle, flow, category in _DIRECTIONAL:
        if needle in upper:
            description = _scrub(re.sub(r"\d{2}/\d{2}/\d{4}", " ", line))
            description = AMOUNT.sub(" ", description)
            description = _scrub(description)
            if not description:
                return None
            row = _transfer(
                line_number,
                slash_date(dates[0]),
                description,
                parse_money(amounts[0]),
                flow,
                category,
            )
            return row, parse_money(amounts[1])
    return None


def _transfer(line_number: int, posted, description: str, amount, flow: str, category: str) -> ExtractedRow:
    return ExtractedRow(
        line_number=line_number,
        posted_on=posted,
        card_last4="",
        entry_type="transfer",
        category=category,
        description=description,
        amount=amount,
        flow=flow,
    )


def _account_last4(text: str) -> str:
    best = ""
    for line in lines_of(text):
        if "IBAN" in line.upper() or "Title" in line:
            continue
        if not re.search(r"\bAccount\b", line):
            continue
        runs = [run for run in re.findall(r"\d+", line) if len(run) >= 6]
        if not runs:
            continue
        candidate = max(runs, key=len)
        if len(candidate) > len(best):
            best = candidate
    if not best:
        raise InvalidFixture("The ADCB bank fixture is missing an account.")
    return best[-4:]


def _scrub(value: str) -> str:
    cleaned = IBAN.sub("", value)
    cleaned = LONG_DIGITS.sub("", cleaned)
    cleaned = cleaned.replace(CUSTOMER, "")
    return re.sub(r"\s+", " ", cleaned).replace("- :", "").replace("EMI:", "EMI").strip(" -:")
