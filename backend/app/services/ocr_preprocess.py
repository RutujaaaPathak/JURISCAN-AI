"""OpenCV page preparation for scanned OCR.

The routines here are deliberately conservative: they improve low-contrast,
noisy or slightly skewed scans, but fall back to the original rendered page if
OpenCV cannot decode it or if enhancement would destroy most of the content.
They never change the source page number; rotation is only used to make the
bitmap upright before recognition.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(slots=True, frozen=True)
class PreparedPage:
    image: bytes
    width: int
    height: int
    rotation: int
    skew_angle: float
    steps: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def _decode(image: bytes) -> np.ndarray | None:
    import cv2
    import numpy as np

    buffer = np.frombuffer(image, dtype=np.uint8)
    decoded = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return decoded


def _encode(image: np.ndarray) -> bytes:
    import cv2

    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("The prepared page image could not be encoded.")
    return buffer.tobytes()


def _to_gray(image: np.ndarray) -> np.ndarray:
    import cv2

    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _text_mask(gray: np.ndarray) -> np.ndarray:
    import cv2

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, mask = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    return mask


def _trim_borders(gray: np.ndarray) -> tuple[np.ndarray, bool]:
    """Crop dark scanner borders while keeping the page's white margins.

    Cropping to the text bounding box would remove the margins that layout
    analysis uses to distinguish headers and footers from body text. Only
    near-solid dark bands at the page edges are removed here.
    """

    import numpy as np

    height, width = gray.shape[:2]
    if height < 4 or width < 4:
        return gray, False

    dark = gray < 128
    max_vertical = max(1, int(height * 0.10))
    max_horizontal = max(1, int(width * 0.10))

    top = 0
    while top < max_vertical and dark[top].mean() >= 0.5:
        top += 1
    bottom = height
    while bottom > height - max_vertical and dark[bottom - 1].mean() >= 0.5:
        bottom -= 1
    left = 0
    while left < max_horizontal and dark[:, left].mean() >= 0.5:
        left += 1
    right = width
    while right > width - max_horizontal and dark[:, right - 1].mean() >= 0.5:
        right -= 1

    if top == 0 and bottom == height and left == 0 and right == width:
        return gray, False

    pad = max(4, min(width, height) // 200)
    top = max(0, top - pad)
    bottom = min(height, bottom + pad)
    left = max(0, left - pad)
    right = min(width, right + pad)
    if bottom - top < height * 0.5 or right - left < width * 0.5:
        return gray, False
    return gray[top:bottom, left:right], True


def _horizontal_text_score(gray: np.ndarray) -> float:
    """Higher when dark pixels form wide horizontal lines rather than columns."""

    import cv2

    mask = _text_mask(gray)
    if int(mask.sum()) < 255 * 20:
        return 0.0
    kernel_width = max(15, gray.shape[1] // 30)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1))
    joined = cv2.dilate(mask, kernel, iterations=1)
    contours, _ = cv2.findContours(
        joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    page_width = max(1, gray.shape[1])
    page_height = max(1, gray.shape[0])
    min_height = max(7.0, page_height * 0.008)
    min_width = max(20.0, page_width * 0.05)
    total_width = 0.0
    for contour in contours:
        _x, _y, width, height = cv2.boundingRect(contour)
        if height < min_height or width < min_width:
            continue
        if width / max(1, height) < 2.0:
            continue
        total_width += width
    return total_width / page_width


def detect_rotation(gray: np.ndarray) -> int:
    """Return ``90`` when the page is sideways, otherwise ``0``.

    A 180-degree page is intentionally left alone: RapidOCR's bundled angle
    classifier corrects upside-down text per line, and rotating a page twice
    would only add another resampling step. A 270-degree page is rotated by 90
    degrees here and then corrected by the same classifier.
    """

    import cv2

    upright = _horizontal_text_score(gray)
    sideways = _horizontal_text_score(cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE))
    if sideways > max(0.30, upright * 1.5):
        return 90
    return 0


def _rotate(gray: np.ndarray, degrees: float) -> np.ndarray:
    import cv2

    height, width = gray.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, degrees, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_width = int((height * sin) + (width * cos))
    new_height = int((height * cos) + (width * sin))
    matrix[0, 2] += (new_width / 2.0) - center[0]
    matrix[1, 2] += (new_height / 2.0) - center[1]
    return cv2.warpAffine(
        gray,
        matrix,
        (new_width, new_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def estimate_skew(gray: np.ndarray) -> float:
    """Estimate the dominant text-line angle in degrees (``-15..15``)."""

    import cv2

    mask = _text_mask(gray)
    if int(mask.sum()) < 255 * 20:
        return 0.0

    height, width = gray.shape[:2]
    kernel_width = max(9, min(61, width // 60))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1))
    joined = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(
        joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    angles: list[tuple[float, float]] = []
    for contour in contours:
        rect = cv2.minAreaRect(contour)
        (rect_width, rect_height) = rect[1]
        if min(rect_width, rect_height) < 4:
            continue
        if max(rect_width, rect_height) < width * 0.08:
            continue
        angle = float(rect[2])
        if angle < -45:
            angle += 90
        elif angle > 45:
            angle -= 90
        if abs(angle) <= 15:
            angles.append((angle, max(rect_width, rect_height)))

    if not angles:
        return 0.0
    total_weight = sum(weight for _, weight in angles)
    if total_weight <= 0:
        return 0.0
    return sum(angle * weight for angle, weight in angles) / total_weight


def _deskew(gray: np.ndarray, angle: float) -> tuple[np.ndarray, float]:
    if abs(angle) < 0.2 or abs(angle) > 15:
        return gray, 0.0
    # ``minAreaRect`` reports the line's angle relative to horizontal. Rotating
    # by the negative value makes that line horizontal again.
    return _rotate(gray, -angle), angle


def _enhance(gray: np.ndarray) -> tuple[np.ndarray, tuple[str, ...]]:
    import cv2

    steps: list[str] = []
    denoised = cv2.medianBlur(gray, 3)
    steps.append("denoise")

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(denoised)
    steps.append("contrast")

    block_size = max(15, (min(contrasted.shape[:2]) // 45) | 1)
    binary = cv2.adaptiveThreshold(
        contrasted,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        15,
    )
    steps.append("adaptive_threshold")

    # A threshold result that is almost entirely black or white usually means a
    # photograph or a heavily shaded scan. Keep the contrast-enhanced grayscale
    # instead of destroying the page.
    white_ratio = float((binary > 0).mean())
    if white_ratio < 0.08 or white_ratio > 0.995:
        return contrasted, tuple(steps[:-1] + ["contrast_fallback"])
    return binary, tuple(steps)


def prepare_page(image: bytes) -> PreparedPage:
    """Prepare one rendered page for OCR and return PNG bytes plus metadata."""

    if not settings.ocr_preprocess_enabled:
        return PreparedPage(image=image, width=0, height=0, rotation=0, skew_angle=0.0, steps=())

    try:
        decoded = _decode(image)
    except Exception:
        decoded = None
    if decoded is None:
        return PreparedPage(
            image=image,
            width=0,
            height=0,
            rotation=0,
            skew_angle=0.0,
            steps=(),
            warnings=("page_image_decode_failed",),
        )

    try:
        gray = _to_gray(decoded)
        steps: list[str] = []
        warnings: list[str] = []

        # Detect orientation before cropping to the text bounding box. A tight
        # crop removes the page margins that make the horizontal/vertical
        # projection comparison reliable, and can make upright text look
        # sideways (observed with full-width legal lines).
        rotation = 0
        if settings.ocr_rotation_detection_enabled:
            rotation = detect_rotation(gray)

        gray, trimmed = _trim_borders(gray)
        if trimmed:
            steps.append("border_cleanup")

        if rotation:
            import cv2

            gray = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
            steps.append("rotation_90")

        skew_angle = 0.0
        if settings.ocr_deskew_enabled:
            skew_angle = estimate_skew(gray)
            gray, applied = _deskew(gray, skew_angle)
            if applied:
                steps.append("deskew")
            else:
                skew_angle = 0.0

        prepared, enhancement_steps = _enhance(gray)
        steps.extend(enhancement_steps)

        height, width = prepared.shape[:2]
        return PreparedPage(
            image=_encode(prepared),
            width=width,
            height=height,
            rotation=rotation,
            skew_angle=skew_angle,
            steps=tuple(steps),
            warnings=tuple(warnings),
        )
    except Exception:
        return PreparedPage(
            image=image,
            width=0,
            height=0,
            rotation=0,
            skew_angle=0.0,
            steps=(),
            warnings=("page_preprocess_failed",),
        )


__all__ = [
    "PreparedPage",
    "detect_rotation",
    "estimate_skew",
    "prepare_page",
]
