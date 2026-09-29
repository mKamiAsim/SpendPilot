"""Synthetic named layouts. Real statements are not in the repo."""

from __future__ import annotations

import json
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from pikepdf import Pdf

from app.ingestion.adapter import UnsupportedLayout, extract
from app.ingestion.extract import read_statement_text
from app.ingestion.layouts.adcb_bank import ACCOUNT, CUSTOMER, IBAN_VALUE, build_pdf as build_bank
from app.ingestion.layouts.adcb_bank import ocr_fixture_text
from app.ingestion.layouts.adcb_lulu import build_pdf as build_lulu
from app.ingestion.layouts.adcb_lulu import text_layer_fixture
from app.ingestion.layouts.common import month_name_date
from app.ingestion.layouts.emirates_islamic import build_pdf as build_ei
from app.ingestion.layouts.emirates_islamic import fixture_pages as ei_pages
from app.ingestion.layouts.emirates_islamic import wrapped_fixture
from app.ingestion.layouts.emirates_nbd import build_pdf as build_enbd
from app.ingestion.layouts.emirates_nbd import wrapped_summary_fixture
from app.ledger.money import money

FORBIDDEN = ("7837", "8220", "6719", "5976", "3753", "8792")
FAKE_PASSWORD = "layout-fake-password"


def _blob(statement) -> str:
    payload = {
        "layout": statement.layout,
        "alias": statement.account_alias,
        "last4": statement.account_last4,
        "cards": statement.card_last4s,
        "opening": str(statement.opening_liability),
        "closing": str(statement.closing_liability),
        "rows": [
            {
                "posted_on": row.posted_on.isoformat(),
                "card": row.card_last4,
                "type": row.entry_type,
                "category": row.category,
                "description": row.description,
                "amount": str(row.amount),
            }
            for row in statement.rows
        ],
    }
    return json.dumps(payload)


def test_fixtures_do_not_use_real_last4s():
    root = Path(__file__).resolve().parents[1] / "app" / "ingestion" / "layouts"
    text = "\n".join(path.read_text() for path in root.glob("*.py"))
    for last4 in FORBIDDEN:
        assert last4 not in text


def test_july_transaction_on_an_august_statement_keeps_the_same_year():
    assert month_name_date("31 JUL", date(2026, 8, 31)) == date(2026, 7, 31)
    assert month_name_date("02 DEC", date(2026, 1, 31)) == date(2025, 12, 2)


def test_adcb_lulu_credits_and_plan(tmp_path: Path, monkeypatch):
    called = {"n": 0}

    def explode(source, output):
        del source, output
        called["n"] += 1
        raise AssertionError("page 1 text was sent to OCR")

    monkeypatch.setattr("app.ingestion.extract.ocr_scanned_page", explode)
    path = tmp_path / "lulu.pdf"
    path.write_bytes(build_lulu())
    text = read_statement_text(path, None)
    statement = extract(text)
    assert called["n"] == 0
    assert statement.layout == "adcb-lulu-card-v1"
    assert statement.account_last4 == "1414"
    assert statement.card_last4s == ("1415", "1414")
    assert statement.computed_closing() == statement.closing_liability == money("1147.90")
    by_desc = {row.description: row for row in statement.rows}
    assert by_desc["CAFE DUBAI AR"].card_last4 == "1415"
    assert by_desc["CAFE DUBAI AR"].entry_type == "purchase"
    assert by_desc["PAYMENT RECEIVED, THANK YOU"].entry_type == "payment"
    assert by_desc["GROCERY REFUND"].entry_type == "refund"
    assert by_desc["REV FOREIGN TRANSACTION FEE"].entry_type == "refund"
    assert by_desc["VAT REV ON REV FOREIGN TRANSACTION"].entry_type == "refund"
    assert "PERSONAL PAYMENT PLAN" not in _blob(statement)
    assert "75.00" not in _blob(statement)
    assert "-2.10" not in _blob(statement)
    assert "-15" not in _blob(statement)
    assert "Available Cash" not in _blob(statement)
    assert "Drop This Street" not in _blob(statement)


