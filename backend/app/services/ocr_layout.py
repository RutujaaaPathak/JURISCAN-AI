"""Layout ordering, confidence metrics and text reconstruction for OCR pages.

RapidOCR returns detected lines in a rough top-to-bottom order. Legal documents
often use two or more columns, with headers, footers and tables. This module
orders those lines by visual region, preserves table rows and reconstructs
paragraphs without flattening clause boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
import statistics

from app.config import settings

_CLAUSE_START = re.compile(
    r"^(?:"
    r"(?:clause|article|section|schedule|appendix|annex|part|paragraph|recital)\s+"
    r"(?:\d+|[ivxlcdm]+|[a-z]+)"
    r"|"
    r"\d{1,3}(?:\.\d{1,4}){0,5}[.):]?"
    r"|"
    r"\((?:\d+|[ivxlcdm]+|[a-z]+)\)"
    r"|"
    r"[A-Za-z][.)]"
    r"|"
    r"[-\u2022\u25e6\u25aa\u2023]"
    r")\s+",
    re.IGNORECASE,
)
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?%])")
_SPACE_AFTER_OPEN = re.compile(r"([(\[])\s+")
_MULTISPACE = re.compile(r"[ \t]+")
_HYPHEN_BREAK = re.compile(r"[-\u2010\u2011]$")


@dataclass(slots=True, frozen=True)
class OcrLine:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float] | None = None
    role: str = "body"
    column: int = 0
    row: int = 0
    table_row: bool = False


@dataclass(slots=True, frozen=True)
class OcrLineSpan:
    """A normalised OCR line mapped to offsets in reconstructed page text."""

    text: str
    confidence: float
    start_offset: int
    end_offset: int
    bbox: tuple[float, float, float, float] | None = None


@dataclass(slots=True, frozen=True)
class LowConfidenceLine:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float] | None = None


@dataclass(slots=True, frozen=True)
class PageQuality:
    confidence: float | None
    min_confidence: float | None
    low_confidence_ratio: float
    low_confidence_lines: tuple[LowConfidenceLine, ...]
    line_count: int
    word_count: int
    warnings: tuple[str, ...]


def _bbox_from_box(box) -> tuple[float, float, float, float] | None:
    if box is None:
        return None
    try:
        points = list(box)
        if len(points) < 4:
            return None
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return (min(xs), min(ys), max(xs), max(ys))
    except Exception:
        return None


def parse_rapidocr_result(result) -> list[OcrLine]:
    """Convert RapidOCR's ``[box, text, score]`` entries into ordered lines."""

    lines: list[OcrLine] = []
    for entry in result or []:
        if not entry or len(entry) < 2:
            continue
        text = str(entry[1] or "").strip()
        if not text:
            continue
        try:
            confidence = float(entry[2]) if len(entry) >= 3 else 1.0
        except (TypeError, ValueError):
            confidence = 1.0
        lines.append(
            OcrLine(
                text=text,
                confidence=max(0.0, min(1.0, confidence)),
                bbox=_bbox_from_box(entry[0]),
            )
        )
    return lines


def _merge_intervals(
    intervals: list[tuple[float, float]], tolerance: float
) -> list[tuple[float, float]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1] + tolerance:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _split_columns(
    lines: list[OcrLine], content_width: float
) -> list[list[OcrLine]]:
    """Recursively split lines on clear vertical gutters."""

    if len(lines) < 4 or content_width <= 0:
        return [lines]

    intervals = [
        (line.bbox[0], line.bbox[2])
        for line in lines
        if line.bbox is not None
    ]
    merged = _merge_intervals(intervals, content_width * 0.025)
    if len(merged) < 2:
        return [lines]

    gaps = [
        (
            merged[index + 1][0] - merged[index][1],
            (merged[index][1] + merged[index + 1][0]) / 2.0,
        )
        for index in range(len(merged) - 1)
    ]
    gap, split = max(gaps)
    if gap < content_width * 0.08:
        return [lines]

    left = [line for line in lines if line.bbox and line.bbox[2] <= split]
    right = [line for line in lines if line.bbox and line.bbox[0] >= split]
    crossing = [line for line in lines if line not in left and line not in right]
    if len(left) < 2 or len(right) < 2:
        return [lines]

    groups: list[list[OcrLine]] = []
    groups.extend(_split_columns(left, content_width))
    groups.extend(_split_columns(right, content_width))
    if crossing:
        groups.append(crossing)
    groups.sort(key=lambda group: min(line.bbox[0] for line in group if line.bbox))
    return groups


