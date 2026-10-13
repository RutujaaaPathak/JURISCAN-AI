"""Segmentation tests driven by realistic legal-document fixtures.

Each fixture is segmented and checked for:

* exact, ordered, non-overlapping source offsets (original wording preserved);
* the expected label / level / parent-child hierarchy;
* a preserved preamble;
* determinism across repeated runs.

A separate test covers a clause that spans a PDF page break, and an end-to-end
test checks that risk findings reference the correct clause (by id and label).

Known limitations that are intentionally *not* fixed here are asserted in
``test_segmentation.py`` so that the current contract is documented explicitly.
"""

from __future__ import annotations

import pytest

from app.services.extraction import page_number_for_offset, validate_and_extract
from app.services.segmentation import segment_clauses
from tests.legal_fixtures import (
    ALL_FIXTURES,
    EMPLOYMENT_CONTRACT,
    PRIVACY_POLICY,
    RENTAL_AGREEMENT,
    SERVICE_AGREEMENT,
    SUBSCRIPTION_AGREEMENT,
    TERMS_AND_CONDITIONS,
)
from tests.pdf_factory import multi_page_pdf

# (label, level, parent label) for every segment, in document order. The first
# entry of each document is its preamble.
RENTAL_EXPECTED = [
    (None, 1, None),
    ("1", 1, None),
    ("2", 1, None),
    ("2.1", 2, "2"),
    ("2.2", 2, "2"),
    ("3", 1, None),
    ("(a)", 3, "3"),
    ("(b)", 3, "3"),
    ("(c)", 3, "3"),
    ("4", 1, None),
    ("5", 1, None),
]

EMPLOYMENT_EXPECTED = [
    (None, 1, None),
    ("1", 1, None),
    ("1.1", 2, "1"),
    ("1.2", 2, "1"),
    ("2", 1, None),
    ("2.1", 2, "2"),
    ("2.2", 2, "2"),
    ("2.3", 2, "2"),
    ("3", 1, None),
    ("(a)", 3, "3"),
    ("(b)", 3, "3"),
    ("4", 1, None),
    ("4.1", 2, "4"),
    ("4.2", 2, "4"),
    ("5", 1, None),
]

PRIVACY_EXPECTED = [
    (None, 1, None),
    ("1", 1, None),
    ("2", 1, None),
    ("2.1", 2, "2"),
    ("2.2", 2, "2"),
    ("3", 1, None),
    ("3.1", 2, "3"),
    ("3.2", 2, "3"),
    ("4", 1, None),
    ("(a)", 3, "4"),
    ("(b)", 3, "4"),
    ("(c)", 3, "4"),
    ("5", 1, None),
]

TERMS_EXPECTED = [
    (None, 1, None),
    ("1", 1, None),
    ("2", 1, None),
    ("2.1", 2, "2"),
    ("2.2", 2, "2"),
    ("3", 1, None),
    ("3.1", 2, "3"),
    ("3.2", 2, "3"),
    ("4", 1, None),
    ("(a)", 3, "4"),
    ("(b)", 3, "4"),
    ("5", 1, None),
]

SERVICE_EXPECTED = [
    (None, 1, None),
    ("1", 1, None),
    ("2", 1, None),
    ("2.1", 2, "2"),
    ("2.2", 2, "2"),
    ("2.2.1", 3, "2.2"),
    ("2.2.2", 3, "2.2"),
    ("2.3", 2, "2"),
    ("3", 1, None),
    ("3.1", 2, "3"),
    ("3.2", 2, "3"),
    ("4", 1, None),
    ("5", 1, None),
]

SUBSCRIPTION_EXPECTED = [
    (None, 1, None),
    ("1", 1, None),
    ("1.1", 2, "1"),
    ("(i)", 4, "1.1"),
    ("(ii)", 4, "1.1"),
    ("2", 1, None),
    (None, 4, "2"),
    (None, 4, "2"),
    (None, 4, "2"),
    ("3", 1, None),
    ("3.1", 2, "3"),
]

CASES = {
    "rental": (RENTAL_AGREEMENT, RENTAL_EXPECTED),
    "employment": (EMPLOYMENT_CONTRACT, EMPLOYMENT_EXPECTED),
    "privacy": (PRIVACY_POLICY, PRIVACY_EXPECTED),
    "terms": (TERMS_AND_CONDITIONS, TERMS_EXPECTED),
    "service": (SERVICE_AGREEMENT, SERVICE_EXPECTED),
    "subscription": (SUBSCRIPTION_AGREEMENT, SUBSCRIPTION_EXPECTED),
}


