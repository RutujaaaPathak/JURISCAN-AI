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

from collections.abc import Iterator
from concurrent.futures import (
    CancelledError,
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
from dataclasses import replace
import threading
import time

from app.config import settings
from app.services.ocr_layout import (
    OcrLine,
    OcrLineSpan,
    PageQuality,
    layout_lines,
    page_quality,
    parse_rapidocr_result,
    reconstruct_page_text_with_spans,
)
from app.services.ocr_preprocess import prepare_page

_engine_lock = threading.Lock()
_engine_local = threading.local()

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


class OcrUnavailable(RuntimeError):
    """OCR cannot run because the optional engine/dependencies are missing."""


class OcrError(RuntimeError):
    """The OCR engine was available but failed to process a page."""


class OcrTimeout(OcrError):
    """OCR exceeded its configured deadline before finishing."""


class OcrPageText(str):
    """OCR text that remains string-compatible but carries quality metadata."""

    def __new__(
        cls,
        text: str,
        *,
        quality: PageQuality | None = None,
        lines: tuple[OcrLine, ...] = (),
        line_spans: tuple[OcrLineSpan, ...] = (),
        rotation: int = 0,
        skew_angle: float = 0.0,
        preprocess_steps: tuple[str, ...] = (),
        preprocess_warnings: tuple[str, ...] = (),
    ):
        instance = super().__new__(cls, text)
        instance.quality = quality
        instance.lines = lines
        instance.line_spans = line_spans
        instance.rotation = rotation
        instance.skew_angle = skew_angle
        instance.preprocess_steps = preprocess_steps
        instance.preprocess_warnings = preprocess_warnings
        return instance


def ocr_available() -> bool:
    """Return True when both the renderer and the OCR engine can be imported."""

    try:
        import pymupdf  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
    except Exception:
        return False
    return True


def _get_engine():
    """Return a lazily-created RapidOCR engine owned by the current thread.

    Each OCR worker gets its own engine. That keeps the default single-worker
    path unchanged while avoiding shared mutable engine state if an operator
    deliberately raises ``ocr_max_concurrent_inferences``.
    """

    engine = getattr(_engine_local, "engine", None)
    if engine is not None:
        return engine

    with _engine_lock:
        engine = getattr(_engine_local, "engine", None)
        if engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except Exception as exc:  # pragma: no cover - import guarded
                raise OcrUnavailable(
                    "The OCR engine (rapidocr-onnxruntime) is not installed."
                ) from exc
            try:
                engine = RapidOCR()
            except Exception as exc:  # pragma: no cover - engine init failure
                raise OcrUnavailable(
                    "The OCR engine could not be initialised."
                ) from exc
            _engine_local.engine = engine
    return engine


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=max(1, settings.ocr_max_concurrent_inferences),
                    thread_name_prefix="juriscan-ocr",
                )
    return _executor


def _abandon_executor() -> None:
    """Retire the current executor without waiting for a stuck inference.

    Python cannot forcibly stop a running native ONNX/RapidOCR call. Retiring
    the executor at least ensures later OCR jobs are not permanently queued
    behind a timed-out page; the abandoned thread finishes in the background.
    """

    global _executor
    with _executor_lock:
        executor = _executor
        _executor = None
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)


def shutdown_ocr_executor(*, wait: bool = False) -> None:
    """Release the module-level OCR executor (used at shutdown and in tests)."""

    global _executor
    with _executor_lock:
        executor = _executor
        _executor = None
    if executor is not None:
        executor.shutdown(wait=wait, cancel_futures=True)


def _iter_page_batches(
    data: bytes,
    page_numbers: list[int],
    dpi: int,
    batch_size: int,
) -> Iterator[list[tuple[int, bytes]]]:
    """Yield bounded batches of rendered page images, then release them."""

    try:
        import pymupdf
    except Exception as exc:  # pragma: no cover - import guarded
        raise OcrUnavailable("The PDF renderer (pymupdf) is not installed.") from exc

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise OcrError("The PDF could not be opened for OCR rendering.") from exc

    try:
        batch: list[tuple[int, bytes]] = []
        for number in page_numbers:
            try:
                page = document[number - 1]
            except Exception as exc:
                raise OcrError(f"PDF page {number} could not be rendered.") from exc

            pixmap = None
            try:
                pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB)
                image = pixmap.tobytes("png")
            except Exception as exc:
                raise OcrError(f"PDF page {number} could not be rendered.") from exc
            finally:
                del pixmap

            batch.append((number, image))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
    finally:
        document.close()