def _assign_rows(lines: list[OcrLine], median_height: float) -> list[OcrLine]:
    ordered = sorted(
        lines,
        key=lambda line: (
            line.bbox[1] if line.bbox else 0.0,
            line.bbox[0] if line.bbox else 0.0,
        ),
    )
    row = -1
    row_top: float | None = None
    tolerance = max(3.0, median_height * 0.55)
    assigned: list[OcrLine] = []
    for line in ordered:
        center_y = (
            (line.bbox[1] + line.bbox[3]) / 2.0 if line.bbox else 0.0
        )
        if row_top is None or abs(center_y - row_top) > tolerance:
            row += 1
            row_top = center_y
        assigned.append(replace(line, row=row))
    # Cells on the same visual row must be read left-to-right even when OCR
    # reports a few pixels of vertical jitter between them.
    assigned.sort(
        key=lambda line: (
            line.row,
            line.bbox[0] if line.bbox else 0.0,
        )
    )
    return assigned


def _detect_table_row_ids(
    lines: list[OcrLine],
    content_width: float,
    median_height: float,
) -> set[int]:
    """Identify short, widely-separated cells that form a table row."""

    by_row: dict[int, list[OcrLine]] = {}
    for line in lines:
        by_row.setdefault(line.row, []).append(line)

    table_ids: set[int] = set()
    for row_lines in by_row.values():
        if len(row_lines) < 2:
            continue
        ordered = sorted(
            row_lines,
            key=lambda line: line.bbox[0] if line.bbox else 0.0,
        )
        widths = [
            line.bbox[2] - line.bbox[0] for line in ordered if line.bbox
        ]
        gaps = [
            ordered[index + 1].bbox[0] - ordered[index].bbox[2]
            for index in range(len(ordered) - 1)
            if ordered[index].bbox and ordered[index + 1].bbox
        ]
        if not widths or not gaps:
            continue
        if max(gaps) < max(12.0, median_height * 1.5):
            continue
        # Table cells are short. Long lines separated by a gutter are a
        # two-column layout, not a table, and must stay in column order.
        if statistics.median(widths) >= content_width * 0.18:
            continue
        if sum(widths) >= content_width * 0.90:
            continue
        table_ids.update(id(line) for line in ordered)
    return table_ids


def _mark_table_rows(lines: list[OcrLine], median_height: float) -> list[OcrLine]:
    by_row: dict[int, list[OcrLine]] = {}
    for line in lines:
        by_row.setdefault(line.row, []).append(line)

    table_rows: set[int] = set()
    for row, row_lines in by_row.items():
        if len(row_lines) < 2:
            continue
        ordered = sorted(
            row_lines,
            key=lambda line: line.bbox[0] if line.bbox else 0.0,
        )
        gaps = [
            ordered[index + 1].bbox[0] - ordered[index].bbox[2]
            for index in range(len(ordered) - 1)
            if ordered[index].bbox and ordered[index + 1].bbox
        ]
        if gaps and max(gaps) > max(8.0, median_height * 1.2):
            table_rows.add(row)

    return [
        replace(line, table_row=line.row in table_rows)
        for line in lines
    ]


