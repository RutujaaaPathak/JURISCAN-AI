import pytest

import app.services.ocr as ocr_module
from app.core.exceptions import ValidationFailed
from app.services.analysis import MODEL_NAME, analyze_segments
from app.services.extraction import page_number_for_offset, validate_and_extract
from app.services.segmentation import segment_clauses
from tests.pdf_factory import image_only_pdf, mixed_pdf, multi_page_pdf

SCANNED_LINES = [
    "1. Indemnity",
    "The Supplier shall indemnify the Customer for all losses.",
]

NUMBERED_CONTRACT = """1. Indemnity
The Supplier shall indemnify the Customer against all losses without any cap.

2. Limitation of Liability
Notwithstanding the above, the Supplier's liability shall be unlimited.

3. Payment Terms
Payment shall be due within ninety (90) days of a valid invoice.

4. Governing Law
This Agreement is governed by the laws of Germany.
"""


def test_segmentation_splits_numbered_clauses():
    segments = segment_clauses(NUMBERED_CONTRACT)
    assert len(segments) == 4
    assert segments[0].heading is not None
    assert segments[0].start_offset == 0
    assert all(segment.text for segment in segments)


def test_segmentation_falls_back_to_paragraphs():
    text = "First paragraph with enough words to stand alone as a clause.\n\nSecond paragraph also long enough to be its own clause."
    segments = segment_clauses(text)
    assert len(segments) == 2


def test_rule_engine_flags_uncapped_indemnity_and_unlimited_liability():
    segments = segment_clauses(NUMBERED_CONTRACT)
    result = analyze_segments(segments)
    codes = {finding.rule_code for finding in result.findings}
    assert "UNCAPPED_INDEMNITY" in codes
    assert "UNLIMITED_LIABILITY" in codes
    assert "EXTENDED_PAYMENT_TERMS" in codes
    assert "FOREIGN_GOVERNING_LAW" in codes
    assert result.risk_score > 0
    assert MODEL_NAME in result.summary


def test_rule_engine_reports_no_findings_for_benign_text():
    segments = segment_clauses(
        "1. Definitions\nThis section defines the terms used in this agreement."
    )
    result = analyze_segments(segments)
    assert result.findings == []
    assert result.risk_score == 0
    assert "no" in result.summary.lower()


def test_extraction_rejects_unsupported_extension():
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(b"some content", "file.rtf", "application/rtf")
    assert exc.value.code == "unsupported_file_type"


def test_extraction_rejects_text_without_content():
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(b"   ", "file.txt", "text/plain")
    assert exc.value.code in {"invalid_document", "no_extractable_text"}


def test_extraction_of_txt_reports_word_count():
    extracted = validate_and_extract(
        b"1. Indemnity\nThe supplier shall indemnify the customer for all losses.",
        "file.txt",
        "text/plain",
    )
    assert extracted.file_type == "txt"
    assert extracted.word_count > 5
    assert extracted.language == "en"


def test_extraction_rejects_mime_type_mismatch():
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(b"%PDF-1.4 fake body content", "file.pdf", "text/plain")
    assert exc.value.code == "mime_type_mismatch"


def test_extraction_allows_generic_octet_stream():
    extracted = validate_and_extract(
        b"1. Clause\nThe supplier shall indemnify the customer for all losses.",
        "file.txt",
        "application/octet-stream",
    )
    assert extracted.file_type == "txt"


def test_extraction_ignores_mime_type_parameters():
    extracted = validate_and_extract(
        b"1. Clause\nThe supplier shall indemnify the customer for all losses.",
        "file.txt",
        "text/plain; charset=utf-8",
    )
    assert extracted.file_type == "txt"


