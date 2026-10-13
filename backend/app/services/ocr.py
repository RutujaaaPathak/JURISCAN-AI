"""Optional OCR for scanned / image-only PDF pages.

Engine
------
- Rendering: **PyMuPDF** (``pymupdf``) rasterises individual PDF pages. It is a
  self-contained wheel with no system dependencies.
- Recognition: **RapidOCR** (``rapidocr-onnxruntime``) runs PP-OCR models via
  ONNX Runtime. The detection/recognition/classification models ship inside the
  wheel, so no downloads or external binaries (Tesseract/Poppler) are required.

Installation
------------
::

    pip install "rapidocr-onnxruntime==1.2.*" "pymupdf==1.28.*"

Both packages are optional. Everything here is imported lazily so the rest of
the application keeps working when they are absent: callers must first check
:func:`ocr_available` (or handle :class:`OcrUnavailable`).

This module never claims success for a page it could not read. A page that
yields no text simply maps to an empty string.
"""

from __future__ import annotations

import threading

_engine = None
_engine_lock = threading.Lock()


class OcrUnavailable(RuntimeError):
    """OCR cannot run because the optional engine/dependencies are missing."""


class OcrError(RuntimeError):
    """The OCR engine was available but failed to process a page."""


def ocr_available() -> bool:
    """Return True when both the renderer and the OCR engine can be imported."""

    try:
        import pymupdf  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
    except Exception:
        return False
    return True


def _get_engine():
    """Return a lazily-created, process-wide RapidOCR engine."""

    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                try:
                    from rapidocr_onnxruntime import RapidOCR
                except Exception as exc:  # pragma: no cover - import guarded
                    raise OcrUnavailable(
                        "The OCR engine (rapidocr-onnxruntime) is not installed."
                    ) from exc
                try:
                    _engine = RapidOCR()
                except Exception as exc:  # pragma: no cover - engine init failure
                    raise OcrUnavailable(
                        "The OCR engine could not be initialised."
                    ) from exc
    return _engine


def _render_pages(data: bytes, page_numbers: list[int], dpi: int) -> dict[int, bytes]:
    """Rasterise the requested 1-based PDF pages to PNG bytes."""

    try:
        import pymupdf
    except Exception as exc:  # pragma: no cover - import guarded
        raise OcrUnavailable("The PDF renderer (pymupdf) is not installed.") from exc

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise OcrError("The PDF could not be opened for OCR rendering.") from exc

    images: dict[int, bytes] = {}
    try:
        for number in page_numbers:
            try:
                page = document[number - 1]
            except Exception as exc:
                raise OcrError(f"PDF page {number} could not be rendered.") from exc
            pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB)
            images[number] = pixmap.tobytes("png")
    finally:
        document.close()
    return images


def _recognise(engine, image: bytes, page_number: int) -> str:
    try:
        result, _elapsed = engine(image)
    except Exception as exc:
        raise OcrError(f"OCR failed while reading page {page_number}.") from exc
    if not result:
        return ""
    lines: list[str] = []
    for entry in result:
        if entry and len(entry) >= 2 and entry[1]:
            lines.append(str(entry[1]))
    return "\n".join(lines)


def ocr_pdf_pages(
    data: bytes,
    page_numbers: list[int],
    *,
    dpi: int = 200,
) -> dict[int, str]:
    """OCR the given 1-based PDF pages and return ``{page_number: text}``.

    Raises :class:`OcrUnavailable` when the engine/deps are missing and
    :class:`OcrError` when a page cannot be rendered or recognised. Pages with
    no detected text map to an empty string.
    """

    requested = sorted({number for number in page_numbers if number >= 1})
    if not requested:
        return {}

    engine = _get_engine()
    images = _render_pages(data, requested, dpi)
    return {number: _recognise(engine, image, number) for number, image in images.items()}


__all__ = ["OcrError", "OcrUnavailable", "ocr_available", "ocr_pdf_pages"]
