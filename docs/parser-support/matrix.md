# Parser support

This build reads one synthetic layout. It does not name or certify a bank. OCR is not in the image.

| Layout | Source | What it covers | Status |
|---|---|---|---|
| `generic-aed-card-v1` | Synthetic PDF built in `backend/app/ingestion/synthetic.py` | Shared AED liability, two cards, purchase, fee, payment, refund, cash withdrawal, transfer. Same-day same-amount purchases are both kept. | Text extraction only. Covered by `backend/tests/test_ledger.py`. |
| Anything else | Uploaded PDF | No rows are invented. | That file fails as `unsupported_layout` or `no_text`. The rest of the batch continues. |

A scanned page has no extractable text here, so it fails that file. OCRmyPDF and Tesseract are not installed.

The September figures on Overview, Transactions, and Advisor in `npm run dev` are a development fixture. They are not this layout and they are not in the production build.