def _assert_exact_slices(text: str, segments) -> None:
    assert [segment.number for segment in segments] == list(
        range(1, len(segments) + 1)
    )
    for segment in segments:
        assert segment.text
        assert text[segment.start_offset : segment.end_offset] == segment.text
        assert segment.end_offset - segment.start_offset == len(segment.text)
    for earlier, later in zip(segments, segments[1:]):
        assert earlier.end_offset <= later.start_offset


@pytest.mark.parametrize("name", list(CASES))
def test_fixture_structure_and_hierarchy(name):
    text, expected = CASES[name]
    segments = segment_clauses(text)

    assert len(segments) == len(expected)
    labels = [item[0] for item in expected]
    for index, (segment, (label, level, parent_label)) in enumerate(
        zip(segments, expected)
    ):
        assert segment.number == index + 1
        assert segment.label == label, (name, index, segment.label, label)
        assert segment.level == level, (name, index, segment.level, level)
        if parent_label is None:
            assert segment.parent is None, (name, index, segment.parent)
        else:
            assert segment.parent == labels.index(parent_label), (
                name,
                index,
                segment.parent,
                parent_label,
            )

    _assert_exact_slices(text, segments)


@pytest.mark.parametrize("name", list(ALL_FIXTURES))
def test_fixture_preserves_preamble(name):
    text = ALL_FIXTURES[name]
    segments = segment_clauses(text)

    preamble = segments[0]
    assert preamble.kind == "preamble"
    assert preamble.label is None
    assert preamble.level == 1
    assert preamble.parent is None
    # The preamble is the real text before the first numbered clause.
    assert text[preamble.start_offset : preamble.end_offset] == preamble.text
    assert preamble.start_offset == 0


@pytest.mark.parametrize("name", list(ALL_FIXTURES))
def test_fixture_segmentation_is_deterministic(name):
    text = ALL_FIXTURES[name]
    first = segment_clauses(text)
    second = segment_clauses(text)
    signature = lambda segs: [  # noqa: E731 - small local helper
        (s.number, s.label, s.level, s.parent, s.start_offset, s.end_offset)
        for s in segs
    ]
    assert signature(first) == signature(second)


def test_fixture_wording_is_never_rewritten():
    # A spot check that the stored text is a verbatim slice, not a reconstruction.
    for text in ALL_FIXTURES.values():
        for segment in segment_clauses(text):
            assert text[segment.start_offset : segment.end_offset] == segment.text


def test_clause_spanning_pdf_page_break_maps_to_start_page():
    data = multi_page_pdf(
        [
            [
                "1. Definitions",
                "In this Agreement the terms below apply throughout.",
                "2. Services",
                "2.1 The Supplier shall provide the Services described in each",
            ],
            [
                "Statement of Work and shall perform them with reasonable care.",
                "3. Payment",
                "3.1 The Customer shall pay each valid invoice within thirty days.",
            ],
        ]
    )
    extracted = validate_and_extract(data, "service.pdf", "application/pdf")
    segments = segment_clauses(extracted.text)

    by_label = {segment.label: segment for segment in segments}

    # 2.1 starts on page 1 but its body continues onto page 2.
    clause_2_1 = by_label["2.1"]
    assert "described in each" in clause_2_1.text
    assert "Statement of Work" in clause_2_1.text
    assert page_number_for_offset(extracted.pages, clause_2_1.start_offset) == 1

    # 3 starts on page 2.
    assert page_number_for_offset(extracted.pages, by_label["3"].start_offset) == 2
    assert page_number_for_offset(extracted.pages, by_label["3.1"].start_offset) == 2

    _assert_exact_slices(extracted.text, segments)


def test_api_findings_reference_segmented_clause(client):
    resp = client.post(
        "/api/documents",
        files={
            "file": (
                "service.txt",
                SERVICE_AGREEMENT.encode("utf-8"),
                "text/plain",
            )
        },
        data={"title": "Master Services Agreement"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    clauses = body["clauses"]
    assert len(clauses) == len(SERVICE_EXPECTED)

    clauses_by_id = {clause["id"]: clause for clause in clauses}
    indemnity = next(
        clause for clause in clauses if "indemnify" in clause["text"]
    )
    assert indemnity["label"] == "4"
    assert indemnity["level"] == 1

    findings = body["analysis"]["findings"]
    uncapped = next(
        finding for finding in findings if finding["rule_code"] == "UNCAPPED_INDEMNITY"
    )
    # The finding points at the exact clause it was derived from.
    assert uncapped["clause_id"] == indemnity["id"]
    assert uncapped["clause_label"] == "4"
    assert uncapped["clause_level"] == 1
    assert clauses_by_id[uncapped["clause_id"]]["text"] == indemnity["text"]
