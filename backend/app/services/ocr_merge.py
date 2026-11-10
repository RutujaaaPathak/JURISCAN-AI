"""Quality-aware native/OCR text selection and document-level OCR metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.config import settings
from app.services.ocr_layout import LowConfidenceLine, PageQuality


@dataclass(slots=True, frozen=True)
class TextSelection:
    text: str
    source: str
    native_quality: float
    ocr_quality: float


@dataclass(slots=True, frozen=True)
class DocumentQuality:
    confidence: float | None
    min_confidence: float | None
    low_confidence_ratio: float
    low_confidence_lines: tuple[LowConfidenceLine, ...]
    line_count: int
    word_count: int
    pages: dict[int, PageQuality] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def native_text_quality(text: str) -> float:
    """Heuristic quality score for text already embedded in a PDF.

    Native PDF text is normally preferable, but broken encodings can produce
    ``(cid:123)`` placeholders, replacement characters or long unbroken runs.
    The score rewards readable letters, plausible words and normal whitespace,
    and penalises the common failure modes.
    """

    cleaned = (text or "").replace("\r", " ").replace("\n", " ").strip()
    if not cleaned:
        return 0.0

    length = len(cleaned)
    alnum = sum(character.isalnum() for character in cleaned)
    printable = sum(character.isprintable() for character in cleaned)
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-/.]*", cleaned)
    plausible_tokens = sum(len(token) >= 2 for token in tokens)
    token_ratio = plausible_tokens / max(1, len(tokens))

    alnum_ratio = alnum / length
    printable_ratio = printable / length
    space_ratio = cleaned.count(" ") / length

    score = (
        0.35 * alnum_ratio
        + 0.25 * token_ratio
        + 0.25 * printable_ratio
        + 0.15 * min(1.0, space_ratio * 8.0)
    )

    if "(cid:" in cleaned.lower():
        score -= 0.45
    if "\ufffd" in cleaned:
        score -= 0.25
    control_ratio = sum(
        ord(character) < 32 and character not in "\n\r\t"
        for character in cleaned
    ) / length
    score -= control_ratio * 2.0
    if length >= 80 and space_ratio < 0.03:
        score -= 0.20
    if re.search(r"(.)\1{6,}", cleaned):
        score -= 0.10

    # Short headings are legitimate; only apply a length penalty below 20 chars.
    length_factor = min(1.0, length / 20.0)
    return round(max(0.0, min(1.0, score * length_factor)), 4)


def select_page_text(
    native: str,
    ocr_text: str,
    ocr_confidence: float | None,
    *,
    margin: float | None = None,
) -> TextSelection:
    """Choose the better of native and OCR text for one page.

    Native text wins when it is already good, even if OCR produced a longer
    string. OCR wins when the native text is clearly damaged and OCR confidence
    is materially better. Ties preserve native text.
    """

    native_clean = (native or "").strip()
    ocr_clean = (ocr_text or "").strip()
    native_score = native_text_quality(native_clean)
    ocr_score = (
        max(0.0, min(1.0, ocr_confidence))
        if ocr_confidence is not None
        else native_text_quality(ocr_clean)
    )
    effective_margin = settings.ocr_merge_margin if margin is None else margin

    if not native_clean:
        return TextSelection(
            text=ocr_clean,
            source="ocr" if ocr_clean else "empty",
            native_quality=native_score,
            ocr_quality=ocr_score,
        )
    if not ocr_clean:
        return TextSelection(
            text=native_clean,
            source="native",
            native_quality=native_score,
            ocr_quality=ocr_score,
        )

    if native_score >= 0.72 and ocr_score <= native_score + effective_margin:
        return TextSelection(
            text=native_clean,
            source="native",
            native_quality=native_score,
            ocr_quality=ocr_score,
        )

    if ocr_score >= 0.55 and ocr_score >= native_score + effective_margin:
        return TextSelection(
            text=ocr_clean,
            source="ocr",
            native_quality=native_score,
            ocr_quality=ocr_score,
        )

    if (
        native_score < settings.ocr_native_recheck_threshold
        and ocr_score >= native_score - 0.05
    ):
        return TextSelection(
            text=ocr_clean,
            source="ocr",
            native_quality=native_score,
            ocr_quality=ocr_score,
        )

    if len(ocr_clean) >= len(native_clean) * 1.25 and ocr_score >= max(
        0.5, native_score - 0.05
    ):
        return TextSelection(
            text=ocr_clean,
            source="ocr",
            native_quality=native_score,
            ocr_quality=ocr_score,
        )

    return TextSelection(
        text=native_clean,
        source="native",
        native_quality=native_score,
        ocr_quality=ocr_score,
    )


def aggregate_quality(
    pages: dict[int, PageQuality],
    *,
    warning_threshold: float | None = None,
) -> DocumentQuality | None:
    """Combine page-level OCR confidence into a document-level warning set."""

    usable = {
        number: quality
        for number, quality in pages.items()
        if quality.line_count > 0 and quality.confidence is not None
    }
    if not usable:
        return None

    warning = (
        settings.ocr_quality_warning_threshold
        if warning_threshold is None
        else warning_threshold
    )
    total_lines = sum(quality.line_count for quality in usable.values())
    confidence = sum(
        (quality.confidence or 0.0) * quality.line_count
        for quality in usable.values()
    ) / max(1, total_lines)
    low_count = sum(
        len(quality.low_confidence_lines) for quality in usable.values()
    )
    low_ratio = low_count / max(1, total_lines)
    min_confidence = min(
        quality.min_confidence
        for quality in usable.values()
        if quality.min_confidence is not None
    )
    low_lines = tuple(
        line
        for number in sorted(usable)
        for line in usable[number].low_confidence_lines
    )

    warnings: list[str] = []
    if confidence < warning:
        warnings.append(
            f"Document OCR confidence {confidence:.2f} is below the warning "
            f"threshold {warning:.2f}; risk analysis may be unreliable."
        )
    if low_ratio > 0.15:
        warnings.append(
            f"{low_count} of {total_lines} OCR text lines are low-confidence."
        )
    weak_pages = [
        number
        for number, quality in sorted(usable.items())
        if quality.confidence is not None and quality.confidence < warning
    ]
    if weak_pages:
        pages_text = ", ".join(str(number) for number in weak_pages[:10])
        suffix = "..." if len(weak_pages) > 10 else ""
        warnings.append(
            f"Low OCR confidence on page(s) {pages_text}{suffix}."
        )

    return DocumentQuality(
        confidence=round(confidence, 4),
        min_confidence=round(min_confidence, 4),
        low_confidence_ratio=round(low_ratio, 4),
        low_confidence_lines=low_lines,
        line_count=total_lines,
        word_count=sum(quality.word_count for quality in usable.values()),
        pages=usable,
        warnings=tuple(warnings),
    )


__all__ = [
    "DocumentQuality",
    "TextSelection",
    "aggregate_quality",
    "native_text_quality",
    "select_page_text",
]
