"""Decrypt a PDF locally and read its text.

A page that already has text is not sent through OCR. A scanned page is.
"""

from __future__ import annotations

import tempfile
import threading
from io import BytesIO
from pathlib import Path

import pdfminer.pdffont as pdffont
import pdfplumber
from pikepdf import PasswordError, Pdf

# OCRmyPDF replaces this constructor on import. Text PDFs in this process
# must keep the stock decoder, or their text comes back as character codes.
_STOCK_SIMPLE_FONT_INIT = pdffont.PDFSimpleFont.__init__
_pdfminer_lock = threading.Lock()


class DecryptError(Exception):
    pass


class OcrError(Exception):
    pass


def read_statement_text(path: Path, password: str | None) -> str:
    text = _extract_text(path, password)
    if text.strip():
        return text
    return _ocr_scanned(path, password)


def ocr_scanned_page(source: Path, output: Path) -> None:
    """OCR one decrypted file. The password is not an argument."""

    import ocrmypdf

    with _pdfminer_lock:
        ocrmypdf.ocr(
            str(source),
            str(output),
            language=["eng", "ara"],
            progress_bar=False,
            optimize=0,
            output_type="pdf",
        )


def _extract_text(path: Path, password: str | None) -> str:
    with _pdfminer_lock:
        current = pdffont.PDFSimpleFont.__init__
        pdffont.PDFSimpleFont.__init__ = _STOCK_SIMPLE_FONT_INIT
        try:
            return _extract_text_locked(path, password)
        finally:
            pdffont.PDFSimpleFont.__init__ = current


def _extract_text_locked(path: Path, password: str | None) -> str:
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


def _ocr_scanned(path: Path, password: str | None) -> str:
    decrypted: Path | None = None
    output: Path | None = None
    try:
        source = path
        if password:
            handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            handle.close()
            decrypted = Path(handle.name)
            with Pdf.open(path, password=password) as opened:
                opened.save(decrypted)
            source = decrypted
        handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        handle.close()
        output = Path(handle.name)
        ocr_scanned_page(source, output)
        return _extract_text(output, None)
    except PasswordError as exc:
        raise DecryptError("The password was not accepted.") from exc
    except DecryptError:
        raise
    except Exception as exc:
        raise OcrError("This scanned page could not be read.") from exc
    finally:
        for item in (decrypted, output):
            if item is not None:
                item.unlink(missing_ok=True)
