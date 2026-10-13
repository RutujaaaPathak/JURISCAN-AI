"""Deterministic legal-clause segmentation.

This is an explainable, rule-based baseline; no machine-learning model is
involved. It recognises the common ways legal documents mark structure:

* keyword headings — ``Clause 3``, ``ARTICLE IV``, ``Section 4.2``, ``Part 2``,
  ``Schedule A``, ``Appendix I``, ``Annex 1``, ``Paragraph 7``;
* decimal numbering — ``1.``, ``2.1``, ``2.1.1`` (level = number of parts);
* Roman numerals — ``IV.``, ``(iv)``, ``iv)``;
* lettered subclauses — ``(a)``, ``a)``, ``A.``;
* bullets — ``-``, ``*``, ``•``, ``·`` and dash bullets;
* parenthesised markers — ``(1)``, ``(a)``, ``(iv)``.

Each recognised marker starts a new clause/subclause. Text before the first
marker (a preamble or unnumbered intro) is kept as its own segment, and
paragraph/blank-line boundaries are used when no explicit numbering is present.

The original wording is never rewritten: ``Segment.text`` is an exact (trimmed)
slice of the source string and ``start_offset``/``end_offset`` map back into it.
Split points come from content, not from page breaks, so a clause that spills
onto the next page is not torn in two (its page number is the page it starts on,
computed later from the page spans).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MIN_CLAUSE_CHARACTERS = 40
MAX_HEADING_LENGTH = 240
MAX_STORED_HEADING = 255

_LEAD = r"[ \t]*"
_DECIMAL = r"\d{1,3}(?:\.\d{1,4}){0,5}"
_ROMAN = r"[IVXLCDM]{1,7}"
_LETTER = r"[A-Za-z]{1,3}"

_ROMAN_STRICT = re.compile(
    r"^M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$",
    re.IGNORECASE,
)
_DECIMAL_FULL = re.compile(rf"^{_DECIMAL}$")

# Keyword-prefixed headings: "Clause 3", "ARTICLE IV", "Section 4.2", "Part 2".
_KEYWORD_HEADING = re.compile(
    rf"^(?P<lead>{_LEAD})"
    rf"(?P<kw>clause|article|section|schedule|appendix|annex|part|paragraph|recital)"
    rf"\s+(?P<num>(?:{_DECIMAL})|(?:{_ROMAN})|(?:{_LETTER}))"
    rf"(?P<sep>[.):\]]?)"
    rf"(?:[\s:.\-–—]+(?P<title>\S.*))?$",
    re.IGNORECASE,
)

# Parenthesised markers: "(1)", "(a)", "(iv)", "(2.1)".
_PAREN_MARKER = re.compile(
    rf"^(?P<lead>{_LEAD})\((?P<num>(?:{_DECIMAL})|(?:{_ROMAN})|(?:{_LETTER}))\)"
    rf"(?:\s+(?P<title>\S.*))?$",
    re.IGNORECASE,
)

# Bare decimal markers: "1.", "2.1", "2.1.1", "3)".
_BARE_DECIMAL = re.compile(
    rf"^(?P<lead>{_LEAD})(?P<num>{_DECIMAL})(?P<sep>[.):])(?:\s+(?P<title>\S.*))?$"
)
# Decimal marker followed by a capitalised title without punctuation: "1 Indemnity".
_BARE_DECIMAL_SPACE = re.compile(
    rf"^(?P<lead>{_LEAD})(?P<num>{_DECIMAL})\s+(?P<title>[A-Z(][^\n]*)$"
)
# Bare uppercase Roman marker: "IV.", "IV)".
_BARE_ROMAN = re.compile(
    rf"^(?P<lead>{_LEAD})(?P<num>{_ROMAN})(?P<sep>[.):])(?:\s+(?P<title>\S.*))?$"
)
# Bare uppercase lettered marker: "A. Definitions", "B) Term".
_BARE_LETTER_UPPER = re.compile(
    rf"^(?P<lead>{_LEAD})(?P<num>[A-H])(?P<sep>[.)])\s+(?P<title>[A-Z][^\n]*)$"
)
# Lowercase lettered marker: "a) ...", "b. ...".
_BARE_LETTER = re.compile(
    rf"^(?P<lead>{_LEAD})(?P<num>[a-hj-z])(?P<sep>[.)])\s+(?P<title>\S.*)$"
)
# Bullet markers.
_BULLET = re.compile(
    rf"^(?P<lead>{_LEAD})(?P<marker>[-*•·◦▪‣–—])\s+(?P<title>\S.*)$"
)

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n+")


@dataclass(slots=True)
class Segment:
    number: int
    heading: str | None
    text: str
    start_offset: int
    end_offset: int
    # Structural metadata (best-effort, deterministic). ``level`` is the inferred
    # nesting depth (1 = top level) and ``parent`` is the index of the nearest
    # enclosing segment, or ``None``. These are not persisted yet, so existing
    # clause records and APIs are unaffected.
    label: str | None = None
    level: int = 1
    parent: int | None = None
    kind: str | None = None


@dataclass(slots=True)
class _Boundary:
    label: str | None
    level: int
    kind: str
    heading: str
    offset: int


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _looks_roman(token: str) -> bool:
    """True for a plausible Roman-numeral marker (avoids single I/V/X-like letters)."""

    if not token or not _ROMAN_STRICT.match(token):
        return False
    if len(token) == 1:
        # Single-letter Roman markers are only trusted for i/v/x, the common
        # subclause numerals; otherwise "(c)"/"C." etc. are treated as letters.
        return token.upper() in {"I", "V", "X"}
    return True


def _classify(token: str, *, parenthesized: bool) -> tuple[str, int] | None:
    if _DECIMAL_FULL.match(token):
        # "1" -> level 1, "2.1" -> level 2, "2.1.1" -> level 3.
        return "decimal", (2 if parenthesized else token.count(".") + 1)
    if _looks_roman(token):
        # "(iv)" nests below lettered sub-items; bare "IV." is a top level.
        return "roman", (4 if parenthesized else 1)
    if token.isalpha():
        # "(a)" nests below a decimal subclause; bare "A." is a top level.
        return "letter", (3 if parenthesized else 2)
    return None


def _detect_boundary(content: str) -> _Boundary | None:
    """Return the structural marker starting ``content`` (a single line), if any."""

    stripped = content.strip()
    if not stripped or len(stripped) > MAX_HEADING_LENGTH:
        return None

    match = _KEYWORD_HEADING.match(content)
    if match:
        num = match.group("num").strip()
        classified = _classify(num, parenthesized=False)
        kind = classified[0] if classified else "keyword"
        level = 1 if kind != "decimal" else num.count(".") + 1
        label = f"{match.group('kw')} {num}".strip()
        return _Boundary(label, max(1, level), "keyword", stripped, len(match.group("lead")))

    match = _PAREN_MARKER.match(content)
    if match:
        num = match.group("num").strip()
        classified = _classify(num, parenthesized=True)
        kind, level = classified or ("marker", 2)
        return _Boundary(f"({num})", level, kind, stripped, len(match.group("lead")))

    match = _BARE_DECIMAL.match(content)
    if match:
        num = match.group("num")
        return _Boundary(num, num.count(".") + 1, "decimal", stripped, len(match.group("lead")))

    match = _BARE_DECIMAL_SPACE.match(content)
    if match:
        num = match.group("num")
        return _Boundary(num, num.count(".") + 1, "decimal", stripped, len(match.group("lead")))

    match = _BARE_ROMAN.match(content)
    if match and _looks_roman(match.group("num")):
        return _Boundary(match.group("num"), 1, "roman", stripped, len(match.group("lead")))

    match = _BARE_LETTER_UPPER.match(content)
    if match:
        return _Boundary(match.group("num"), 2, "letter", stripped, len(match.group("lead")))

    match = _BARE_LETTER.match(content)
    if match:
        return _Boundary(match.group("num"), 2, "letter", stripped, len(match.group("lead")))

    match = _BULLET.match(content)
    if match:
        return _Boundary(None, 4, "bullet", stripped, len(match.group("lead")))

    return None


def _find_boundaries(text: str) -> list[tuple[int, _Boundary]]:
    boundaries: list[tuple[int, _Boundary]] = []
    position = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\n")
        if content.strip():
            boundary = _detect_boundary(content)
            if boundary is not None:
                boundaries.append((position + boundary.offset, boundary))
        position += len(line)
    return boundaries


def _stored_heading(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return value[:MAX_STORED_HEADING] or None


def _append_segment(
    segments: list[Segment],
    text: str,
    start: int,
    end: int,
    *,
    heading: str | None,
    label: str | None,
    level: int,
    kind: str | None,
) -> None:
    raw = text[start:end]
    stripped = raw.strip()
    if not stripped:
        return
    leading = len(raw) - len(raw.lstrip())
    segment_start = start + leading
    segments.append(
        Segment(
            number=len(segments) + 1,
            heading=_stored_heading(heading),
            text=stripped,
            start_offset=segment_start,
            end_offset=segment_start + len(stripped),
            label=label,
            level=level,
            kind=kind,
        )
    )


def _assign_parents(segments: list[Segment]) -> None:
    stack: list[int] = []
    for index, segment in enumerate(segments):
        while stack and segments[stack[-1]].level >= segment.level:
            stack.pop()
        segment.parent = stack[-1] if stack else None
        stack.append(index)


def _segments_from_boundaries(
    text: str, boundaries: list[tuple[int, _Boundary]]
) -> list[Segment]:
    segments: list[Segment] = []

    first_start = boundaries[0][0]
    if first_start > 0:
        _append_segment(
            segments,
            text,
            0,
            first_start,
            heading=_first_line(text[:first_start]),
            label=None,
            level=1,
            kind="preamble",
        )

    for index, (start, boundary) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        _append_segment(
            segments,
            text,
            start,
            end,
            heading=boundary.heading,
            label=boundary.label,
            level=boundary.level,
            kind=boundary.kind,
        )

    _assign_parents(segments)
    return segments


def _segments_from_paragraphs(text: str) -> list[Segment]:
    blocks: list[tuple[int, str]] = []
    position = 0
    for separator in _PARAGRAPH_BREAK.finditer(text):
        block = text[position : separator.start()]
        if block.strip():
            blocks.append((position, block.strip()))
        position = separator.end()
    tail = text[position:]
    if tail.strip():
        blocks.append((position, tail.strip()))

    if not blocks:
        single = text.strip()
        if not single:
            return []
        return [
            Segment(
                number=1,
                heading=_stored_heading(_first_line(single)),
                text=single,
                start_offset=0,
                end_offset=len(text),
                level=1,
                kind="paragraph",
            )
        ]

    merged: list[tuple[int, str]] = []
    for offset, block in blocks:
        if merged and len(merged[-1][1]) < MIN_CLAUSE_CHARACTERS:
            previous_offset, previous_block = merged[-1]
            merged[-1] = (previous_offset, f"{previous_block}\n{block}")
        else:
            merged.append((offset, block))

    segments: list[Segment] = []
    for offset, block in merged:
        heading = None
        first = _first_line(block)
        if first and len(first) <= MAX_HEADING_LENGTH and len(block) > len(first):
            heading = first
        segments.append(
            Segment(
                number=len(segments) + 1,
                heading=_stored_heading(heading),
                text=block,
                start_offset=offset,
                end_offset=offset + len(block),
                level=1,
                kind="paragraph",
            )
        )
    return segments


def segment_clauses(text: str) -> list[Segment]:
    """Split document text into ordered clause segments with character offsets.

    Explicit structural markers take precedence; when fewer than two are found
    the text is grouped by paragraph/blank-line boundaries instead, preserving
    the original wording and offsets in both cases.
    """

    if not text.strip():
        return []

    boundaries = _find_boundaries(text)
    # Use explicit markers when the document clearly has structure (two or more
    # markers) or when a single marker opens the document. A lone marker buried
    # after a preamble is more likely an incidental list item, so the document is
    # grouped by paragraphs instead. This also keeps a clause that runs across a
    # PDF page break together, because the split points come only from markers.
    if boundaries:
        opens_document = not text[: boundaries[0][0]].strip()
        if len(boundaries) >= 2 or opens_document:
            segments = _segments_from_boundaries(text, boundaries)
            if segments:
                return segments

    return _segments_from_paragraphs(text)


__all__ = ["Segment", "segment_clauses"]