def _is_upside_down(engine, image: bytes, result) -> bool:
    """Ask RapidOCR's angle classifier whether most text lines are inverted."""

    raw_boxes = [
        entry[0]
        for entry in (result or [])
        if entry and len(entry) >= 2 and entry[0] is not None
    ]
    if not raw_boxes:
        return False
    try:
        import numpy as np

        boxes = [np.asarray(box, dtype=np.float32) for box in raw_boxes]
        loaded = engine.load_img(image)
        crops = engine.get_crop_img_list(loaded, boxes)
        if not crops:
            return False
        _rotated, labels, _elapsed = engine.text_cls(crops)
    except Exception:
        return False
    if not labels:
        return False
    votes = sum(
        1
        for label, score in labels
        if "180" in str(label) and float(score) >= 0.9
    )
    return votes > len(labels) / 2.0


def _recognise(image: bytes, page_number: int) -> OcrPageText:
    prepared = prepare_page(image)
    engine = _get_engine()
    try:
        result, _elapsed = engine(prepared.image)
    except Exception as exc:
        raise OcrError(f"OCR failed while reading page {page_number}.") from exc

    if (
        settings.ocr_rotation_detection_enabled
        and _is_upside_down(engine, prepared.image, result)
    ):
        try:
            import cv2

            upright = cv2.rotate(
                engine.load_img(prepared.image), cv2.ROTATE_180
            )
            ok, encoded = cv2.imencode(".png", upright)
            if ok:
                rotated_result, _elapsed = engine(encoded.tobytes())
                if rotated_result:
                    result = rotated_result
                    prepared = replace(
                        prepared,
                        image=encoded.tobytes(),
                        rotation=(prepared.rotation + 180) % 360,
                        steps=prepared.steps + ("rotation_180",),
                    )
        except Exception:
            pass

    parsed = parse_rapidocr_result(result)
    ordered = layout_lines(parsed, prepared.width, prepared.height)
    text, line_spans = reconstruct_page_text_with_spans(ordered)
    quality = page_quality(ordered)
    return OcrPageText(
        text,
        quality=quality,
        lines=tuple(ordered),
        line_spans=line_spans,
        rotation=prepared.rotation,
        skew_angle=prepared.skew_angle,
        preprocess_steps=prepared.steps,
        preprocess_warnings=prepared.warnings,
    )


def _run_recognition(
    image: bytes, page_number: int, deadline: float
) -> OcrPageText:
    """Run one page inference without allowing it to block forever."""

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OcrTimeout(
                f"OCR timed out while reading page {page_number}."
            )

        try:
            executor = _get_executor()
            future = executor.submit(_recognise, image, page_number)
        except RuntimeError:
            # Another timed-out call retired this executor between lookup and
            # submission. Retry on the freshly-created replacement.
            _abandon_executor()
            continue

        try:
            return future.result(timeout=remaining)
        except FutureTimeoutError as exc:
            future.cancel()
            _abandon_executor()
            raise OcrTimeout(
                f"OCR timed out while reading page {page_number}."
            ) from exc
        except CancelledError:
            if deadline - time.monotonic() <= 0:
                raise OcrTimeout(
                    f"OCR timed out while reading page {page_number}."
                ) from None
            continue
        except (OcrUnavailable, OcrError):
            raise
        except Exception as exc:
            raise OcrError(
                f"OCR failed while reading page {page_number}."
            ) from exc


def ocr_pdf_pages(
    data: bytes,
    page_numbers: list[int],
    *,
    dpi: int = 200,
    timeout_seconds: float | None = None,
    batch_size: int | None = None,
) -> dict[int, OcrPageText]:
    """OCR the given 1-based PDF pages and return ``{page_number: text}``.

    Rendering is bounded by ``batch_size`` (default:
    ``settings.ocr_page_batch_size``), so at most one batch of page images is
    held in memory. The whole call is bounded by ``timeout_seconds`` (default:
    ``settings.ocr_timeout_seconds``).

    Raises :class:`OcrUnavailable` when the engine/deps are missing,
    :class:`OcrTimeout` when the deadline expires, and :class:`OcrError` when a
    page cannot be rendered or recognised. Pages with no detected text map to an
    empty string.
    """

    requested = sorted({number for number in page_numbers if number >= 1})
    if not requested:
        return {}

    effective_batch = (
        settings.ocr_page_batch_size if batch_size is None else max(1, batch_size)
    )
    effective_timeout = (
        settings.ocr_timeout_seconds
        if timeout_seconds is None
        else timeout_seconds
    )
    if effective_timeout <= 0:
        raise OcrTimeout("OCR timed out before it could start.")

    deadline = time.monotonic() + effective_timeout
    readings: dict[int, OcrPageText] = {}
    batches = _iter_page_batches(data, requested, dpi, effective_batch)
    try:
        for batch in batches:
            for number, image in batch:
                readings[number] = _run_recognition(image, number, deadline)
                del image
            batch.clear()
    finally:
        batches.close()
    return readings


__all__ = [
    "OcrError",
    "OcrPageText",
    "OcrTimeout",
    "OcrUnavailable",
    "ocr_available",
    "ocr_pdf_pages",
    "shutdown_ocr_executor",
]
