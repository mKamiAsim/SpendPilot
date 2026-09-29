# ADR 0004: PDF and OCR licences

Date: 29 September 2026

## Decision

Text extraction uses libraries whose licences were read from the tagged upstream files below. The runtime image installs pypdf, pikepdf, pdfplumber, and OCRmyPDF. A PDF that already has a text layer is returned from that extraction and is not sent through OCR. A page with no text is OCR'd with English and Arabic Tesseract data. The PDF password is used only to write a temporary decrypted file. It is not an argument to OCR.

| Component | Version | Licence | Source checked |
|---|---|---|---|
| pypdf | 6.19.0 | BSD-3-Clause | `py-pdf/pypdf` tag `6.19.0` `LICENSE` |
| pikepdf | 10.15.0 | MPL-2.0 | `pikepdf/pikepdf` tag `v10.15.0` `LICENSE.txt` |
| pdfplumber | 0.11.10 | MIT | `jsvine/pdfplumber` tag `v0.11.10` `LICENSE.txt` |
| ocrmypdf | 17.13.0 | MPL-2.0 | `ocrmypdf/OCRmyPDF` tag `v17.13.0` `LICENSE` |
| Tesseract | Debian `tesseract-ocr` 5.3.0-2 in the runtime image | Apache-2.0 | `/usr/share/doc/tesseract-ocr/copyright` names upstream `tesseract-ocr` as Apache-2.0 |
| tessdata (`eng`) | Debian `tesseract-ocr-eng` 1:4.1.0-2 | Apache-2.0 | `/usr/share/doc/tesseract-ocr-eng/copyright` names upstream `tessdata_fast` as Apache-2.0 |
| tessdata (`ara`) | Debian `tesseract-ocr-ara` 1:4.1.0-2 | Apache-2.0 | `/usr/share/doc/tesseract-ocr-ara/copyright` names upstream `tessdata_fast` as Apache-2.0 |

Redistribution of the Apache-2.0 OCR engine and the `eng` and `ara` traineddata is allowed when the Apache notices stay with the files. The image installs those three Debian packages and fails the build if any copyright file is missing or if `tesseract --list-langs` lacks `eng` or `ara`. No separate tessdata archive is vendored. The same package names are installed in CI.

## Unverified

No bank or card statement PDF is in this repository. No bank is named or certified. OCR of a real statement is unverified. A synthetic image that says HELLO is not a bank PDF.
