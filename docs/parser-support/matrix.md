# Parser support

This build reads two synthetic layouts. It does not name or certify a bank. OCR is not in the image.

| Layout | Source | What it covers | Status |
|---|---|---|---|
| `generic-aed-card-v1` | Synthetic PDF built in `backend/app/ingestion/synthetic.py` | Shared AED liability, two cards, purchase, fee, payment, refund, cash withdrawal, transfer. Same-day same-amount purchases are both kept. | Text extraction only. Covered by `backend/tests/test_ledger.py`. |
| `generic-aed-bank-v1` | Synthetic PDF built in `backend/app/ingestion/bank.py` | One current-account transfer labelled as a card payment. Not a named bank. The transfer is not a second spending event. | Text extraction only. Covered by `backend/tests/test_product.py`. |
| Anything else | Uploaded PDF, including a file that only contains instructions | No rows are invented. Instruction text is not a layout and is not obeyed. | That file fails as `unsupported_layout` or `no_text`. The rest of the batch continues. Covered by `backend/tests/test_hardening.py`. |

A scanned page has no extractable text here, so it fails that file. OCRmyPDF and Tesseract are not installed.

The September figures on Overview, Transactions, and Advisor in `npm run dev` are a development fixture. They are not this layout and they are not in the production build.
