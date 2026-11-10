"""Conservative text normalisation for explainable legal-rule matching.

The original clause text is always preserved. This module produces a separate
detection copy that fixes common OCR artefacts and maps a small set of legal
synonyms onto the wording the rule engine already understands. Every rewrite is
recorded so the transformation remains auditable.
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.services.segmentation import Segment

_CHAR_MAP = str.maketrans(
    {
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2011": "-",
        "\u00ad": "",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb00": "ff",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
    }
)
_SPACE = re.compile(r"[ \t\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_OCR_TERMS = (
    (re.compile(r"\bindemnitv\b", re.IGNORECASE), "indemnify"),
    (re.compile(r"\bindemnlty\b", re.IGNORECASE), "indemnity"),
    (re.compile(r"\bliabilitv\b", re.IGNORECASE), "liability"),
    (re.compile(r"\bterminatlon\b", re.IGNORECASE), "termination"),
    (re.compile(r"\bpayrnent\b", re.IGNORECASE), "payment"),
    (re.compile(r"\bconfidentlal\b", re.IGNORECASE), "confidential"),
    (re.compile(r"\bagreernent\b", re.IGNORECASE), "agreement"),
)
_SYNONYMS = (
    (re.compile(r"\bhold\s+harmless\b", re.IGNORECASE), "indemnify", "hold_harmless"),
    (re.compile(r"\bsave\s+harmless\b", re.IGNORECASE), "indemnify", "save_harmless"),
    (
        re.compile(r"\bpersonal\s+information\b", re.IGNORECASE),
        "personal data",
        "personal_information",
    ),
    (
        re.compile(r"\bauto[-\s]?renew(?:al|s|ed|ing)?\b", re.IGNORECASE),
        "automatically renew",
        "auto_renew",
    ),
    (
        re.compile(r"\bnon[-\s]?compete\b", re.IGNORECASE),
        "non-compete",
        "non_compete",
    ),
    (
        re.compile(r"\bgoverning\s+laws\b", re.IGNORECASE),
        "governing law",
        "governing_laws",
    ),
    (
        re.compile(r"\bterminate\s+at\s+will\b", re.IGNORECASE),
        "terminate without cause",
        "terminate_at_will",
    ),
    (
        re.compile(r"\bat\s+(?:its|their)\s+sole\s+option\b", re.IGNORECASE),
        "at its sole discretion",
        "sole_option",
    ),
)


def _change(rule: str, before: str, after: str, count: int) -> dict:
    return {
        "rule": rule,
        "before": before,
        "after": after,
        "count": count,
    }


def normalize_legal_text(text: str) -> tuple[str, list[dict]]:
    """Return a detection-only normalised copy and a list of applied changes."""

    normalized = text.translate(_CHAR_MAP)
    changes: list[dict] = []
    if normalized != text:
        changes.append(
            _change(
                "unicode",
                "unicode punctuation or compatibility characters",
                "ASCII equivalents",
                1,
            )
        )

    collapsed = _SPACE.sub(" ", normalized)
    collapsed = _BLANK_LINES.sub("\n\n", collapsed)
    if collapsed != normalized:
        changes.append(
            _change("whitespace", "irregular whitespace", "normalised whitespace", 1)
        )
    normalized = collapsed

    for pattern, replacement in _OCR_TERMS:
        normalized, count = pattern.subn(replacement, normalized)
        if count:
            changes.append(
                _change(
                    "ocr_term",
                    pattern.pattern,
                    replacement,
                    count,
                )
            )

    for pattern, replacement, rule in _SYNONYMS:
        normalized, count = pattern.subn(replacement, normalized)
        if count:
            changes.append(
                _change(rule, pattern.pattern, replacement, count)
            )

    return normalized, changes


def normalize_segment(segment: Segment) -> Segment:
    """Attach a normalised detection copy to a segment without changing its text."""

    normalized, changes = normalize_legal_text(segment.text)
    return replace(
        segment,
        normalized_text=normalized,
        normalization_changes=tuple(changes),
    )


def normalize_segments(segments: list[Segment]) -> list[Segment]:
    return [normalize_segment(segment) for segment in segments]


__all__ = [
    "normalize_legal_text",
    "normalize_segment",
    "normalize_segments",
]
