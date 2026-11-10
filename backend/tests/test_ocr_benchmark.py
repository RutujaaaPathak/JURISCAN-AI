from datetime import datetime, timezone
import os

import pytest

from app.services.extraction import ExtractedDocument, PageSpan
from app.services.ocr_layout import OcrLine, layout_lines, reconstruct_page_text
from app.services.segmentation import segment_clauses
from benchmarks import ocr_dataset
from benchmarks.ocr_dataset import BenchmarkCase, PageSpec, benchmark_cases
from benchmarks.ocr_metrics import (
    canonical_text,
    character_error_rate,
    levenshtein,
    marker_order_ok,
    marker_positions,
    page_offset_metrics,
    risk_metrics,
    segmentation_metrics,
    word_error_rate,
    word_order_accuracy,
)
from benchmarks.run_ocr_benchmark import (
    _aggregate,
    _environment,
    render_markdown,
    run_case,
)


def _line(text, x0, y0, x1, y1, confidence=0.9):
    return OcrLine(
        text=text,
        confidence=confidence,
        bbox=(x0, y0, x1, y1),
    )


def test_metric_primitives_are_deterministic():
    assert canonical_text("\u201cIndemnity\u201d \u2014  A\tB") == (
        '"indemnity" - a b'
    )
    assert levenshtein("kitten", "sitting") == 3
    assert character_error_rate("abc", "abd") == round(1 / 3, 6)
    assert word_error_rate("one two", "one too") == 0.5
    assert word_order_accuracy("one two three", "three one two") == round(
        2 / 3, 6
    )
    assert marker_positions("B then A", ("A", "B")) == [7, 0]
    assert not marker_order_ok("B then A", ("A", "B"))
    assert marker_order_ok("A then B", ("A", "B"))


def test_risk_metrics_reports_recall_and_misses():
    metrics = risk_metrics(
        {"UNLIMITED_LIABILITY", "EXTRA_CODE"},
        ("UNLIMITED_LIABILITY", "AUTO_RENEWAL"),
    )

    assert metrics["recall"] == 0.5
    assert metrics["false_negative_codes"] == ["AUTO_RENEWAL"]
    assert metrics["false_positive_codes"] == ["EXTRA_CODE"]


def test_segmentation_metrics_checks_exact_offsets_and_marker_order():
    text = "1. Definitions\nAlpha\n\n2. Payment\nBeta\n"
    segments = segment_clauses(text)

    metrics = segmentation_metrics(
        text,
        segments,
        ("1. Definitions", "2. Payment"),
    )

    assert metrics["marker_recall"] == 1.0
    assert metrics["marker_order_ok"] is True
    assert metrics["exact_source_offsets"] is True
    assert metrics["overlapping_segments"] == 0


def test_page_offset_metrics_maps_markers_to_the_right_page():
    page_one = "Page one\n\n1. Start"
    page_two = "Page two\n\n2. End"
    text = f"{page_one}\n\n{page_two}"
    second_start = len(page_one) + 2
    extracted = ExtractedDocument(
        text=text,
        file_type="pdf",
        page_count=2,
        word_count=len(text.split()),
        language="en",
        extracted_at=datetime.now(timezone.utc),
        pages=[
            PageSpan(1, 0, len(page_one), len(page_one)),
            PageSpan(2, second_start, len(text), len(text) - second_start),
        ],
    )

    metrics = page_offset_metrics(
        extracted,
        ((1, "1. Start"), (2, "2. End")),
    )

    assert metrics["ordered_page_numbers"] is True
    assert metrics["contiguous_spans"] is True
    assert metrics["page_marker_accuracy"] == 1.0


def test_manifest_is_deterministic_and_covers_required_failure_modes():
    first = ocr_dataset.manifest()
    second = ocr_dataset.manifest()

    assert first == second
    assert first["version"] == ocr_dataset.BENCHMARK_VERSION
    assert "Synthetic legal text" in first["disclaimer"]
    case_ids = [case["id"] for case in first["cases"]]
    assert len(case_ids) == len(set(case_ids)) == 9
    tags = {tag for case in first["cases"] for tag in case["tags"]}
    assert {
        "rotation",
        "skew",
        "columns",
        "table",
        "mixed",
        "stamp",
        "long",
        "low-quality",
    } <= tags
    assert all(
        page["ground_truth"]
        for case in first["cases"]
        for page in case["pages"]
    )


