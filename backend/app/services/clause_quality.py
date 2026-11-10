"""Clause-level OCR quality assessment and manual-review flags.

OCR confidence is measured per recognised line. This module maps those lines
back onto clause offsets, so a finding is only marked unreliable when the text
that triggered it came from a weak OCR region (not merely because another page
in the document was noisy).
"""

from __future__ import annotations

from app.config import settings
from app.services.extraction import PageSpan
from app.services.ocr_layout import OcrLineSpan
from app.services.segmentation import Segment


def _page_for_offset(pages: list[PageSpan], offset: int) -> PageSpan | None:
    for page in pages:
        if page.start_offset <= offset < page.end_offset:
            return page
    if pages and offset >= pages[-1].end_offset:
        return pages[-1]
    return pages[0] if pages else None


def _native_quality(page: PageSpan | None) -> dict:
    return {
        "source": "native",
        "page_number": page.page_number if page else None,
        "confidence": None,
        "min_confidence": None,
        "low_confidence_ratio": 0.0,
        "low_confidence_lines": [],
        "warnings": [],
        "requires_verification": False,
    }


def assess_clause_quality(
    segments: list[Segment],
    pages: list[PageSpan],
    line_spans: list[OcrLineSpan],
) -> list[dict]:
    """Return a persisted-quality payload for every clause segment."""

    low_threshold = settings.ocr_low_confidence_threshold
    warning_threshold = settings.ocr_quality_warning_threshold
    qualities: list[dict] = []

    for segment in segments:
        page = _page_for_offset(pages, segment.start_offset)
        if page is None or page.source != "ocr":
            qualities.append(_native_quality(page))
            continue

        overlapping = [
            span
            for span in line_spans
            if span.end_offset > segment.start_offset
            and span.start_offset < segment.end_offset
        ]
        if overlapping:
            weights = [
                max(
                    1,
                    min(span.end_offset, segment.end_offset)
                    - max(span.start_offset, segment.start_offset),
                )
                for span in overlapping
            ]
            total_weight = sum(weights)
            confidence = sum(
                span.confidence * weight
                for span, weight in zip(overlapping, weights)
            ) / total_weight
            low_lines = [
                span for span in overlapping if span.confidence < low_threshold
            ]
            low_ratio = len(low_lines) / len(overlapping)
            min_confidence = min(span.confidence for span in overlapping)
        else:
            confidence = page.ocr_confidence
            low_lines = []
            low_ratio = 0.0
            min_confidence = page.ocr_confidence

        warnings: list[str] = []
        if confidence is None:
            warnings.append(
                "OCR confidence is unavailable for this clause; verify the wording manually."
            )
        elif confidence < warning_threshold:
            warnings.append(
                f"Clause OCR confidence {confidence:.2f} is below the verification "
                f"threshold {warning_threshold:.2f}."
            )
        if low_ratio > 0.20:
            warnings.append(
                f"{len(low_lines)} of {len(overlapping)} OCR lines in this clause "
                "are low-confidence."
            )

        requires_verification = (
            confidence is None
            or confidence < warning_threshold
            or low_ratio > 0.20
        )
        qualities.append(
            {
                "source": "ocr",
                "page_number": page.page_number,
                "confidence": round(confidence, 4) if confidence is not None else None,
                "min_confidence": (
                    round(min_confidence, 4) if min_confidence is not None else None
                ),
                "low_confidence_ratio": round(low_ratio, 4),
                "low_confidence_lines": [
                    {
                        "text": span.text,
                        "confidence": round(span.confidence, 4),
                        "start_offset": span.start_offset,
                        "end_offset": span.end_offset,
                        "bbox": list(span.bbox) if span.bbox else None,
                    }
                    for span in low_lines
                ],
                "warnings": warnings,
                "requires_verification": requires_verification,
            }
        )

    return qualities


def quality_requires_review(quality: dict | None) -> bool:
    return bool(quality and quality.get("requires_verification"))


__all__ = ["assess_clause_quality", "quality_requires_review"]
