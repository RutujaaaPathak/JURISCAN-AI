r"""Run the OCR regression benchmark and write a measured report.

Usage (from the backend directory, so ``app`` and ``benchmarks`` are importable):

    .\.venv\Scripts\python.exe -m benchmarks.run_ocr_benchmark

The runner measures the real Phase 1-3 pipeline through
``validate_and_extract``. It does not claim legal accuracy and does not use
external or client documents. Every number in the generated report comes from
the run recorded in the accompanying JSON file.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib import import_module, metadata
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

from app.config import settings
from app.services.analysis import analyze_segments
from app.services.clause_quality import assess_clause_quality
from app.services.extraction import validate_and_extract
from app.services.legal_normalization import normalize_segments
from app.services.segmentation import segment_clauses
from benchmarks import ocr_dataset
from benchmarks.ocr_dataset import BenchmarkCase, benchmark_cases, build_case_pdf, manifest
from benchmarks.ocr_metrics import (
    canonical_text,
    character_error_rate,
    measure_pages,
    page_offset_metrics,
    risk_metrics,
    segmentation_metrics,
    word_error_rate,
    word_order_accuracy,
)


def _environment(dpi: int) -> dict:
    packages: dict[str, str | None] = {}
    for module_name, distribution in (
        ("rapidocr_onnxruntime", "rapidocr-onnxruntime"),
        ("pymupdf", "pymupdf"),
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("pypdf", "pypdf"),
    ):
        try:
            module = import_module(module_name)
        except Exception:
            packages[distribution] = None
            continue
        version = getattr(module, "__version__", None)
        if not version:
            try:
                version = metadata.version(distribution)
            except metadata.PackageNotFoundError:
                version = "unknown"
        packages[distribution] = version
    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": packages,
        "settings": {
            "ocr_enabled": settings.ocr_enabled,
            "ocr_render_dpi": dpi,
            "ocr_preprocess_enabled": settings.ocr_preprocess_enabled,
            "ocr_deskew_enabled": settings.ocr_deskew_enabled,
            "ocr_rotation_detection_enabled": settings.ocr_rotation_detection_enabled,
            "ocr_layout_analysis_enabled": settings.ocr_layout_analysis_enabled,
            "ocr_low_confidence_threshold": settings.ocr_low_confidence_threshold,
            "ocr_quality_warning_threshold": settings.ocr_quality_warning_threshold,
            "ocr_native_recheck_threshold": settings.ocr_native_recheck_threshold,
            "ocr_merge_margin": settings.ocr_merge_margin,
        },
    }


def _page_markers(case: BenchmarkCase) -> tuple[tuple[int, str], ...]:
    return tuple(
        (index + 1, page.page_marker)
        for index, page in enumerate(case.pages)
        if page.page_marker
    )


def run_case(case: BenchmarkCase, *, dpi: int) -> dict:
    build_start = time.perf_counter()
    tracemalloc.start()
    try:
        pdf = build_case_pdf(case)
        pdf_build_seconds = time.perf_counter() - build_start
        extract_start = time.perf_counter()
        try:
            extracted = validate_and_extract(
                pdf,
                f"{case.case_id}.pdf",
                "application/pdf",
                allow_ocr=True,
                ocr_min_page_chars=settings.ocr_min_page_chars,
                ocr_dpi=dpi,
                max_pdf_pages=settings.max_pdf_pages,
            )
        except Exception as exc:
            return {
                "case_id": case.case_id,
                "category": case.category,
                "description": case.description,
                "tags": list(case.tags),
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
                "pdf_build_seconds": round(pdf_build_seconds, 6),
                "extract_seconds": round(time.perf_counter() - extract_start, 6),
                "peak_memory_mb": round(
                    tracemalloc.get_traced_memory()[1] / (1024 * 1024), 3
                ),
            }
        extract_seconds = time.perf_counter() - extract_start
        peak_memory_mb = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
    finally:
        tracemalloc.stop()

    expected_pages = tuple(page.expected_text() for page in case.pages)
    expected_sources = case.expected_sources()
    page_measurements = measure_pages(
        extracted, expected_pages, expected_sources
    )
    expected_document = "\n\n".join(expected_pages)
    document_cer = character_error_rate(expected_document, extracted.text)
    document_wer = word_error_rate(expected_document, extracted.text)
    document_order = word_order_accuracy(expected_document, extracted.text)

    segments = segment_clauses(extracted.text)
    segmentation = segmentation_metrics(
        extracted.text, segments, case.clause_markers
    )
    offsets = page_offset_metrics(extracted, _page_markers(case))

    clause_qualities = assess_clause_quality(
        segments, extracted.pages, extracted.ocr_line_spans
    )
    normalized_segments = normalize_segments(segments)
    analysis = analyze_segments(normalized_segments)
    risk = risk_metrics(
        {finding.rule_code for finding in analysis.findings},
        case.expected_risk_codes,
    )

    review_indexes = {
        index
        for index, quality in enumerate(clause_qualities)
        if quality.get("requires_verification")
    }
    review_findings = sum(
        1
        for finding in analysis.findings
        if finding.segment_index in review_indexes
    )
    source_accuracy = round(
        sum(
            1
            for measurement in page_measurements
            if measurement.source == measurement.expected_source
        )
        / len(page_measurements),
        6,
    ) if page_measurements else 1.0
    ocr_page_confidences = [
        measurement.confidence
        for measurement in page_measurements
        if measurement.source == "ocr" and measurement.confidence is not None
    ]

    return {
        "case_id": case.case_id,
        "category": case.category,
        "description": case.description,
        "tags": list(case.tags),
        "status": "ok",
        "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
        "pdf_build_seconds": round(pdf_build_seconds, 6),
        "extract_seconds": round(extract_seconds, 6),
        "total_seconds": round(pdf_build_seconds + extract_seconds, 6),
        "peak_memory_mb": round(peak_memory_mb, 3),
        "document": {
            "cer": document_cer,
            "wer": document_wer,
            "word_order_accuracy": document_order,
            "characters": len(canonical_text(extracted.text)),
            "words": len(canonical_text(extracted.text).split()),
        },
        "pages": [asdict(measurement) for measurement in page_measurements],
        "sources": {
            "expected": list(expected_sources),
            "actual": [measurement.source for measurement in page_measurements],
            "accuracy": source_accuracy,
            "ocr_pages": list(extracted.ocr_pages),
        },
        "segmentation": segmentation,
        "page_offsets": offsets,
        "quality": {
            "document_confidence": (
                extracted.ocr_quality.confidence
                if extracted.ocr_quality is not None
                else None
            ),
            "document_low_confidence_ratio": (
                extracted.ocr_quality.low_confidence_ratio
                if extracted.ocr_quality is not None
                else 0.0
            ),
            "warnings": list(extracted.quality_warnings),
            "mean_page_confidence": (
                round(statistics.mean(ocr_page_confidences), 6)
                if ocr_page_confidences
                else None
            ),
            "clauses_requiring_review": len(review_indexes),
            "clause_count": len(segments),
            "review_findings": review_findings,
            "review_clause_indexes": sorted(review_indexes),
        },
        "risk": risk,
        "clause_marker_order_ok": segmentation["marker_order_ok"],
        "expected_pages": list(expected_pages),
    }


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 6) if values else None


def _fmt(value, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _aggregate(results: list[dict]) -> dict:
    ok = [result for result in results if result.get("status") == "ok"]
    by_category: dict[str, dict] = {}
    for result in ok:
        category = result["category"]
        bucket = by_category.setdefault(
            category,
            {
                "cases": 0,
                "cer": [],
                "wer": [],
                "order": [],
                "risk_recall": [],
                "confidence": [],
                "source_accuracy": [],
                "review_cases": 0,
                "seconds": [],
            },
        )
        bucket["cases"] += 1
        bucket["cer"].append(result["document"]["cer"])
        bucket["wer"].append(result["document"]["wer"])
        bucket["order"].append(result["document"]["word_order_accuracy"])
        bucket["risk_recall"].append(result["risk"]["recall"])
        bucket["source_accuracy"].append(result["sources"]["accuracy"])
        bucket["seconds"].append(result["total_seconds"])
        if result["quality"]["mean_page_confidence"] is not None:
            bucket["confidence"].append(
                result["quality"]["mean_page_confidence"]
            )
        if result["quality"]["clauses_requiring_review"]:
            bucket["review_cases"] += 1

    summary = {}
    for category, bucket in sorted(by_category.items()):
        summary[category] = {
            "cases": bucket["cases"],
            "mean_cer": _mean(bucket["cer"]),
            "mean_wer": _mean(bucket["wer"]),
            "mean_word_order_accuracy": _mean(bucket["order"]),
            "mean_risk_recall": _mean(bucket["risk_recall"]),
            "mean_page_confidence": _mean(bucket["confidence"]),
            "mean_source_accuracy": _mean(bucket["source_accuracy"]),
            "cases_requiring_review": bucket["review_cases"],
            "mean_seconds": _mean(bucket["seconds"]),
        }

    return {
        "case_count": len(results),
        "ok_count": len(ok),
        "error_count": len(results) - len(ok),
        "mean_cer": _mean([result["document"]["cer"] for result in ok]),
        "mean_wer": _mean([result["document"]["wer"] for result in ok]),
        "mean_word_order_accuracy": _mean(
            [result["document"]["word_order_accuracy"] for result in ok]
        ),
        "mean_risk_recall": _mean(
            [result["risk"]["recall"] for result in ok]
        ),
        "mean_page_confidence": _mean(
            [
                result["quality"]["mean_page_confidence"]
                for result in ok
                if result["quality"]["mean_page_confidence"] is not None
            ]
        ),
        "mean_source_accuracy": _mean(
            [result["sources"]["accuracy"] for result in ok]
        ),
        "total_seconds": round(
            sum(result.get("total_seconds", 0.0) for result in results), 6
        ),
        "peak_memory_mb": max(
            (result.get("peak_memory_mb", 0.0) for result in results),
            default=0.0,
        ),
        "by_category": summary,
    }


def render_markdown(results: list[dict], environment: dict) -> str:
    aggregate = _aggregate(results)
    lines: list[str] = []
    lines.append("# JurisScan-AI OCR Benchmark")
    lines.append("")
    lines.append(
        "This report records a measured run of the Phase 1-3 OCR pipeline. "
        "Every CER, WER, confidence, timing and memory value below is from the "
        "run recorded in the companion JSON output. It is not a legal-accuracy "
        "claim and it does not use client documents."
    )
    lines.append("")
    lines.append("## Scope and method")
    lines.append("")
    lines.append(
        "- Corpus: synthetic legal clauses generated by `backend/benchmarks/ocr_dataset.py`."
    )
    lines.append(
        "- Documents are rendered to PDFs, then selected pages are rasterised to "
        "image-only scans so extraction must use OCR."
    )
    lines.append(
        "- Ground truth is the exact page text and reading order expected from a "
        "perfect extractor. CER/WER are computed after Unicode, case and "
        "whitespace normalisation; punctuation and word order are preserved."
    )
    lines.append(
        "- `word order` is longest-common-subsequence recall over word tokens. "
        "It exposes reordered columns even when every word was recognised."
    )
    lines.append(
        "- Clause segmentation is measured against the original extracted text: "
        "exact source offsets, expected clause-marker recall and marker order."
    )
    lines.append(
        "- OCR confidence is line-level confidence weighted by line length. It "
        "is not word-level confidence and must not be read as a probability that "
        "a clause is legally correct."
    )
    lines.append(
        "- Peak memory is Python `tracemalloc` peak, not process RSS; native "
        "ONNX and OpenCV allocations are outside that measurement."
    )
    lines.append(
        "- Risk recall is measured against the expected rule codes hand-labelled "
        "for each synthetic case. False positives are recorded in the JSON."
    )
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    lines.append(f"- Measured at: `{environment['measured_at']}`")
    lines.append(
        f"- Python {environment['python']} on {environment['platform']}"
    )
    packages = ", ".join(
        f"{name}={version or 'not importable'}"
        for name, version in environment["packages"].items()
    )
    lines.append(f"- Packages: {packages}")
    lines.append(
        "- Settings: "
        + ", ".join(
            f"`{key}={value}`"
            for key, value in environment["settings"].items()
        )
    )
    lines.append("")
    lines.append("## Corpus")
    lines.append("")
    lines.append("| Case | Category | Pages | Tags |")
    lines.append("|---|---|---:|---|")
    for result in results:
        lines.append(
            f"| `{result['case_id']}` | {result['category']} | "
            f"{len(result.get('pages', []))} | {', '.join(result.get('tags', []))} |"
        )
    lines.append("")
    lines.append("## Measured results")
    lines.append("")
    lines.append(
        "| Case | CER | WER | Word order | Risk recall | OCR confidence | "
        "Review clauses | Source accuracy | Extract s | Peak MB |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        if result.get("status") != "ok":
            lines.append(
                f"| `{result['case_id']}` | ERROR | ERROR | ERROR | ERROR | "
                f"ERROR | ERROR | ERROR | {_fmt(result.get('extract_seconds'))} | "
                f"{_fmt(result.get('peak_memory_mb'))} |"
            )
            continue
        lines.append(
            f"| `{result['case_id']}` | {_fmt(result['document']['cer'])} | "
            f"{_fmt(result['document']['wer'])} | "
            f"{_fmt(result['document']['word_order_accuracy'])} | "
            f"{_fmt(result['risk']['recall'])} | "
            f"{_fmt(result['quality']['mean_page_confidence'])} | "
            f"{result['quality']['clauses_requiring_review']}/"
            f"{result['quality']['clause_count']} | "
            f"{_fmt(result['sources']['accuracy'])} | "
            f"{_fmt(result['extract_seconds'], 2)} | "
            f"{_fmt(result['peak_memory_mb'], 2)} |"
        )
    lines.append("")
    lines.append(
        f"Across {aggregate['ok_count']} successful case(s): mean CER "
        f"{_fmt(aggregate['mean_cer'])}, mean WER {_fmt(aggregate['mean_wer'])}, "
        f"mean word order {_fmt(aggregate['mean_word_order_accuracy'])}, mean risk "
        f"recall {_fmt(aggregate['mean_risk_recall'])}, mean OCR confidence "
        f"{_fmt(aggregate['mean_page_confidence'])}. Total measured extraction "
        f"time {_fmt(aggregate['total_seconds'], 2)} s; largest peak traced memory "
        f"{_fmt(aggregate['peak_memory_mb'], 2)} MB."
    )
    lines.append("")
    lines.append("## Per-category summary")
    lines.append("")
    lines.append(
        "| Category | Cases | Mean CER | Mean WER | Mean word order | "
        "Mean risk recall | Mean confidence | Review cases |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for category, values in aggregate["by_category"].items():
        lines.append(
            f"| {category} | {values['cases']} | {_fmt(values['mean_cer'])} | "
            f"{_fmt(values['mean_wer'])} | "
            f"{_fmt(values['mean_word_order_accuracy'])} | "
            f"{_fmt(values['mean_risk_recall'])} | "
            f"{_fmt(values['mean_page_confidence'])} | "
            f"{values['cases_requiring_review']} |"
        )
    lines.append("")
    lines.append("## Layout, segmentation and offsets")
    lines.append("")
    lines.append(
        "| Case | Marker order | Marker recall | Exact source offsets | "
        "Overlapping segments | Page-marker accuracy |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    for result in results:
        if result.get("status") != "ok":
            continue
        lines.append(
            f"| `{result['case_id']}` | "
            f"{'yes' if result['segmentation']['marker_order_ok'] else 'no'} | "
            f"{_fmt(result['segmentation']['marker_recall'])} | "
            f"{'yes' if result['segmentation']['exact_source_offsets'] else 'no'} | "
            f"{result['segmentation']['overlapping_segments']} | "
            f"{_fmt(result['page_offsets']['page_marker_accuracy'])} |"
        )
    lines.append("")
    lines.append("## Quality, review and low-quality risk analysis")
    lines.append("")
    lines.append(
        "| Case | OCR pages | Document confidence | Low-confidence ratio | "
        "Review clauses | Review findings | Warnings |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for result in results:
        if result.get("status") != "ok":
            continue
        warnings = result["quality"]["warnings"]
        lines.append(
            f"| `{result['case_id']}` | {len(result['sources']['ocr_pages'])} | "
            f"{_fmt(result['quality']['document_confidence'])} | "
            f"{_fmt(result['quality']['document_low_confidence_ratio'])} | "
            f"{result['quality']['clauses_requiring_review']} | "
            f"{result['quality']['review_findings']} | "
            f"{'; '.join(warnings) if warnings else 'none'} |"
        )
    lines.append("")
    lines.append("## Native/OCR merge and recovery")
    lines.append("")
    for result in results:
        if result.get("status") != "ok":
            continue
        expected = ", ".join(result["sources"]["expected"])
        actual = ", ".join(result["sources"]["actual"])
        lines.append(
            f"- `{result['case_id']}`: expected page sources [{expected}], "
            f"measured [{actual}], accuracy {_fmt(result['sources']['accuracy'])}."
        )
    lines.append(
        "- Recovery behaviour is covered by the deterministic tests for OCR "
        "timeouts, executor retirement, bounded batching and retry, not by "
        "forcing an artificial failure into this accuracy corpus."
    )
    lines.append("")
    lines.append("## Evidence-based weaknesses and recommendations")
    lines.append("")
    worst_cer = max(
        (result for result in results if result.get("status") == "ok"),
        key=lambda result: result["document"]["cer"],
        default=None,
    )
    worst_order = min(
        (result for result in results if result.get("status") == "ok"),
        key=lambda result: result["document"]["word_order_accuracy"],
        default=None,
    )
    if worst_cer is not None:
        lines.append(
            f"- Highest character error rate: `{worst_cer['case_id']}` at "
            f"{_fmt(worst_cer['document']['cer'])} CER and "
            f"{_fmt(worst_cer['document']['wer'])} WER. Inspect its page rows in "
            "the JSON result before changing thresholds."
        )
    if worst_order is not None:
        lines.append(
            f"- Lowest reading-order score: `{worst_order['case_id']}` at "
            f"{_fmt(worst_order['document']['word_order_accuracy'])}. Inspect its "
            "page rows: both reordered text and character substitutions can "
            "reduce this score."
        )
    marker_failures = [
        result["case_id"]
        for result in results
        if result.get("status") == "ok"
        and not result["segmentation"]["marker_order_ok"]
    ]
    if marker_failures:
        lines.append(
            "- Clause-marker order failed for: "
            + ", ".join(f"`{case}`" for case in marker_failures)
            + ". Treat these as reading-order regressions first, not as segmentation failures."
        )
    source_failures = [
        result["case_id"]
        for result in results
        if result.get("status") == "ok"
        and result["sources"]["accuracy"] < 1.0
    ]
    if source_failures:
        lines.append(
            "- Native/OCR source selection differed from the expected source on: "
            + ", ".join(f"`{case}`" for case in source_failures)
            + ". Verify that native text was not discarded or damaged text was not kept."
        )
    review_cases = [
        result["case_id"]
        for result in results
        if result.get("status") == "ok"
        and result["quality"]["clauses_requiring_review"]
    ]
    if review_cases:
        lines.append(
            "- Review flags were raised on: "
            + ", ".join(f"`{case}`" for case in review_cases)
            + ". This is desirable only when the confidence actually correlates with the measured error."
        )
    else:
        lines.append(
            "- No case raised a clause-level review flag. If a low-quality scan "
            "still scores below the warning threshold, inspect calibration before "
            "trusting the flag as a safety net."
        )
    lines.append(
        "- Recommendation: keep OCR confidence as a review signal, never as a "
        "legal-correctness score. Re-run this benchmark after changing "
        "preprocessing, layout ordering or merge thresholds."
    )
    lines.append(
        "- Recommendation: expand the corpus with real, consented, redacted scans "
        "before making production accuracy claims; this synthetic corpus is a "
        "regression harness, not a representative sample."
    )
    lines.append("")
    lines.append("## Reproduction")
    lines.append("")
    lines.append("```powershell")
    lines.append("cd backend")
    lines.append(".venv\\Scripts\\python.exe -m benchmarks.run_ocr_benchmark")
    lines.append("```")
    lines.append("")
    lines.append("The runner writes the machine-readable result JSON alongside the report.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(
            Path(__file__).resolve().parents[2] / "docs" / "OCR_BENCHMARK.md"
        ),
    )
    parser.add_argument(
        "--json-output",
        default=str(
            Path(__file__).resolve().parents[2]
            / "data"
            / "ocr_benchmark_results.json"
        ),
    )
    parser.add_argument(
        "--manifest-output",
        default=str(
            Path(__file__).resolve().parents[2]
            / "data"
            / "ocr_benchmark_manifest.json"
        ),
    )
    parser.add_argument("--dpi", type=int, default=ocr_dataset.DEFAULT_DPI)
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help="Run only the named case (repeatable).",
    )
    args = parser.parse_args(argv)

    if args.dpi != ocr_dataset.DEFAULT_DPI:
        ocr_dataset.DEFAULT_DPI = args.dpi

    selected = [
        case
        for case in benchmark_cases()
        if not args.cases or case.case_id in set(args.cases)
    ]
    if not selected:
        parser.error("No benchmark cases matched the requested --case values.")

    environment = _environment(args.dpi)
    results = [run_case(case, dpi=args.dpi) for case in selected]
    payload = {
        "version": ocr_dataset.BENCHMARK_VERSION,
        "disclaimer": ocr_dataset.DISCLAIMER,
        "environment": environment,
        "aggregate": _aggregate(results),
        "cases": results,
    }

    output = Path(args.output)
    json_output = Path(args.json_output)
    manifest_output = Path(args.manifest_output)
    for path in (output, json_output, manifest_output):
        path.parent.mkdir(parents=True, exist_ok=True)

    json_output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest_output.write_text(
        json.dumps(manifest(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    output.write_text(render_markdown(results, environment), encoding="utf-8")

    print(
        f"Wrote {output}\nWrote {json_output}\nWrote {manifest_output}\n"
        f"{len(results)} case(s), {payload['aggregate']['error_count']} error(s)."
    )
    return 0 if payload["aggregate"]["error_count"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