def test_lulu_text_layer_without_masthead_labels():
    statement = extract(text_layer_fixture())
    assert statement.layout == "adcb-lulu-card-v1"
    assert "ADCB" not in text_layer_fixture()
    assert statement.account_last4 == "1414"
    assert statement.period_end == date(2026, 3, 15)
    assert statement.card_last4s == ("1415", "1414")
    assert statement.computed_closing() == statement.closing_liability == money("1147.90")
    payment = next(row for row in statement.rows if "PAYMENT RECEIVED" in row.description)
    assert payment.entry_type == "payment"
    assert payment.amount == money("40.00")
    assert all("NEW BALANCE" not in row.description for row in statement.rows)
    assert all(row.amount != money("1147.90") for row in statement.rows)
    assert "PERSONAL PAYMENT PLAN" not in _blob(statement)
    assert "75.00" not in _blob(statement)
    assert "Drop This Street" not in _blob(statement)


def test_lulu_text_page_is_not_ocrd_when_page_2_is_an_image(tmp_path: Path, monkeypatch):
    called = {"n": 0}

    def explode(source, output):
        del source, output
        called["n"] += 1
        raise AssertionError("a text page was sent to OCR")

    monkeypatch.setattr("app.ingestion.extract.ocr_scanned_page", explode)
    image = BytesIO()
    from PIL import Image
    import img2pdf

    Image.new("L", (40, 40), 255).save(image, format="PNG")
    merged = Pdf.open(BytesIO(build_lulu()))
    scanned = Pdf.open(BytesIO(img2pdf.convert(image.getvalue())))
    merged.pages.append(scanned.pages[0])
    raw = BytesIO()
    merged.save(raw)
    path = tmp_path / "lulu-page2-image.pdf"
    path.write_bytes(raw.getvalue())
    text = read_statement_text(path, None)
    assert "PAYMENT RECEIVED, THANK YOU" in text
    assert called["n"] == 0


def test_fake_password_decrypts_a_synthetic_layout(tmp_path: Path):
    path = tmp_path / "locked.pdf"
    path.write_bytes(build_lulu(password=FAKE_PASSWORD))
    text = read_statement_text(path, FAKE_PASSWORD)
    statement = extract(text)
    assert statement.layout == "adcb-lulu-card-v1"
    assert FAKE_PASSWORD not in text


def test_emirates_islamic_is_one_layout_for_both_products(tmp_path: Path):
    path = tmp_path / "ei.pdf"
    path.write_bytes(build_ei())
    cashback = extract(read_statement_text(path, None))
    rewards = extract("\n".join(line for page in ei_pages(rewards=True) for line in page))
    assert cashback.layout == rewards.layout == "emirates-islamic-card-v1"
    assert [row.description for row in cashback.rows] == [row.description for row in rewards.rows]
    assert cashback.computed_closing() == cashback.closing_liability == money("-1007.36")
    assert len(cashback.rows) == 4
    foreign = next(row for row in cashback.rows if "AMAZON" in row.description)
    assert foreign.amount == money("20.00")
    assert foreign.entry_type == "purchase"
    assert "722.00" in foreign.description
    assert "441122334455" in foreign.description
    assert foreign.posted_on == date(2026, 7, 31)
    assert all(row.amount != money("722.00") for row in cashback.rows)
    assert all(row.amount != money("10000.00") for row in cashback.rows)
    assert "Over Limit Fee" not in _blob(cashback)
    assert "Direct Debit Return Fee" not in _blob(cashback)
    payment = next(row for row in cashback.rows if row.entry_type == "payment")
    assert payment.amount == money("1192.36")
    assert cashback.card_last4s == ("2525", "2526")