def layout_lines(
    lines: list[OcrLine],
    width: int,
    height: int,
) -> list[OcrLine]:
    """Order OCR lines for reading, including columns, headers and footers."""

    if not lines:
        return []

    lines = [
        replace(line, confidence=max(0.0, min(1.0, line.confidence)))
        for line in lines
    ]

    if not settings.ocr_layout_analysis_enabled or not any(
        line.bbox is not None for line in lines
    ):
        return [
            replace(line, role="body", column=0, row=index)
            for index, line in enumerate(lines)
        ]

    valid = [line for line in lines if line.bbox is not None]
    page_height = float(height) if height > 0 else max(line.bbox[3] for line in valid)
    page_width = float(width) if width > 0 else max(line.bbox[2] for line in valid)

    header_cut = page_height * 0.06
    footer_cut = page_height * 0.94
    headers = [
        line
        for line in valid
        if (line.bbox[1] + line.bbox[3]) / 2.0 < header_cut
    ]
    footers = [
        line
        for line in valid
        if (line.bbox[1] + line.bbox[3]) / 2.0 > footer_cut
    ]
    header_ids = {id(line) for line in headers}
    footer_ids = {id(line) for line in footers}
    body = [
        line
        for line in valid
        if id(line) not in header_ids and id(line) not in footer_ids
    ]

    heights = [line.bbox[3] - line.bbox[1] for line in body if line.bbox]
    median_height = statistics.median(heights) if heights else 10.0

    content_left = min(line.bbox[0] for line in body) if body else 0.0
    content_right = max(line.bbox[2] for line in body) if body else page_width
    content_width = max(1.0, content_right - content_left)
    center = (content_left + content_right) / 2.0

    row_ordered = _assign_rows(body, median_height)
    table_ids = _detect_table_row_ids(
        row_ordered, content_width, median_height
    )
    body = []
    table_line_ids: set[int] = set()
    for line in row_ordered:
        if id(line) in table_ids:
            table_line = replace(line, table_row=True)
            body.append(table_line)
            table_line_ids.add(id(table_line))
        else:
            body.append(line)

    full_width = [
        line
        for line in body
        if (line.bbox[2] - line.bbox[0]) >= content_width * 0.65
        and line.bbox[0] < center < line.bbox[2]
    ]
    full_width_ids = {id(line) for line in full_width} | table_line_ids

    regions: list[list[OcrLine]] = []
    current: list[OcrLine] = []
    for line in body:
        if id(line) in full_width_ids:
            if current:
                regions.append(current)
                current = []
            regions.append([line])
        else:
            current.append(line)
    if current:
        regions.append(current)

    ordered_body: list[OcrLine] = []
    for region in regions:
        if len(region) == 1:
            line = region[0]
            ordered_body.append(
                replace(
                    line,
                    column=0,
                    row=line.row if line.table_row else 0,
                )
            )
            continue
        groups = _split_columns(region, content_width)
        for column, group in enumerate(groups):
            group = _assign_rows(group, median_height)
            group = _mark_table_rows(group, median_height)
            ordered_body.extend(replace(line, column=column) for line in group)

    headers = sorted(headers, key=lambda line: (line.bbox[1], line.bbox[0]))
    footers = sorted(footers, key=lambda line: (line.bbox[1], line.bbox[0]))
    headers = [
        replace(line, role="header", column=0, row=index)
        for index, line in enumerate(headers)
    ]
    footers = [
        replace(line, role="footer", column=0, row=index)
        for index, line in enumerate(footers)
    ]
    ordered_body = [replace(line, role="body") for line in ordered_body]
    return headers + ordered_body + footers


def normalise_line(text: str) -> str:
    text = _MULTISPACE.sub(" ", text.replace("\r", " ").replace("\n", " ")).strip()
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _SPACE_AFTER_OPEN.sub(r"\1", text)
    return text


def _line_height(line: OcrLine) -> float:
    return line.bbox[3] - line.bbox[1] if line.bbox else 0.0


def _is_clause_start(text: str) -> bool:
    return bool(_CLAUSE_START.match(text.strip()))


def _new_block(
    previous: OcrLine,
    current: OcrLine,
    median_height: float,
) -> bool:
    if previous.role != current.role:
        return True
    if previous.column != current.column:
        return True
    if previous.table_row != current.table_row:
        return True
    if previous.table_row and previous.row != current.row:
        return True
    if current.row == previous.row and current.table_row:
        return False
    if _is_clause_start(current.text):
        return True
    previous_bottom = previous.bbox[3] if previous.bbox else 0.0
    current_top = current.bbox[1] if current.bbox else previous_bottom
    gap = current_top - previous_bottom
    if median_height > 0 and gap > median_height * 1.5:
        return True
    if previous.text.rstrip().endswith((".", "!", "?", ":")) and current.text[:1].isupper():
        return gap > median_height * 0.25
    return False


def _join_text(previous: str, current: str) -> str:
    if _HYPHEN_BREAK.search(previous) and current[:1].islower():
        return previous[:-1] + current
    return f"{previous} {current}"


