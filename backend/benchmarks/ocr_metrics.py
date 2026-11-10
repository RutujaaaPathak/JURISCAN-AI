"""Measurement primitives for the OCR benchmark.

These functions are intentionally independent of the OCR engine so their
behaviour can be tested with known inputs. They report distances, not pass/fail
thresholds: the benchmark report records the measured values and any threshold
used by a regression test is stated explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from app.services.extraction import ExtractedDocument, page_number_for_offset
from app.services.segmentation import Segment

_WHITESPACE = re.compile(r"\s+")
_DASHES = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
}
_QUOTES = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
}


def canonical_text(text: str) -> str:
    """Normalise OCR and ground truth before character/word comparison.

    Case, Unicode compatibility forms, dash/quote variants and whitespace are
    normalised. Punctuation and word order are preserved so CER/WER still expose
    recognition and reading-order mistakes.
    """

    value = unicodedata.normalize("NFKC", text or "")
    replacements = {
        ord(character): replacement
        for character, replacement in {**_DASHES, **_QUOTES}.items()
    }
    value = value.translate(replacements)
    value = value.casefold()
    return _WHITESPACE.sub(" ", value).strip()


def _tokens(text: str) -> list[str]:
    return canonical_text(text).split()


def levenshtein(reference: str, hypothesis: str) -> int:
    """Character-level edit distance with O(min(n, m)) memory."""

    if reference == hypothesis:
        return 0
    if not reference:
        return len(hypothesis)
    if not hypothesis:
        return len(reference)
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for row, ref_char in enumerate(reference, start=1):
        current = [row]
        for column, hyp_char in enumerate(hypothesis, start=1):
            insert = current[column - 1] + 1
            delete = previous[column] + 1
            substitute = previous[column - 1] + (ref_char != hyp_char)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


def word_edit_distance(reference: str, hypothesis: str) -> int:
    return levenshtein_tokens(_tokens(reference), _tokens(hypothesis))


def levenshtein_tokens(reference: list[str], hypothesis: list[str]) -> int:
    if reference == hypothesis:
        return 0
    if not reference:
        return len(hypothesis)
    if not hypothesis:
        return len(reference)
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for row, ref_token in enumerate(reference, start=1):
        current = [row]
        for column, hyp_token in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (ref_token != hyp_token),
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    ref = canonical_text(reference)
    hyp = canonical_text(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return round(levenshtein(ref, hyp) / len(ref), 6)


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref = _tokens(reference)
    hyp = _tokens(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return round(levenshtein_tokens(ref, hyp) / len(ref), 6)


def _lcs_length(left: list[str], right: list[str]) -> int:
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for column, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current.append(previous[column - 1] + 1)
            else:
                current.append(max(previous[column], current[column - 1]))
        previous = current
    return previous[-1]


def word_order_accuracy(reference: str, hypothesis: str) -> float:
    """Longest-common-subsequence recall over canonical word tokens."""

    ref = _tokens(reference)
    if not ref:
        return 1.0
    return round(_lcs_length(ref, _tokens(hypothesis)) / len(ref), 6)


def marker_positions(text: str, markers: tuple[str, ...]) -> list[int | None]:
    canonical = canonical_text(text)
    positions: list[int | None] = []
    for marker in markers:
        needle = canonical_text(marker)
        index = canonical.find(needle)
        positions.append(None if index < 0 else index)
    return positions


def marker_order_ok(text: str, markers: tuple[str, ...]) -> bool:
    positions = marker_positions(text, markers)
    found = [position for position in positions if position is not None]
    return len(found) == len(markers) and found == sorted(found)


def segmentation_metrics(
    text: str,
    segments: list[Segment],
    expected_markers: tuple[str, ...],
) -> dict:
    exact_offsets = all(
        text[segment.start_offset : segment.end_offset] == segment.text
        for segment in segments
    )
    overlaps = sum(
        1
        for index in range(1, len(segments))
        if segments[index].start_offset < segments[index - 1].end_offset
    )
    found = [
        marker
        for marker in expected_markers
        if any(marker.casefold() in segment.text.casefold() for segment in segments)
    ]
    positions = marker_positions(text, expected_markers)
    return {
        "segment_count": len(segments),
        "expected_marker_count": len(expected_markers),
        "found_marker_count": len(found),
        "marker_recall": (
            round(len(found) / len(expected_markers), 6)
            if expected_markers
            else 1.0
        ),
        "marker_order_ok": marker_order_ok(text, expected_markers),
        "missing_markers": [
            marker for marker in expected_markers if marker not in found
        ],
        "exact_source_offsets": exact_offsets,
        "overlapping_segments": overlaps,
        "marker_positions": positions,
    }


def page_offset_metrics(
    extracted: ExtractedDocument,
    page_markers: tuple[tuple[int, str], ...],
) -> dict:
    """Check page spans are ordered/contiguous and markers map to their page."""

    spans = extracted.pages
    ordered = [span.page_number for span in spans] == list(
        range(1, len(spans) + 1)
    )
    contiguous = all(
        spans[index].start_offset >= spans[index - 1].end_offset
        and spans[index].start_offset - spans[index - 1].end_offset <= 2
        for index in range(1, len(spans))
    )
    marker_hits: list[dict] = []
    for expected_page, marker in page_markers:
        offset = extracted.text.casefold().find(marker.casefold())
        actual_page = (
            page_number_for_offset(spans, offset) if offset >= 0 else None
        )
        marker_hits.append(
            {
                "marker": marker,
                "expected_page": expected_page,
                "offset": offset if offset >= 0 else None,
                "actual_page": actual_page,
                "ok": offset >= 0 and actual_page == expected_page,
            }
        )
    return {
        "page_count": len(spans),
        "ordered_page_numbers": ordered,
        "contiguous_spans": contiguous,
        "marker_hits": marker_hits,
        "page_marker_accuracy": (
            round(
                sum(1 for hit in marker_hits if hit["ok"]) / len(marker_hits),
                6,
            )
            if marker_hits
            else 1.0
        ),
    }


@dataclass(slots=True)
class PageMeasurement:
    page_number: int
    source: str
    expected_source: str
    cer: float
    wer: float
    word_order_accuracy: float
    confidence: float | None
    expected_text: str
    actual_text: str


def measure_pages(
    extracted: ExtractedDocument,
    expected_pages: tuple[str, ...],
    expected_sources: tuple[str, ...],
) -> list[PageMeasurement]:
    measurements: list[PageMeasurement] = []
    for index, expected in enumerate(expected_pages):
        span = (
            extracted.pages[index]
            if index < len(extracted.pages)
            else None
        )
        actual = (
            extracted.text[span.start_offset : span.end_offset]
            if span is not None
            else ""
        )
        measurements.append(
            PageMeasurement(
                page_number=index + 1,
                source=span.source if span is not None else "missing",
                expected_source=(
                    expected_sources[index]
                    if index < len(expected_sources)
                    else "unknown"
                ),
                cer=character_error_rate(expected, actual),
                wer=word_error_rate(expected, actual),
                word_order_accuracy=word_order_accuracy(expected, actual),
                confidence=span.ocr_confidence if span is not None else None,
                expected_text=expected,
                actual_text=actual,
            )
        )
    return measurements


def risk_metrics(
    detected_codes: set[str], expected_codes: tuple[str, ...]
) -> dict:
    expected = set(expected_codes)
    found = expected & detected_codes
    return {
        "expected_codes": sorted(expected),
        "detected_codes": sorted(detected_codes),
        "true_positive_codes": sorted(found),
        "false_negative_codes": sorted(expected - detected_codes),
        "false_positive_codes": sorted(detected_codes - expected),
        "recall": (
            round(len(found) / len(expected), 6) if expected else 1.0
        ),
    }


__all__ = [
    "PageMeasurement",
    "canonical_text",
    "character_error_rate",
    "levenshtein",
    "levenshtein_tokens",
    "marker_order_ok",
    "marker_positions",
    "measure_pages",
    "page_offset_metrics",
    "risk_metrics",
    "segmentation_metrics",
    "word_edit_distance",
    "word_error_rate",
    "word_order_accuracy",
]