def test_generated_benchmark_pdfs_are_valid_and_complete():
    import pymupdf

    for case in benchmark_cases():
        data = ocr_dataset.build_case_pdf(case)
        assert data.startswith(b"%PDF")
        document = pymupdf.open(stream=data, filetype="pdf")
        try:
            assert document.page_count == len(case.pages)
        finally:
            document.close()


def test_layout_keeps_two_columns_in_column_order():
    lines = [
        _line("4. Limitation of Liability", 72, 90, 300, 110),
        _line("The Supplier shall have", 72, 115, 280, 135),
        _line("5. Indemnity", 380, 88, 550, 108),
        _line("The Supplier shall indemnify", 380, 113, 610, 133),
    ]

    ordered = layout_lines(lines, 612, 792)

    assert [line.text for line in ordered] == [
        "4. Limitation of Liability",
        "The Supplier shall have",
        "5. Indemnity",
        "The Supplier shall indemnify",
    ]
    assert [line.column for line in ordered] == [0, 0, 1, 1]
    assert not any(line.table_row for line in ordered)


def test_layout_orders_skewed_rows_by_vertical_center():
    lines = [
        _line("5. Indemnity", 186, 300, 386, 330),
        _line(
            "The Supplier shall indemnify and hold harmless the Customer",
            195,
            280,
            1177,
            350,
        ),
    ]

    ordered = layout_lines(lines, 1224, 1584)

    assert [line.text for line in ordered] == [
        "5. Indemnity",
        "The Supplier shall indemnify and hold harmless the Customer",
    ]


def test_layout_orders_table_cells_left_to_right_with_vertical_jitter():
    lines = [
        _line("Party", 50, 100, 120, 115),
        _line("Amount", 250, 100, 330, 115),
        _line("Term", 450, 99, 520, 114),
        _line("Alice", 50, 130, 100, 145),
        _line("100", 250, 132, 300, 147),
        _line("30 days", 450, 129, 520, 144),
    ]

    ordered = layout_lines(lines, 600, 400)

    assert reconstruct_page_text(ordered) == (
        "Party | Amount | Term\n\nAlice | 100 | 30 days"
    )


def test_runner_measures_a_native_document_end_to_end():
    case = BenchmarkCase(
        case_id="native_smoke",
        category="native_smoke",
        description="Native-only smoke case for the benchmark runner.",
        pages=(
            PageSpec(
                kind="native",
                lines=("1. Definitions", "Alpha"),
                expected_source="native",
                page_marker="1. Definitions",
            ),
        ),
        clause_markers=("1. Definitions",),
    )

    result = run_case(case, dpi=200)

    assert result["status"] == "ok"
    assert result["document"]["cer"] == 0.0
    assert result["document"]["wer"] == 0.0
    assert result["sources"]["actual"] == ["native"]
    assert result["sources"]["accuracy"] == 1.0
    assert result["segmentation"]["exact_source_offsets"] is True
    assert result["page_offsets"]["contiguous_spans"] is True

    aggregate = _aggregate([result])
    assert aggregate["ok_count"] == 1
    assert aggregate["mean_cer"] == 0.0

    report = render_markdown([result], _environment(200))
    assert "native_smoke" in report
    assert "## Measured results" in report


@pytest.mark.skipif(
    os.environ.get("JURISCAN_RUN_OCR_BENCHMARK") != "1",
    reason="set JURISCAN_RUN_OCR_BENCHMARK=1 to run the real OCR smoke test",
)
def test_real_ocr_clean_contract_smoke():
    case = next(
        item for item in benchmark_cases() if item.case_id == "clean_contract"
    )

    result = run_case(case, dpi=200)

    assert result["status"] == "ok"
    assert result["document"]["cer"] < 0.05
    assert result["document"]["word_order_accuracy"] > 0.95
    assert result["sources"]["accuracy"] == 1.0
