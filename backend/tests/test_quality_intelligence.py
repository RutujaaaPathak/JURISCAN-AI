from datetime import datetime, timezone

import pymupdf

from app.core.database import SessionLocal
from app.models import Analysis, Clause, Document, User
from app.services import processing as processing_module
from app.services.analysis import analyze_segments
from app.services.clause_quality import assess_clause_quality
from app.services.extraction import ExtractedDocument, PageSpan
from app.services.legal_normalization import normalize_legal_text, normalize_segment
from app.services.ocr_layout import OcrLineSpan
from app.services.processing import run_processing
from app.services.report import build_report_pdf
from app.services.segmentation import Segment, segment_clauses

SCANNED_CONTRACT = (
    "1. Indemnity\n"
    "The Supplier shall indemnitv the Customer against all losses.\n\n"
    "2. Payment\n"
    "Payment shall be due within thirty (30) days of a valid invoice.\n"
)


def _fake_extracted() -> ExtractedDocument:
    text = SCANNED_CONTRACT
    return ExtractedDocument(
        text=text,
        file_type="txt",
        page_count=1,
        word_count=len(text.split()),
        language="en",
        extracted_at=datetime.now(timezone.utc),
        pages=[
            PageSpan(
                page_number=1,
                start_offset=0,
                end_offset=len(text),
                char_count=len(text),
                source="ocr",
                ocr_confidence=0.4,
            )
        ],
        ocr_pages=[1],
        ocr_line_spans=[
            OcrLineSpan(
                text=text,
                confidence=0.4,
                start_offset=0,
                end_offset=len(text),
                bbox=(0.0, 0.0, 100.0, 100.0),
            )
        ],
        quality_warnings=[
            "Document OCR confidence 0.40 is below the warning threshold 0.65."
        ],
    )


def test_normalization_keeps_original_and_fixes_ocr_for_detection():
    segment = Segment(
        number=1,
        heading="Indemnity",
        text="1. Indemnity\nThe Supplier shall indemnitv the Customer.",
        start_offset=0,
        end_offset=55,
    )

    normalized = normalize_segment(segment)

    assert normalized.text == segment.text
    assert "indemnify" in (normalized.normalized_text or "")
    assert normalized.normalization_changes
    assert any(
        change["rule"] == "ocr_term"
        for change in normalized.normalization_changes
    )

    result = analyze_segments([normalized])
    assert "UNCAPPED_INDEMNITY" in {
        finding.rule_code for finding in result.findings
    }


def test_normalization_records_synonym_rewrites():
    normalized, changes = normalize_legal_text(
        "The Supplier shall hold harmless the Customer. Personal information "
        "shall be protected."
    )

    assert "indemnify" in normalized
    assert "personal data" in normalized
    assert {change["rule"] for change in changes} >= {
        "hold_harmless",
        "personal_information",
    }


def test_clause_quality_flags_low_confidence_ocr_lines():
    segments = segment_clauses(SCANNED_CONTRACT)
    page = PageSpan(
        page_number=1,
        start_offset=0,
        end_offset=len(SCANNED_CONTRACT),
        char_count=len(SCANNED_CONTRACT),
        source="ocr",
        ocr_confidence=0.4,
    )
    span = OcrLineSpan(
        text=SCANNED_CONTRACT,
        confidence=0.4,
        start_offset=0,
        end_offset=len(SCANNED_CONTRACT),
    )

    qualities = assess_clause_quality(segments, [page], [span])

    assert len(qualities) == len(segments)
    assert all(quality["source"] == "ocr" for quality in qualities)
    assert all(quality["requires_verification"] for quality in qualities)
    assert all(quality["warnings"] for quality in qualities)
    assert qualities[0]["confidence"] == 0.4


def test_clause_quality_does_not_flag_native_text():
    segments = segment_clauses(SCANNED_CONTRACT)
    page = PageSpan(
        page_number=1,
        start_offset=0,
        end_offset=len(SCANNED_CONTRACT),
        char_count=len(SCANNED_CONTRACT),
        source="native",
    )

    qualities = assess_clause_quality(segments, [page], [])

    assert all(quality["requires_verification"] is False for quality in qualities)
    assert all(quality["source"] == "native" for quality in qualities)


def test_processing_persists_quality_and_review_metadata(monkeypatch):
    monkeypatch.setattr(
        processing_module,
        "validate_and_extract",
        lambda *args, **kwargs: _fake_extracted(),
    )

    with SessionLocal() as session:
        user = User(
            email="quality@example.com",
            username="quality",
            full_name="Quality User",
        )
        session.add(user)
        session.flush()
        document = Document(
            user_id=user.id,
            title="Scanned contract",
            filename="scan.txt",
            file_type="txt",
            status="PROCESSING",
        )
        session.add(document)
        session.flush()

        run_processing(
            session,
            document,
            data=b"fake scan",
            filename="scan.txt",
            content_type="text/plain",
            title="Scanned contract",
            max_size_bytes=1024 * 1024,
        )

        clauses = session.query(Clause).order_by(Clause.clause_number).all()
        analysis = session.query(Analysis).one()

        assert clauses[0].text.startswith("1. Indemnity")
        assert "indemnify" in (clauses[0].normalized_text or "")
        assert clauses[0].normalization_changes
        assert clauses[0].ocr_quality["requires_verification"] is True

        finding = next(
            item for item in analysis.risk_findings if item.rule_code == "UNCAPPED_INDEMNITY"
        )
        assert finding.requires_review is True
        assert finding.review_reason
        assert "verify" in finding.review_reason.lower()
        assert finding.ocr_confidence == 0.4
        assert "OCR verification notice" in (analysis.summary or "")


def test_upload_exposes_quality_counts_and_review_fields(client, monkeypatch):
    monkeypatch.setattr(
        processing_module,
        "validate_and_extract",
        lambda *args, **kwargs: _fake_extracted(),
    )

    response = client.post(
        "/api/documents",
        files={"file": ("scan.txt", b"fake scan", "text/plain")},
        data={"title": "Scanned contract"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["clauses_requiring_verification"] > 0
    assert body["unverified_findings"] > 0
    assert body["clauses"][0]["normalized_text"]
    assert body["clauses"][0]["ocr_quality"]["requires_verification"] is True
    assert any(finding["requires_review"] for finding in body["analysis"]["findings"])


def test_report_contains_quality_and_manual_review_sections(monkeypatch):
    monkeypatch.setattr(
        processing_module,
        "validate_and_extract",
        lambda *args, **kwargs: _fake_extracted(),
    )

    with SessionLocal() as session:
        user = User(
            email="report-quality@example.com",
            username="reportquality",
            full_name="Report Quality User",
        )
        session.add(user)
        session.flush()
        document = Document(
            user_id=user.id,
            title="Scanned contract",
            filename="scan.txt",
            file_type="txt",
            status="PROCESSING",
        )
        session.add(document)
        session.flush()

        run_processing(
            session,
            document,
            data=b"fake scan",
            filename="scan.txt",
            content_type="text/plain",
            title="Scanned contract",
            max_size_bytes=1024 * 1024,
        )

        analysis = session.query(Analysis).one()
        clauses_by_id = {clause.id: clause for clause in document.clauses}
        pdf = build_report_pdf(document, analysis, clauses_by_id)

    assert pdf.startswith(b"%PDF")
    report = pymupdf.open(stream=pdf, filetype="pdf")
    text = "\n".join(page.get_text() for page in report)
    report.close()
    assert "Text quality and verification" in text
    assert "Manual verification required" in text