def test_emirates_islamic_keeps_rows_after_a_repeated_summary_strip():
    statement = extract(wrapped_fixture())
    assert statement.layout == "emirates-islamic-card-v1"
    assert statement.period_start == date(2026, 8, 1)
    assert statement.period_end == date(2026, 8, 31)
    assert statement.card_last4s == ("2525", "2526")
    assert statement.closing_liability == money("-1007.36")
    assert statement.computed_closing() == statement.closing_liability
    assert len(statement.rows) == 4
    payment = next(row for row in statement.rows if row.entry_type == "payment")
    assert payment.amount == money("1192.36")
    assert payment.card_last4 == "2526"
    foreign = next(row for row in statement.rows if "AMAZON" in row.description)
    assert foreign.amount == money("20.00")
    assert "*(1 AED" not in _blob(statement)
    assert "Over Limit Fee" not in _blob(statement)
    assert all(row.amount != money("10000.00") for row in statement.rows)


def test_emirates_nbd_ignores_a_fab_filename_and_points_adjustment():
    statement = extract(read_statement_text_bytes(build_enbd()))
    assert statement.layout == "emirates-nbd-mastercard-platinum-v1"
    assert statement.account_alias.startswith("Emirates NBD")
    assert statement.computed_closing() == statement.closing_liability == money("145.00")
    assert statement.period_start == date(2026, 8, 10)
    assert statement.period_end == date(2026, 9, 9)
    market = next(row for row in statement.rows if row.description.startswith("MARKET"))
    assert market.posted_on == date(2026, 9, 9)
    assert market.entry_type == "purchase"
    assert sum(1 for row in statement.rows if row.description.startswith("MARKET")) == 1
    redeemed = [row for row in statement.rows if "Plus Points Redeemed" in row.description]
    assert len(redeemed) == 1
    assert redeemed[0].entry_type == "cashback"
    assert redeemed[0].amount == money("15.00")
    assert all(row.amount != money("1350.00") for row in statement.rows)
    assert "100259835700003" not in _blob(statement)
    assert "Foreign Currency transaction fees" not in _blob(statement)
    replaced = read_statement_text_bytes(build_enbd()).replace("Emirates NBD", "FAB")
    with pytest.raises(UnsupportedLayout):
        extract(replaced)


def test_emirates_nbd_reads_a_wrapped_summary_as_one_points_credit():
    statement = extract(wrapped_summary_fixture())
    assert statement.computed_closing() == statement.closing_liability == money("145.00")
    assert statement.opening_liability == money("200.00")
    redeemed = [row for row in statement.rows if "Plus Points Redeemed" in row.description]
    assert len(redeemed) == 1
    assert redeemed[0].entry_type == "cashback"
    assert redeemed[0].amount == money("15.00")
    payment = next(row for row in statement.rows if row.entry_type == "payment")
    assert payment.amount == money("80.00")
    assert all(row.amount != money("1350.00") for row in statement.rows)
    assert "Foreign Currency transaction fees" not in _blob(statement)
    assert "100259835700003" not in _blob(statement)


def test_adcb_bank_drops_identifiers_and_keeps_the_card_payment_as_a_transfer():
    statement = extract(read_statement_text_bytes(build_bank()))
    assert statement.layout == "adcb-privilege-bank-v1"
    assert statement.kind == "bank"
    assert statement.account_last4 == "0123"
    assert statement.computed_closing() == statement.closing_liability == money("1360.00")
    blob = _blob(statement)
    assert ACCOUNT not in blob
    assert IBAN_VALUE not in blob
    assert CUSTOMER not in blob
    assert "B/F" not in blob
    descriptions = {row.description: row for row in statement.rows}
    assert "B/F" not in descriptions
    assert descriptions["CREDIT CARD PAYMNT"].entry_type == "transfer"
    assert descriptions["CREDIT CARD PAYMNT"].flow == "out"
    assert descriptions["SALARY"].category == "Income"
    assert descriptions["SALARY"].entry_type == "transfer"
    assert descriptions["SALARY"].flow == "in"
    assert descriptions["LOANRECOVERY-EMI"].entry_type == "transfer"
    assert "MBTRF TRF OUT TO SYNTHETIC PERSON" in descriptions
    assert "Send Money via Aani to Synthetic Friend" in descriptions
    assert all(row.entry_type != "purchase" for row in statement.rows)
    assert len(statement.rows) == 5


