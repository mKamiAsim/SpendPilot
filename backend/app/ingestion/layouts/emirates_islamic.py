"""One Emirates Islamic card layout for Switch Cashback and Amazon World."""

from __future__ import annotations

import re

from app.ingestion.adapter import ExtractedRow, ExtractedStatement, InvalidFixture
from app.ingestion.layouts.common import last4, lines_of, long_date, month_name_date, parse_money
from app.ingestion.synthetic import write_pages_pdf

LAYOUT = "emirates-islamic-card-v1"
ROW = re.compile(r"^(\d{2} [A-Za-z]{3})\s+(\d{2} [A-Za-z]{3})\s+(.+)$")
MONEY = re.compile(r"(\d{1,3}(?:,\d{3})*\.\d{2})(CR)?", re.IGNORECASE)
CURRENCY = re.compile(r"^[A-Z]{3}$")
STOP = (
    "Card Limit",
    "Available Limit",
    "Minimum Payment Due",
    "Payment Due Date",
    "Total Payment Due",
    "Profit/Other Charges",
    "Current Balance",
    "Warning Statements",
)
CASHBACK = "Please view cashback in the EI+ mobile app"
REWARDS = "Please login to the EI+ App to view the Rewards summary"

PAGE_1 = [
    "Emirates Islamic",
    "Statement of Card Account",
    "Card Account Number.: 4000 00XX XXXX 2525",
    "Statement Period:",
    "From: 1st Aug 2026",
    "To: 31st Aug 2026",
    "PAGE 1 OF 2",
    "Holder: Synthetic Person",
    "Address: Drop This Road",
    "OPENING BALANCE 100.00",
    "PRIMARY CARD NO:400000XXXXXX2525",
    "Post Date Trxn. Date Description Amount",
    "02 AUG 02 AUG MARKET DUBAI ARE 50.00",
    "02 AUG 31 JUL *AMAZON UK 441122334455 722.00 GBP 20.00",
    "*(1 AED = GBP 0.2000)",
    "SUPPLEMENTARY CARD NO: 400000XXXXXX2526",
    "03 AUG 03 AUG CAFE ABU DHABI ARE 15.00",
    "04 AUG 04 AUG TRANSFER PAYMENT RECEIVED THANK YOU 1,192.36CR",
    "Card Limit 10,000.00",
    "Available Limit 11,007.36",
    "Minimum Payment Due 0.00",
    "Payment Due Date 25/09/26",
    "Total Payment Due 0.00",
    "Profit/Other Charges (AED) 0.00",
    "Current Balance (AED) -1,007.36",
    CASHBACK,
]
PAGE_2 = [
    "Emirates Islamic",
    "Statement of Card Account",
    "PAGE 2 OF 2",
    "Card Limit 10,000.00",
    "Current Balance (AED) -1,007.36",
    "Total Payment Due 0.00",
    "Warning Statements",
    "Over Limit Fee",
    "Direct Debit Return Fee",
    "Donation Amount",
    "Purchases/Cash Advances",
]


def detect(text: str) -> bool:
    return "Emirates Islamic" in text and "Statement of Card Account" in text and "OPENING BALANCE" in text


def fixture_pages(*, rewards: bool = False) -> list[list[str]]:
    trailer = REWARDS if rewards else CASHBACK
    first = [trailer if line == CASHBACK else line for line in PAGE_1]
    return [first, PAGE_2]


def build_pdf(*, password: str | None = None, rewards: bool = False) -> bytes:
    return write_pages_pdf(fixture_pages(rewards=rewards), password=password)


def extract(text: str) -> ExtractedStatement:
    period_end = long_date(next(line for line in lines_of(text) if line.startswith("To:")))
    period_start = long_date(next(line for line in lines_of(text) if line.startswith("From:")))
    opening = None
    closing = None
    for line in lines_of(text):
        if line.startswith("OPENING BALANCE"):
            opening = parse_money(line.split()[-1])
        if line.startswith("Current Balance"):
            closing = parse_money(line.split()[-1])
            break
    rows: list[ExtractedRow] = []
    current = ""
    cards: list[str] = []
    stopped = False
    for line in lines_of(text):
        if stopped or line.startswith(STOP) or line.startswith("*(1 AED ="):
            if line.startswith(STOP):
                stopped = True
            continue
        if "CARD NO" in line:
            current = last4(line)
            if current not in cards:
                cards.append(current)
            continue
        matched = ROW.match(line)
        if matched is None or not current:
            continue
        description, amount, credit = _aed_amount(matched.group(3))
        if amount is None or description.startswith("*(1 AED ="):
            continue
        posted = month_name_date(matched.group(2), period_end)
        entry_type = "payment" if "TRANSFER PAYMENT RECEIVED" in description else "purchase"
        if credit and entry_type != "payment":
            entry_type = "refund"
        rows.append(
            ExtractedRow(
                line_number=len(rows) + 1,
                posted_on=posted,
                card_last4=current,
                entry_type=entry_type,
                category="Transfers" if entry_type == "payment" else "Other",
                description=description,
                amount=amount,
            )
        )
    if opening is None or closing is None or not rows:
        raise InvalidFixture("The Emirates Islamic fixture is missing a balance or a row.")
    return ExtractedStatement(
        layout=LAYOUT,
        account_alias="Emirates Islamic card",
        account_last4=cards[0],
        period_start=period_start,
        period_end=period_end,
        opening_liability=opening,
        closing_liability=closing,
        card_last4s=tuple(cards),
        rows=tuple(rows),
    )


def _aed_amount(rest: str):
    """The AED figure is the last amount that is not a foreign-currency amount."""

    chosen = None
    for match in MONEY.finditer(rest):
        after = rest[match.end() :].strip()
        nxt = after.split(" ", 1)[0] if after else ""
        if CURRENCY.match(nxt) and nxt != "AED":
            continue
        chosen = match
    if chosen is None:
        return rest.strip(), None, False
    description = rest[: chosen.start()].strip()
    return description, parse_money(chosen.group(1)), chosen.group(2) is not None
