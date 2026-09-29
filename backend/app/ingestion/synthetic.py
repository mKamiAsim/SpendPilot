"""Build the generic AED card fixture. It is not a bank statement."""

from __future__ import annotations

from io import BytesIO

from pikepdf import Dictionary, Encryption, Name, Pdf

LAYOUT = "generic-aed-card-v1"

FIXTURE_LINES = [
    "SPENDPILOT SYNTHETIC FIXTURE",
    f"Layout: {LAYOUT}",
    "This is not a bank statement.",
    "Account alias: Shared liability",
    "Account last4: 4410",
    "Period start: 2026-09-01",
    "Period end: 2026-09-30",
    "Opening liability: 1000.00",
    "Closing liability: 1215.00",
    "Card: Everyday | 4412",
    "Card: Supplementary | 4413",
    "ROW | 2026-09-02 | 4412 | purchase | Groceries | Carrefour | 200.00",
    "ROW | 2026-09-02 | 4412 | purchase | Groceries | Carrefour | 200.00",
    "ROW | 2026-09-03 | 4413 | purchase | Dining | Cafe | 50.00",
    "ROW | 2026-09-05 | 4412 | fee | Fees and interest | Card fee | 25.00",
    "ROW | 2026-09-06 | 4412 | payment | Transfers | Payment received | 300.00",
    "ROW | 2026-09-07 | 4412 | refund | Groceries | Carrefour refund | 20.00",
    "ROW | 2026-09-08 | 4412 | cash_withdrawal | Cash | Cash withdrawal | 100.00",
    "ROW | 2026-09-09 | 4412 | transfer | Transfers | Transfer to own account | 40.00",
]


def fixture_lines(*, closing: str = "1215.00", note: str | None = None) -> list[str]:
    lines = []
    for line in FIXTURE_LINES:
        if line.startswith("Closing liability:"):
            lines.append(f"Closing liability: {closing}")
        else:
            lines.append(line)
    if note:
        if not note.isascii() or any(character in note for character in "()\r\n\\"):
            raise ValueError("Fixture notes must be plain ASCII.")
        lines.append(f"Note: {note}")
    return lines


def build_fixture_pdf(
    *,
    password: str | None = None,
    closing: str = "1215.00",
    note: str | None = None,
) -> bytes:
    lines = fixture_lines(closing=closing, note=note)
    pdf = Pdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    commands = ["BT", "/F1 10 Tf", "48 740 Td", "12 TL"]
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({escaped}) Tj")
        commands.append("T*")
    commands.append("ET")
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Contents = pdf.make_stream(" ".join(commands).encode("ascii"))
    page.Resources = Dictionary(Font=Dictionary(F1=font))
    raw = BytesIO()
    pdf.save(raw)
    if not password:
        return raw.getvalue()
    encrypted = BytesIO()
    Pdf.open(BytesIO(raw.getvalue())).save(encrypted, encryption=Encryption(owner=password, user=password))
    return encrypted.getvalue()
