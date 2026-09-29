"""Named statement layouts. Fixtures are synthetic. Real files are not in the repo."""

from __future__ import annotations

from app.ingestion.adapter import ExtractedStatement
from app.ingestion.layouts import adcb_bank, adcb_lulu, emirates_islamic, emirates_nbd

PARSERS = (adcb_lulu, emirates_islamic, emirates_nbd, adcb_bank)


def parse_named(text: str) -> ExtractedStatement | None:
    for parser in PARSERS:
        if parser.detect(text):
            return parser.extract(text)
    return None