def test_adcb_bank_ocr_text_drops_garbled_lines_and_identifiers():
    statement = extract(ocr_fixture_text())
    assert statement.kind == "bank"
    assert statement.account_last4 == "0123"
    assert statement.computed_closing() == statement.closing_liability == money("1360.00")
    blob = _blob(statement)
    assert ACCOUNT not in blob
    assert IBAN_VALUE not in blob
    assert CUSTOMER not in blob
    assert "B/F" not in blob
    assert "Synthetic Person" not in blob
    assert "999.99" not in blob
    descriptions = {row.description: row for row in statement.rows}
    assert descriptions["CREDIT CARD PAYMNT"].entry_type == "transfer"
    assert descriptions["CREDIT CARD PAYMNT"].flow == "out"
    assert descriptions["SALARY"].flow == "in"
    assert descriptions["LOANRECOVERY-EMI"].flow == "out"
    assert "MBTRF TRF OUT TO" in descriptions
    assert "Send Money via Aani to Synthetic Friend" in descriptions
    assert len(statement.rows) == 5


async def test_named_layouts_post_without_treating_transfers_as_spending(client, migrator):
    import uuid

    from tests.conftest import csrf_headers, register
    from tests.test_ledger import PASSWORD, _owner_id, _run, _verify

    suffix = uuid.uuid4().hex[:8]
    username = f"layouts{suffix}"
    await register(client, username, f"{username}@example.com", PASSWORD)
    _verify(migrator, username)
    cards = (
        ("LuLu primary", "1414", "ADCB LuLu", "1414"),
        ("LuLu extra", "1415", "ADCB LuLu", "1414"),
        ("Platinum", "3636", "Emirates NBD Mastercard Platinum", "3636"),
    )
    for alias, last4, account_alias, account_last4 in cards:
        created = await client.post(
            "/api/v1/cards",
            headers=await csrf_headers(client),
            json={
                "alias": alias,
                "last4": last4,
                "account_alias": account_alias,
                "account_last4": account_last4,
            },
        )
        assert created.status_code == 201, created.text
    owner_id = await _owner_id(client)
    uploaded = await client.post(
        "/api/v1/imports",
        headers=await csrf_headers(client),
        files=[
            ("files", ("lulu.pdf", build_lulu(), "application/pdf")),
            ("files", ("FAB_MASTER.pdf", build_enbd(), "application/pdf")),
            ("files", ("bank.pdf", build_bank(), "application/pdf")),
        ],
    )
    assert uploaded.status_code == 202, uploaded.text
    _run(uploaded.json()["documents"], owner_id)
    listed = {row["original_name"]: row for row in (await client.get("/api/v1/documents")).json()["documents"]}
    assert listed["lulu.pdf"]["status"] == "committed", listed["lulu.pdf"]
    assert listed["FAB_MASTER.pdf"]["status"] == "committed", listed["FAB_MASTER.pdf"]
    assert listed["bank.pdf"]["status"] == "committed", listed["bank.pdf"]
    transactions = (await client.get("/api/v1/transactions")).json()["transactions"]
    by_desc = {row["description"]: row for row in transactions}
    assert "PERSONAL PAYMENT PLAN" not in by_desc
    assert by_desc["CREDIT CARD PAYMNT"]["entry_type"] == "transfer"
    assert by_desc["SALARY"]["entry_type"] == "transfer"
    assert by_desc["SALARY"]["category"] == "Income"
    summary = (await client.get("/api/v1/analytics/summary")).json()
    assert summary["net_spending"] == "227.90"
    assert summary["transfers"] == "1240.00"
    assert summary["payments"] == "120.00"


def read_statement_text_bytes(payload: bytes) -> str:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        path = Path(directory) / "statement.pdf"
        path.write_bytes(payload)
        return read_statement_text(path, None)
