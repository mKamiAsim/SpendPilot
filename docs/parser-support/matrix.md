# Parser support

This build reads synthetic fixtures. Real statement files were not used, and these layouts are not confirmed against a real PDF. A text PDF is not sent through OCR. A scanned page with no text layer is read with English and Arabic Tesseract data. No bank is certified.

| Layout | Source | What it covers | Status |
|---|---|---|---|
| `generic-aed-card-v1` | Synthetic PDF built in `backend/app/ingestion/synthetic.py` | Shared AED liability, two cards, purchase, fee, payment, refund, cash withdrawal, transfer. Same-day same-amount purchases are both kept. | Text extraction only. Covered by `backend/tests/test_ledger.py`. |
| `generic-aed-bank-v1` | Synthetic PDF built in `backend/app/ingestion/bank.py` | One current-account transfer labelled as a card payment. Not a named bank. The transfer is not a second spending event. | Text extraction only. Covered by `backend/tests/test_product.py`. |
| `adcb-lulu-card-v1` | Synthetic text in `backend/app/ingestion/layouts/adcb_lulu.py` | ADCB LuLu card. Page 1 text is not also OCR'd. `CR` is a credit. Two cards. The undated personal payment plan is not a purchase. | Synthetic only. Covered by `backend/tests/test_layouts.py`. Real file not confirmed. |
| `emirates-islamic-card-v1` | Synthetic text in `backend/app/ingestion/layouts/emirates_islamic.py` | One parser for Switch Cashback and Amazon World. Row dates have no year. A foreign-currency continuation line is not a transaction. The summary strip is not summed once per page. | Synthetic only. Covered by `backend/tests/test_layouts.py`. Real file not confirmed. |
| `emirates-nbd-mastercard-platinum-v1` | Synthetic text in `backend/app/ingestion/layouts/emirates_nbd.py` | Emirates NBD Mastercard Platinum. Issuer text decides the layout when a filename says FAB. A Plus Points redemption is one AED credit. The points adjustment is not a second credit. | Synthetic only. Covered by `backend/tests/test_layouts.py`. Real file not confirmed. |
| `adcb-privilege-bank-v1` | Synthetic text shaped like the OCR target in `backend/app/ingestion/layouts/adcb_bank.py` | ADCB consolidated statement. Separate debit and credit columns. `CREDIT CARD PAYMNT` is a transfer. `B/F` is not a transaction. Account numbers and IBANs are dropped. | Synthetic only. Covered by `backend/tests/test_layouts.py`. Real file not confirmed. |
| Anything else | Uploaded PDF, including a file that only contains instructions | No rows are invented. Instruction text is not a layout and is not obeyed. | That file fails as `unsupported_layout` or `no_text`. The rest of the batch continues. Covered by `backend/tests/test_hardening.py`. |

A scanned PDF page with no text layer is sent through OCRmyPDF with Tesseract `eng` and `ara`. A page that already has text is not sent through OCR. A JPEG or PNG is not opened as a PDF. Tesseract reads it, then the bank text parser keeps a row only when the description shows debit or credit. Garbled lines are left out. A page that still yields no text fails that file as `no_text`. See `docs/adr/0004-pdf-ocr-licences.md`.

The September figures on Overview, Transactions, and Advisor in `npm run dev` are a development fixture. They are not these layouts and they are not in the production build.
