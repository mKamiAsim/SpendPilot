"""Decrypt a PDF locally and read its text. OCR is not installed."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pdfplumber
from pikepdf import PasswordError, Pdf


class DecryptError(Exception):
    pass


def read_statement_text(path: Path, password: str | None) -> str:
    try:
        pdf = Pdf.open(path, password=password or "")
    except PasswordError as exc:
        raise DecryptError("The password was not accepted.") from exc
    buffer = BytesIO()
    pdf.save(buffer)
    buffer.seek(0)
    pages: list[str] = []
    with pdfplumber.open(buffer) as document:
        if len(document.pages) > 30:
            raise DecryptError("The file has more than 30 pages.")
        for page in document.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)
