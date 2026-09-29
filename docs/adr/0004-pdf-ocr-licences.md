# ADR 0004: PDF and OCR licences

Date: 29 September 2026

## Decision

Text extraction, when the document pipeline is built, will use libraries whose licences were read from the tagged upstream files below. Those packages are locked as optional extras. They are not installed in the phase 1 image, and Tesseract language data is not copied into it.

| Component | Version | Licence | Source checked |
|---|---|---|---|
| pypdf | 6.19.0 | BSD-3-Clause | `py-pdf/pypdf` tag `6.19.0` `LICENSE` |
| pikepdf | 10.15.0 | MPL-2.0 | `pikepdf/pikepdf` tag `v10.15.0` `LICENSE.txt` |
| pdfplumber | 0.11.10 | MIT | `jsvine/pdfplumber` tag `v0.11.10` `LICENSE.txt` |
| ocrmypdf | 17.13.0 | MPL-2.0 | `ocrmypdf/OCRmyPDF` tag `v17.13.0` `LICENSE` |
| Tesseract | not packaged yet | Apache-2.0 | `tesseract-ocr/tesseract` `main` `LICENSE` |
| tessdata (`eng`, `ara`) | not packaged yet | Apache-2.0 | `tesseract-ocr/tessdata` `main` `LICENSE` |

Redistribution of the Apache-2.0 OCR engine and `eng`/`ara` traineddata is allowed with the Apache notices retained. That packaging waits until a document worker actually OCRs pages. English and Arabic assets are required then, not now.

## Unverified

No bank or card statement PDF is in this repository. No bank is named or certified. Parser accuracy is unverified.