def test_extraction_rejects_zip_masquerading_as_docx():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "not a word document")

    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(
            buffer.getvalue(),
            "file.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    assert exc.value.code == "invalid_document"


def test_extraction_rejects_binary_txt():
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(
            b"MZ\x90\x00\x03 binary executable content padded out",
            "file.txt",
            "text/plain",
        )
    assert exc.value.code == "invalid_document"


def test_extraction_enforces_max_size():
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(
            b"1. Clause\nA valid text body that is long enough to pass.",
            "file.txt",
            "text/plain",
            max_size_bytes=10,
        )
    assert exc.value.code == "file_too_large"


def test_extraction_records_timestamp_and_no_pages_for_txt():
    extracted = validate_and_extract(
        b"1. Indemnity\nThe supplier shall indemnify the customer for all losses.",
        "file.txt",
        "text/plain",
    )
    assert extracted.extracted_at is not None
    assert extracted.pages == []


def test_extraction_preserves_pdf_page_boundaries():
    data = multi_page_pdf(
        [
            ["1. Indemnity", "The Supplier shall indemnify the Customer for all losses."],
            ["2. Payment Terms", "Payment shall be due within one hundred (100) days."],
        ]
    )
    extracted = validate_and_extract(data, "contract.pdf", "application/pdf")

    assert extracted.file_type == "pdf"
    assert extracted.page_count == 2
    assert len(extracted.pages) == 2
    assert [span.page_number for span in extracted.pages] == [1, 2]
    assert extracted.pages[0].start_offset == 0
    assert extracted.pages[0].end_offset < extracted.pages[1].start_offset
    assert extracted.pages[1].end_offset == len(extracted.text)

    first = extracted.text.index("1. Indemnity")
    second = extracted.text.index("2. Payment Terms")
    assert page_number_for_offset(extracted.pages, first) == 1
    assert page_number_for_offset(extracted.pages, second) == 2


def test_page_number_for_offset_handles_missing_and_out_of_range():
    assert page_number_for_offset([], 0) is None
    assert page_number_for_offset([], None) is None

    extracted = validate_and_extract(
        multi_page_pdf([["1. Clause", "A first page with enough words to pass."]]),
        "contract.pdf",
        "application/pdf",
    )
    assert page_number_for_offset(extracted.pages, None) is None
    assert page_number_for_offset(extracted.pages, 10**6) == 1


def test_extraction_rejects_encrypted_pdf():
    data = multi_page_pdf(
        [["1. Confidential", "This document requires a password to open."]],
        encrypt=True,
    )
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(data, "locked.pdf", "application/pdf")
    assert exc.value.code == "encrypted_document"


def test_extraction_rejects_corrupt_pdf_body():
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(
            b"%PDF-1.4 not actually a pdf body", "broken.pdf", "application/pdf"
        )
    assert exc.value.code == "invalid_document"


def test_extraction_rejects_whitespace_only_txt():
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(b"     \n\t\n   ", "file.txt", "text/plain")
    assert exc.value.code == "no_extractable_text"


def test_extraction_decodes_utf16_txt():
    text = "1. Clause\nThe supplier shall indemnify the customer for all losses."
    extracted = validate_and_extract(
        text.encode("utf-16"), "file.txt", "text/plain"
    )
    assert extracted.file_type == "txt"
    assert "indemnify" in extracted.text


def _blank_pdf(page_count: int) -> bytes:
    """A text-free PDF (pages with no extractable text) without needing OCR deps."""

    return multi_page_pdf([[""] for _ in range(page_count)])


def test_scanned_pdf_uses_ocr_and_records_ocr_pages(monkeypatch):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: True)
    monkeypatch.setattr(
        ocr_module,
        "ocr_pdf_pages",
        lambda data, pages, *, dpi=200: {
            1: "1. Indemnity\nThe Supplier shall indemnify the Customer.",
            2: "2. Payment Terms\nPayment shall be due within ninety (90) days.",
        },
    )

    extracted = validate_and_extract(_blank_pdf(2), "scan.pdf", "application/pdf")

    assert extracted.file_type == "pdf"
    assert extracted.page_count == 2
    assert extracted.ocr_pages == [1, 2]
    assert "indemnify" in extracted.text.lower()
    assert "Payment" in extracted.text
    assert [span.page_number for span in extracted.pages] == [1, 2]


