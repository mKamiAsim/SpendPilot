"""OCR runs only when a PDF has no text layer."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from PIL import Image, ImageDraw, ImageFont
from pikepdf import Encryption, Pdf

from app.ingestion.extract import ocr_scanned_page, read_statement_text
from app.ingestion.synthetic import build_fixture_pdf, write_lines_pdf


def _scanned(word: str) -> bytes:
    image = Image.new("L", (1400, 280), 255)
    draw = ImageDraw.Draw(image)
    draw.text((40, 80), word, fill=0, font=ImageFont.load_default(size=90))
    raw = BytesIO()
    image.save(raw, format="PNG")
    import img2pdf

    return img2pdf.convert(raw.getvalue())


def test_text_pdf_survives_the_ocr_library_import(tmp_path: Path, monkeypatch):
    import ocrmypdf

    del ocrmypdf
    called = {"n": 0}

    def explode(source, output):
        del source, output
        called["n"] += 1
        raise AssertionError("a text PDF was sent to OCR")

    monkeypatch.setattr("app.ingestion.extract.ocr_scanned_page", explode)
    path = tmp_path / "card.pdf"
    path.write_bytes(build_fixture_pdf(password="fixture-password"))
    text = read_statement_text(path, "fixture-password")
    assert "generic-aed-card-v1" in text
    assert "Carrefour" in text
    assert "(cid:" not in text
    assert called["n"] == 0


def test_jpeg_is_ocr_and_not_opened_as_a_pdf(tmp_path: Path, monkeypatch):
    from app.ingestion.adapter import extract
    from app.ingestion.layouts.adcb_bank import ocr_fixture_text

    def explode(*_args, **_kwargs):
        raise AssertionError("an image was opened with pikepdf")

    monkeypatch.setattr("app.ingestion.extract.Pdf.open", explode)
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))

        class Result:
            returncode = 0
            stdout = ocr_fixture_text()
            stderr = ""

        return Result()

    monkeypatch.setattr("app.ingestion.extract.subprocess.run", fake_run)
    path = tmp_path / "statement.jpg"
    Image.new("RGB", (8, 8), "white").save(path, format="JPEG")
    text = read_statement_text(path, "not-a-password")
    assert calls and calls[0][0] == "tesseract"
    assert "not-a-password" not in " ".join(calls[0])
    statement = extract(text)
    assert statement.layout == "adcb-privilege-bank-v1"
    assert any(row.description == "CREDIT CARD PAYMNT" and row.flow == "out" for row in statement.rows)


def test_text_pdf_does_not_use_ocr(tmp_path: Path, monkeypatch):
    called = {"n": 0}

    def explode(source, output):
        del source, output
        called["n"] += 1
        raise AssertionError("a text PDF was sent to OCR")

    monkeypatch.setattr("app.ingestion.extract.ocr_scanned_page", explode)
    path = tmp_path / "text.pdf"
    path.write_bytes(write_lines_pdf(["SPENDPILOT SYNTHETIC FIXTURE"]))
    text = read_statement_text(path, None)
    assert "SPENDPILOT SYNTHETIC FIXTURE" in text
    assert called["n"] == 0


def test_scanned_page_uses_english_and_arabic_ocr(tmp_path: Path, monkeypatch):
    languages: list[list[str]] = []
    real = ocr_scanned_page

    def spy(source, output):
        import ocrmypdf

        original = ocrmypdf.ocr

        def capture(*args, **kwargs):
            languages.append(list(kwargs["language"]))
            return original(*args, **kwargs)

        monkeypatch.setattr(ocrmypdf, "ocr", capture)
        real(source, output)

    monkeypatch.setattr("app.ingestion.extract.ocr_scanned_page", spy)
    path = tmp_path / "scan.pdf"
    path.write_bytes(_scanned("HELLO"))
    text = read_statement_text(path, None)
    assert languages == [["eng", "ara"]]
    assert "HELLO" in text.upper()


def test_ocr_does_not_receive_the_pdf_password(tmp_path: Path, monkeypatch):
    secret = "ocr-secret-password"
    seen = {}

    def spy(source, output):
        seen["bytes"] = Path(source).read_bytes()
        Path(output).write_bytes(write_lines_pdf(["HELLO"]))

    monkeypatch.setattr("app.ingestion.extract.ocr_scanned_page", spy)
    encrypted = BytesIO()
    Pdf.open(BytesIO(_scanned("IMAGE"))).save(encrypted, encryption=Encryption(owner=secret, user=secret))
    path = tmp_path / "locked.pdf"
    path.write_bytes(encrypted.getvalue())
    text = read_statement_text(path, secret)
    assert text.strip()
    assert secret not in text
    assert secret.encode() not in seen["bytes"]


def test_ocr_licence_allows_english_and_arabic_assets():
    adr = (ROOT / "docs" / "adr" / "0004-pdf-ocr-licences.md").read_text()
    assert "Apache-2.0" in adr
    assert "tesseract-ocr-eng" in adr
    assert "tesseract-ocr-ara" in adr
    assert "Redistribution" in adr
    assert "allowed" in adr
