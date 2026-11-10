import cv2
import numpy as np

from app.services import ocr as ocr_module
from app.services.ocr_layout import (
    OcrLine,
    layout_lines,
    page_quality,
    reconstruct_page_text,
    reconstruct_page_text_with_spans,
)
from app.services.ocr_merge import native_text_quality, select_page_text
from app.services.ocr_preprocess import estimate_skew, prepare_page
from tests.pdf_factory import multi_page_pdf


def _line(text, x0, y0, x1, y1, confidence=0.9):
    return OcrLine(
        text=text,
        confidence=confidence,
        bbox=(x0, y0, x1, y1),
    )


def _png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def _text_image() -> np.ndarray:
    image = np.full((500, 400), 255, dtype=np.uint8)
    for index in range(8):
        cv2.putText(
            image,
            "Legal text line",
            (20, 70 + index * 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            0,
            2,
        )
    return image


class _AngleEngine:
    def __init__(self, labels):
        self.labels = labels

    def load_img(self, image):
        return np.zeros((20, 20, 3), dtype=np.uint8)

    def get_crop_img_list(self, image, boxes):
        return [image for _ in boxes]

    def text_cls(self, crops):
        return crops, self.labels, 0.0


def test_upside_down_detection_uses_angle_classifier():
    box = [[0, 0], [20, 0], [20, 8], [0, 8]]
    result = [[box, "text", 0.9], [box, "more text", 0.8]]

    upside_down = _AngleEngine([["180", 0.95], ["180", 0.92]])
    assert ocr_module._is_upside_down(upside_down, b"", result)

    upright = _AngleEngine([["0", 0.99], ["180", 0.95]])
    assert not ocr_module._is_upside_down(upright, b"", result)


def test_prepare_page_detects_sideways_scan_and_deskews():
    upright = _text_image()
    sideways = cv2.rotate(upright, cv2.ROTATE_90_CLOCKWISE)

    prepared = prepare_page(_png(sideways))

    assert prepared.rotation == 90
    assert "rotation_90" in prepared.steps
    assert prepared.width > 0 and prepared.height > 0

    counter_sideways = cv2.rotate(
        upright, cv2.ROTATE_90_COUNTERCLOCKWISE
    )
    assert prepare_page(_png(counter_sideways)).rotation == 90

    matrix = cv2.getRotationMatrix2D((200, 250), 5, 1)
    skewed = cv2.warpAffine(
        upright, matrix, (400, 500), borderValue=255
    )
    angle = estimate_skew(skewed)
    assert abs(angle) > 2


def test_prepare_page_does_not_rotate_upright_text_after_trimming():
    prepared = prepare_page(_png(_text_image()))

    assert prepared.rotation == 0
    assert "rotation_90" not in prepared.steps


def test_layout_orders_columns_and_preserves_headers_footers():
    lines = [
        _line("HEADER", 50, 20, 550, 35),
        _line("Left one alpha", 50, 100, 250, 115),
        _line("Left two beta", 50, 130, 250, 145),
        _line("Right one gamma", 320, 100, 550, 115),
        _line("Right two delta", 320, 130, 550, 145),
        _line("FOOTER", 50, 750, 550, 765),
    ]

    ordered = layout_lines(lines, 600, 800)

    assert [line.text for line in ordered] == [
        "HEADER",
        "Left one alpha",
        "Left two beta",
        "Right one gamma",
        "Right two delta",
        "FOOTER",
    ]
    assert ordered[0].role == "header"
    assert ordered[-1].role == "footer"
    assert ordered[1].column == 0
    assert ordered[3].column == 1


def test_layout_orders_table_rows_across_columns():
    lines = [
        _line("Name", 50, 100, 120, 115),
        _line("Amount", 250, 100, 330, 115),
        _line("Term", 450, 100, 520, 115),
        _line("Alice", 50, 130, 100, 145),
        _line("100", 250, 130, 300, 145),
        _line("30 days", 450, 130, 520, 145),
    ]

    ordered = layout_lines(lines, 600, 400)
    text = reconstruct_page_text(ordered)

    assert text.splitlines()[0] == "Name | Amount | Term"
    assert "Alice | 100 | 30 days" in text


def test_reconstruct_page_text_dehyphenates_and_preserves_clauses():
    lines = [
        _line("The Supplier shall indem-", 50, 100, 350, 115),
        _line("nify the Customer.", 50, 130, 250, 145),
        _line("2. Payment Terms", 50, 180, 250, 195),
        _line("Payment is due in 90 days.", 50, 210, 350, 225),
    ]

    text = reconstruct_page_text(layout_lines(lines, 600, 400))

    assert "indemnify" in text
    assert "indem- nify" not in text
    assert "\n\n2. Payment Terms" in text


def test_reconstruct_page_text_spans_align_with_reconstructed_text():
    lines = [
        _line("The Supplier shall indem-", 50, 100, 350, 115, confidence=0.9),
        _line("nify the Customer.", 50, 130, 250, 145, confidence=0.4),
        _line("2. Payment Terms", 50, 180, 250, 195, confidence=0.8),
        _line("Payment is due in 90 days.", 50, 210, 350, 225, confidence=0.7),
    ]

    text, spans = reconstruct_page_text_with_spans(layout_lines(lines, 600, 400))

    assert text == reconstruct_page_text(layout_lines(lines, 600, 400))
    assert [span.confidence for span in spans] == [0.9, 0.4, 0.8, 0.7]
    for span in spans:
        assert text[span.start_offset : span.end_offset] == span.text
    assert spans[1].start_offset == text.index("nify the Customer.")


def test_page_quality_flags_low_confidence_lines():
    quality = page_quality(
        [
            _line("uncertain words", 0, 0, 100, 10, confidence=0.4),
            _line("clear words", 0, 20, 100, 30, confidence=0.95),
        ]
    )

    assert quality.confidence < 0.75
    assert quality.low_confidence_ratio == 0.5
    assert len(quality.low_confidence_lines) == 1
    assert quality.warnings


def test_native_ocr_merge_prefers_clean_native_and_replaces_broken_native():
    clean = select_page_text(
        "1. Indemnity\nThe Supplier shall indemnify the Customer.",
        "1. Indemnity\nThe Supplier shall indemnify the Customer.",
        0.99,
    )
    assert clean.source == "native"

    broken = select_page_text(
        "(cid:12) (cid:44) (cid:91) broken encoding",
        "1. Payment Terms\nPayment is due within ninety days.",
        0.93,
    )
    assert broken.source == "ocr"
    assert "Payment" in broken.text
    assert native_text_quality("(cid:12) (cid:44)") < 0.5


def test_scanned_document_persists_page_provenance_and_quality_warnings(
    client, monkeypatch
):
    monkeypatch.setattr(ocr_module, "ocr_available", lambda: True)

    low_quality = page_quality(
        [_line("uncertain scanned words", 0, 0, 200, 10, confidence=0.3)]
    )
    good_quality = page_quality(
        [_line("clear scanned words", 0, 0, 200, 10, confidence=0.95)]
    )

    def fake_ocr(data, pages, *, dpi=200):
        return {
            1: ocr_module.OcrPageText(
                "1. Indemnity\nThe Supplier shall indemnify the Customer.",
                quality=low_quality,
                preprocess_warnings=("page_preprocess_failed",),
            ),
            3: ocr_module.OcrPageText(
                "3. Payment Terms\nPayment is due within ninety days.",
                quality=good_quality,
            ),
        }

    monkeypatch.setattr(ocr_module, "ocr_pdf_pages", fake_ocr)

    created = client.post(
        "/api/documents",
        files={
            "file": (
                "scan.pdf",
                multi_page_pdf([[""], [""], [""]]),
                "application/pdf",
            )
        },
    )
    assert created.status_code == 201, created.text
    detail = client.get(f"/api/documents/{created.json()['id']}").json()

    pages = {page["page_number"]: page for page in detail["pages"]}
    assert sorted(pages) == [1, 2, 3]
    assert pages[1]["source"] == "ocr"
    assert pages[1]["ocr_confidence"] == 0.3
    assert pages[2]["source"] == "empty"
    assert pages[3]["source"] == "ocr"
    assert detail["quality_warnings"]
    assert detail["ocr_quality"]["confidence"] < 0.65