def test_mixed_pdf_keeps_native_text_and_ocrs_only_image_page(monkeypatch):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: True)
    seen: list[int] = []

    def fake_ocr(data, pages, *, dpi=200):
        seen.extend(pages)
        return {2: "2. Payment Terms\nPayment shall be due within ninety (90) days."}

    monkeypatch.setattr(ocr_module, "ocr_pdf_pages", fake_ocr)

    data = multi_page_pdf(
        [
            ["1. Indemnity", "The Supplier shall indemnify the Customer without any cap."],
            [""],
        ]
    )
    extracted = validate_and_extract(data, "mixed.pdf", "application/pdf")

    assert seen == [2]
    assert extracted.ocr_pages == [2]
    assert "indemnify" in extracted.text.lower()
    assert "Payment" in extracted.text
    assert [span.page_number for span in extracted.pages] == [1, 2]
    assert page_number_for_offset(extracted.pages, extracted.text.index("Payment")) == 2


def test_short_ocr_result_never_replaces_native_text(monkeypatch):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: True)
    monkeypatch.setattr(ocr_module, "ocr_pdf_pages", lambda *a, **k: {1: "x"})

    data = multi_page_pdf(
        [["1. Indemnity"], ["2. A second page with plenty of native words to keep."]]
    )
    extracted = validate_and_extract(data, "mixed.pdf", "application/pdf")

    assert extracted.ocr_pages == []
    assert "1. Indemnity" in extracted.text


def test_ocr_unavailable_for_fully_scanned_pdf(monkeypatch):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: False)

    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(_blank_pdf(2), "scan.pdf", "application/pdf")

    assert exc.value.code == "ocr_unavailable"
    assert exc.value.details["pages"] == [1, 2]


def test_ocr_disabled_rejects_fully_scanned_pdf():
    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(
            _blank_pdf(1), "scan.pdf", "application/pdf", allow_ocr=False
        )
    assert exc.value.code == "ocr_unavailable"


def test_ocr_disabled_keeps_native_text_of_mixed_pdf(monkeypatch):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: True)
    calls: list[int] = []
    monkeypatch.setattr(
        ocr_module, "ocr_pdf_pages", lambda *a, **k: calls.append(1) or {}
    )

    data = multi_page_pdf(
        [
            ["1. Indemnity", "The Supplier shall indemnify the Customer without any cap."],
            [""],
        ]
    )
    extracted = validate_and_extract(
        data, "mixed.pdf", "application/pdf", allow_ocr=False
    )

    assert extracted.ocr_pages == []
    assert "indemnify" in extracted.text.lower()
    assert calls == []


def test_ocr_failure_is_reported_for_scanned_pdf(monkeypatch):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: True)

    def boom(*args, **kwargs):
        raise ocr_module.OcrError("kaboom")

    monkeypatch.setattr(ocr_module, "ocr_pdf_pages", boom)

    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(_blank_pdf(1), "scan.pdf", "application/pdf")
    assert exc.value.code == "ocr_failed"


def test_scanned_pdf_with_no_ocr_text_reports_no_extractable_text(monkeypatch):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: True)
    monkeypatch.setattr(ocr_module, "ocr_pdf_pages", lambda *a, **k: {1: "   "})

    with pytest.raises(ValidationFailed) as exc:
        validate_and_extract(_blank_pdf(1), "scan.pdf", "application/pdf")
    assert exc.value.code == "no_extractable_text"


def test_genuine_ocr_reads_a_scanned_pdf():
    pytest.importorskip("rapidocr_onnxruntime")
    pytest.importorskip("pymupdf")

    data = image_only_pdf(SCANNED_LINES, dpi=200)
    extracted = validate_and_extract(data, "scan.pdf", "application/pdf")

    assert extracted.page_count == 1
    assert extracted.ocr_pages == [1]
    lowered = extracted.text.lower()
    assert "indemnify" in lowered or "indemnity" in lowered


def test_genuine_ocr_on_mixed_pdf_keeps_both_pages():
    pytest.importorskip("rapidocr_onnxruntime")
    pytest.importorskip("pymupdf")

    data = mixed_pdf(
        [
            ("text", ["1. Indemnity", "The Supplier shall indemnify the Customer."]),
            ("scan", ["2. Payment Terms", "Payment is due within ninety (90) days."]),
        ]
    )
    extracted = validate_and_extract(data, "mixed.pdf", "application/pdf")

    assert extracted.page_count == 2
    assert extracted.ocr_pages == [2]
    lowered = extracted.text.lower()
    assert "indemnify" in lowered
    assert "payment" in lowered
