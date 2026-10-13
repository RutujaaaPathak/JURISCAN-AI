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

Known limitations (documented and asserted by tests rather than papered over):

* Inline numbering inside a wrapping paragraph (``2.1 ... 2.2 ...`` on one line)
  is not split. Doing so safely would require re-flowing the original text, so
  the whole paragraph is returned as a single segment.
* An unnumbered all-caps heading (``CONFIDENTIALITY``) is not treated as a
  boundary while the document contains numbered clauses, so it stays inside the
  surrounding clause. In a document with no numbering at all, paragraph
  grouping keeps it as the first line of its block.
* A single lowercase ``i``/``v``/``x`` marker is ambiguous with a lettered item.
  Only parenthesised forms (``(i)``) and multi-letter Roman tokens (``ii.``,
  ``iv)``) are treated as Roman numerals; single lowercase letters follow the
  lettered-marker rules (``i`` is ignored to avoid misreading prose).
* Hierarchy is inferred from nesting depth, not from numeric prefixes, so a
  ``2.2.1`` clause with no preceding ``2.2`` nests under the nearest shallower
  clause instead.
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
# Bare lowercase Roman subclause marker: "iv.", "iv)", "iii.". Restricted to
# multi-letter tokens so a single letter ("a)", "c)") is never reinterpreted.
_BARE_ROMAN_LOWER = re.compile(
    rf"^(?P<lead>{_LEAD})(?P<num>[ivxlcdm]{{2,7}})(?P<sep>[.)])\s+(?P<title>\S.*)$"
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
    # nesting depth (1 = top level) and ``parent`` is the 0-based index of the nearest
    # enclosing segment, or ``None``. These are persisted onto Clause records.
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

    match = _BARE_ROMAN_LOWER.match(content)
    if match and _looks_roman(match.group("num")):
        # Lowercase Roman markers are subclause numerals, so they nest like the
        # parenthesised form rather than opening a new top-level section.
        return _Boundary(match.group("num"), 4, "roman", stripped, len(match.group("lead")))

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


def _stripped_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Tighten ``[start, end)`` to the first/last non-whitespace characters."""

    raw = text[start:end]
    left = len(raw) - len(raw.lstrip())
    right = len(raw.rstrip())
    if right <= left:
        return start, start
    return start + left, start + right


def _segments_from_paragraphs(text: str) -> list[Segment]:
    # Collect exact source spans for each paragraph rather than trimmed strings,
    # so merged paragraphs keep an exact ``text[start:end]`` mapping (the blank
    # line between merged blocks is part of the slice).
    spans: list[list[int]] = []
    position = 0
    for separator in _PARAGRAPH_BREAK.finditer(text):
        start, end = _stripped_span(text, position, separator.start())
        if end > start:
            spans.append([start, end])
        position = separator.end()
    start, end = _stripped_span(text, position, len(text))
    if end > start:
        spans.append([start, end])

    if not spans:
        return []

    merged: list[list[int]] = []
    for start, end in spans:
        if merged and (merged[-1][1] - merged[-1][0]) < MIN_CLAUSE_CHARACTERS:
            merged[-1][1] = end
        else:
            merged.append([start, end])

    segments: list[Segment] = []
    for start, end in merged:
        block = text[start:end]
        heading = None
        first = _first_line(block)
        if first and len(first) <= MAX_HEADING_LENGTH and len(block) > len(first):
            heading = first
        segments.append(
            Segment(
                number=len(segments) + 1,
                heading=_stored_heading(heading),
                text=block,
                start_offset=start,
                end_offset=end,
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
