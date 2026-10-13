"""Focused unit tests for deterministic clause segmentation.

Each structural pattern the segmenter claims to support gets a dedicated case,
along with malformed, unnumbered and page-spanning documents.
"""

from app.services.extraction import validate_and_extract
from app.services.segmentation import Segment, segment_clauses
from tests.pdf_factory import multi_page_pdf


def _assert_exact_slices(text: str, segments: list[Segment]) -> None:
    """Every segment must map back to an exact, ordered, non-overlapping slice."""

    assert [segment.number for segment in segments] == list(
        range(1, len(segments) + 1)
    )
    for segment in segments:
        assert segment.text
        assert text[segment.start_offset : segment.end_offset] == segment.text
        assert segment.end_offset - segment.start_offset == len(segment.text)
    for earlier, later in zip(segments, segments[1:]):
        assert earlier.end_offset <= later.start_offset


def test_decimal_numbering_builds_parent_child_hierarchy():
    text = (
        "1. Definitions\n"
        "In this Agreement the following terms have the meanings given.\n\n"
        "2. Obligations\n"
        "2.1 The Supplier shall provide the Services with reasonable skill and care.\n"
        "2.2 The Customer shall pay the fees when they become due under this Agreement.\n"
        "2.3 Each party shall comply with all applicable laws at all times.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 5
    assert [segment.label for segment in segments] == ["1", "2", "2.1", "2.2", "2.3"]
    assert [segment.level for segment in segments] == [1, 1, 2, 2, 2]
    assert [segment.parent for segment in segments] == [None, None, 1, 1, 1]
    _assert_exact_slices(text, segments)


def test_keyword_and_roman_headings():
    text = (
        "ARTICLE I\n"
        "Definitions and interpretation apply throughout this Agreement.\n\n"
        "ARTICLE II\n"
        "The obligations of the parties are set out in the following clauses.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 2
    assert segments[0].label == "ARTICLE I"
    assert segments[1].label == "ARTICLE II"
    assert all(segment.level == 1 for segment in segments)
    assert all(segment.heading in {"ARTICLE I", "ARTICLE II"} for segment in segments)
    _assert_exact_slices(text, segments)


def test_keyword_decimal_sections_nest_by_depth():
    text = (
        "Section 4.1 Payment\n"
        "Payment shall be due within thirty (30) days of a valid invoice.\n\n"
        "Section 4.2 Interest\n"
        "Interest accrues on late payments at the agreed contractual rate.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 2
    assert [segment.level for segment in segments] == [2, 2]
    assert segments[0].kind == "keyword"
    assert segments[0].label == "Section 4.1"
    _assert_exact_slices(text, segments)


def test_parenthesised_lettered_subclauses_nest_under_their_clause():
    text = (
        "3. Warranties\n"
        "3.1 The Supplier warrants to the Customer that:\n"
        "(a) it has full authority to enter into this Agreement;\n"
        "(b) the Services will conform to the agreed specification;\n"
        "(c) it will comply with all applicable laws and regulations.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 5
    assert [segment.label for segment in segments] == ["3", "3.1", "(a)", "(b)", "(c)"]
    assert [segment.level for segment in segments] == [1, 2, 3, 3, 3]
    assert [segment.parent for segment in segments] == [None, 0, 1, 1, 1]
    assert segments[2].kind == "letter"
    _assert_exact_slices(text, segments)


def test_roman_numerals_and_bullets_are_recognised():
    text = (
        "5. Confidentiality\n"
        "(i) Each party shall keep the other's information confidential.\n"
        "(ii) This obligation survives termination of this Agreement for five years.\n"
        "- Disclosure required by law is permitted without notice.\n"
        "- Disclosure made with prior written consent is permitted.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 5
    assert segments[1].kind == "roman"
    assert segments[2].kind == "roman"
    assert segments[3].kind == "bullet"
    assert segments[3].label is None
    _assert_exact_slices(text, segments)


def test_lettered_and_lettered_upper_markers():
    text = (
        "SCHEDULE A\n"
        "A. Services\nThe Supplier shall provide the following services.\n"
        "B. Fees\nThe Customer shall pay the fees set out in this Schedule.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 3
    assert segments[0].kind == "keyword"
    assert segments[0].label == "SCHEDULE A"
    assert [segment.label for segment in segments[1:]] == ["A", "B"]
    assert all(segment.kind == "letter" for segment in segments[1:])
    assert [segment.parent for segment in segments[1:]] == [0, 0]
    _assert_exact_slices(text, segments)


def test_unnumbered_document_falls_back_to_paragraphs():
    text = (
        "This Agreement is made between the parties on the date first written above.\n\n"
        "The parties agree to act in good faith at all times during the term.\n\n"
        "Nothing in this Agreement creates a partnership between the parties.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 3
    assert all(segment.label is None for segment in segments)
    assert all(segment.kind == "paragraph" for segment in segments)
    assert all(segment.level == 1 for segment in segments)
    assert all(text[segment.start_offset : segment.end_offset].strip() == segment.text for segment in segments)


def test_wrapped_sentences_are_not_split():
    text = (
        "The Supplier shall provide the Services in a professional manner\n"
        "and shall comply with all reasonable instructions given by the Customer\n"
        "from time to time during the term of this Agreement."
    )

    segments = segment_clauses(text)

    assert len(segments) == 1
    assert "professional manner\nand shall comply" in segments[0].text


def test_irregular_whitespace_and_blank_lines():
    text = (
        "  1.   Indemnity\n"
        "\n\n"
        "   The Supplier shall indemnify the Customer against all losses.\n"
        "\n"
        "   2.   Payment\n"
        "   Payment is due within thirty (30) days of a valid invoice.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 2
    assert "indemnify" in segments[0].text
    assert segments[1].start_offset > segments[0].end_offset
    _assert_exact_slices(text, segments)


def test_malformed_numbering_does_not_crash_or_oversplit():
    text = (
        "1. First real clause with sufficient wording to stand alone.\n"
        "1..2 This malformed numbering should not create a nested clause.\n"
        "(1.2 This unterminated marker is just prose and must not split.\n"
        "2. Second real clause that also has enough words to be meaningful.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 2
    assert segments[0].label == "1"
    assert segments[1].label == "2"
    assert "malformed numbering" in segments[0].text
    _assert_exact_slices(text, segments)


def test_single_numbered_heading_keeps_its_body_together():
    text = "1. Definitions\nThis section defines the terms used in this Agreement."

    segments = segment_clauses(text)

    assert len(segments) == 1
    assert segments[0].heading == "1. Definitions"
    assert segments[0].label == "1"
    assert "defines the terms" in segments[0].text


def test_preamble_before_first_clause_is_preserved():
    text = (
        "This Agreement is entered into between the parties named below.\n\n"
        "1. Definitions\nThe following terms have the meanings set out below.\n\n"
        "2. Term\nThe Agreement begins on the Effective Date and continues.\n"
    )

    segments = segment_clauses(text)

    assert len(segments) == 3
    assert segments[0].kind == "preamble"
    assert segments[0].label is None
    assert segments[0].text.startswith("This Agreement is entered into")
    assert [segment.label for segment in segments[1:]] == ["1", "2"]
    _assert_exact_slices(text, segments)


def test_page_break_does_not_split_a_single_clause():
    data = multi_page_pdf(
        [
            ["1. Indemnity", "The Supplier shall indemnify the Customer for all"],
            ["losses, claims and damages of whatsoever nature."],
        ]
    )
    extracted = validate_and_extract(data, "contract.pdf", "application/pdf")

    segments = segment_clauses(extracted.text)

    assert len(segments) == 1
    assert segments[0].start_offset == 0
    assert "for all" in segments[0].text and "losses, claims" in segments[0].text
    # The whole clause maps back to the extracted text exactly.
    assert extracted.text[segments[0].start_offset : segments[0].end_offset] == segments[0].text


def test_segmentation_is_deterministic():
    text = (
        "1. Indemnity\nThe Supplier shall indemnify the Customer against all losses.\n\n"
        "2. Payment\nPayment is due within ninety (90) days of a valid invoice.\n"
    )
    first = segment_clauses(text)
    second = segment_clauses(text)
    assert [(s.number, s.label, s.level, s.start_offset, s.end_offset) for s in first] == [
        (s.number, s.label, s.level, s.start_offset, s.end_offset) for s in second
    ]
