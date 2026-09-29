"""Shared date and amount parsing for synthetic statement layouts."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from app.ledger.money import money

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
MONEY = re.compile(r"-?\d{1,3}(?:,\d{3})*\.\d{2}")
BIDI = re.compile(r"[\u200e\u200f\u202a-\u202e]")


def clean_line(line: str) -> str:
    return BIDI.sub("", line).strip()


def lines_of(text: str) -> list[str]:
    return [clean_line(line) for line in text.splitlines() if clean_line(line)]


def parse_money(token: str) -> Decimal:
    return money(token.replace(",", "").replace("CR", "").replace("cr", ""))


def last4(line: str) -> str:
    digits = re.findall(r"\d{4}", line)
    if not digits:
        raise ValueError("no last 4")
    return digits[-1]


def slash_date(token: str) -> date:
    day, month, year = token.split("/")
    year_n = int(year)
    if year_n < 100:
        year_n += 2000
    return date(year_n, int(month), int(day))


def month_name_date(token: str, period_end: date) -> date:
    """Row dates omit the year. A later month than the period end is the previous year."""

    day_text, month_text = token.split()
    month = MONTHS[month_text.upper()]
    year = period_end.year
    if month > period_end.month:
        year -= 1
    return date(year, month, int(day_text))


def long_date(token: str) -> date:
    match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})\s+(\d{4})", token)
    if match is None:
        raise ValueError(token)
    return date(int(match.group(3)), MONTHS[match.group(2).upper()], int(match.group(1)))


def mon_yy(token: str) -> date:
    day_text, month_text, year_text = token.split("-")
    return date(2000 + int(year_text), MONTHS[month_text.upper()], int(day_text))