def reconstruct_page_text_with_spans(
    lines: list[OcrLine],
) -> tuple[str, tuple[OcrLineSpan, ...]]:
    """Rebuild page text and map each OCR line back to its character offsets."""

    if not lines:
        return "", ()

    valid_heights = [_line_height(line) for line in lines if line.bbox]
    median_height = statistics.median(valid_heights) if valid_heights else 0.0
    blocks: list[str] = []
    block_spans: list[list[OcrLineSpan]] = []
    previous: OcrLine | None = None

    def add_block(text: str, line: OcrLine) -> None:
        blocks.append(text)
        block_spans.append(
            [OcrLineSpan(text, line.confidence, 0, len(text), line.bbox)]
        )

    def add_span(line: OcrLine, text: str, start: int) -> None:
        block_spans[-1].append(
            OcrLineSpan(
                text,
                line.confidence,
                start,
                start + len(text),
                line.bbox,
            )
        )

    for line in lines:
        text = normalise_line(line.text)
        if not text:
            continue
        if previous is None:
            add_block(text, line)
            previous = line
            continue

        same_row = previous.row == line.row and previous.column == line.column
        if same_row and (previous.table_row or line.table_row):
            old_length = len(blocks[-1])
            blocks[-1] = f"{blocks[-1]} | {text}"
            add_span(line, text, old_length + 3)
            previous = line
            continue

        if _HYPHEN_BREAK.search(previous.text.strip()) and text[:1].islower():
            old_length = len(blocks[-1])
            blocks[-1] = _join_text(blocks[-1], text)
            if block_spans[-1]:
                previous_span = block_spans[-1][-1]
                block_spans[-1][-1] = replace(
                    previous_span,
                    text=(
                        previous_span.text[:-1]
                        if previous_span.text.endswith("-")
                        else previous_span.text
                    ),
                    end_offset=max(previous_span.start_offset, old_length - 1),
                )
            add_span(line, text, max(0, old_length - 1))
            previous = line
            continue

        if _new_block(previous, line, median_height):
            add_block(text, line)
        elif same_row:
            old_length = len(blocks[-1])
            blocks[-1] = f"{blocks[-1]} {text}"
            add_span(line, text, old_length + 1)
        else:
            old_length = len(blocks[-1])
            blocks[-1] = _join_text(blocks[-1], text)
            add_span(line, text, old_length + 1)
        previous = line

    text_parts: list[str] = []
    spans: list[OcrLineSpan] = []
    offset = 0
    for index, block in enumerate(blocks):
        if index:
            offset += 2
        for span in block_spans[index]:
            spans.append(
                replace(
                    span,
                    start_offset=span.start_offset + offset,
                    end_offset=span.end_offset + offset,
                )
            )
        text_parts.append(block)
        offset += len(block)

    return "\n\n".join(text_parts), tuple(spans)


def reconstruct_page_text(lines: list[OcrLine]) -> str:
    """Rebuild paragraphs, table rows and clause boundaries from OCR lines."""

    text, _spans = reconstruct_page_text_with_spans(lines)
    return text

def page_quality(
    lines: list[OcrLine],
    *,
    low_confidence_threshold: float | None = None,
    warning_threshold: float | None = None,
) -> PageQuality:
    """Calculate page-level confidence and low-confidence text diagnostics."""

    threshold = (
        settings.ocr_low_confidence_threshold
        if low_confidence_threshold is None
        else low_confidence_threshold
    )
    warning = (
        settings.ocr_quality_warning_threshold
        if warning_threshold is None
        else warning_threshold
    )
    if not lines:
        return PageQuality(
            confidence=None,
            min_confidence=None,
            low_confidence_ratio=0.0,
            low_confidence_lines=(),
            line_count=0,
            word_count=0,
            warnings=(),
        )

    weights = [max(1, len(line.text)) for line in lines]
    total_weight = sum(weights)
    confidence = sum(
        line.confidence * weight for line, weight in zip(lines, weights)
    ) / total_weight
    low_lines = [
        LowConfidenceLine(
            text=line.text,
            confidence=line.confidence,
            bbox=line.bbox,
        )
        for line in lines
        if line.confidence < threshold
    ]
    low_ratio = len(low_lines) / len(lines)
    warnings: list[str] = []
    if confidence < warning:
        warnings.append(
            f"OCR confidence {confidence:.2f} is below the warning threshold "
            f"{warning:.2f}."
        )
    if low_ratio > 0.20:
        warnings.append(
            f"{len(low_lines)} of {len(lines)} OCR text lines are low-confidence."
        )
    return PageQuality(
        confidence=round(confidence, 4),
        min_confidence=round(min(line.confidence for line in lines), 4),
        low_confidence_ratio=round(low_ratio, 4),
        low_confidence_lines=tuple(low_lines),
        line_count=len(lines),
        word_count=sum(len(line.text.split()) for line in lines),
        warnings=tuple(warnings),
    )


__all__ = [
    "LowConfidenceLine",
    "OcrLine",
    "OcrLineSpan",
    "PageQuality",
    "layout_lines",
    "normalise_line",
    "page_quality",
    "parse_rapidocr_result",
    "reconstruct_page_text",
    "reconstruct_page_text_with_spans",
]
