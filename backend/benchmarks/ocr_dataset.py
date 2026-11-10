"""Synthetic legal-document corpus for OCR regression benchmarks.

All wording here is purpose-written for testing. It is not copied from a real
contract and contains no personal data. The corpus deliberately covers the
failure modes the OCR pipeline is expected to handle: clean scans, blur/noise,
sideways rotation, skew, multi-column reading order, tables, stamps, mixed
native/scanned PDFs and a longer document.

The generated PDFs are deterministic for a fixed PyMuPDF/OpenCV version. Ground
truth is the text a perfect extractor should return for each page; layout order
is part of that truth, not just the words on the page.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Literal

BENCHMARK_VERSION = "1.0"
DISCLAIMER = (
    "Synthetic legal text created solely for OCR regression testing. It is not "
    "legal advice, contains no client data, and must not be treated as a "
    "verified legal reference."
)
DEFAULT_DPI = 200
_FONT_SIZE = 13
_LEADING = 20
_COLUMN_FONT_SIZE = 11
_COLUMN_LEADING = 18
_TABLE_FONT_SIZE = 11
_TABLE_LEADING = 22


@dataclass(frozen=True, slots=True)
class PageSpec:
    """One page in a benchmark document.

    Exactly one of ``lines``, ``columns`` or ``table_rows`` should be populated.
    ``kind`` is ``"scan"`` (rasterised, no text layer) or ``"native"`` (PDF text).
    """

    kind: Literal["scan", "native"]
    lines: tuple[str, ...] = ()
    columns: tuple[tuple[str, ...], ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()
    transforms: tuple[str, ...] = ()
    ground_truth: str = ""
    expected_source: str = ""
    page_marker: str | None = None

    def expected_text(self) -> str:
        if self.ground_truth:
            return self.ground_truth
        if self.columns:
            return "\n\n".join("\n".join(column) for column in self.columns)
        if self.table_rows:
            return "\n\n".join(" | ".join(row) for row in self.table_rows)
        return "\n".join(self.lines)


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    category: str
    description: str
    pages: tuple[PageSpec, ...]
    clause_markers: tuple[str, ...] = ()
    expected_risk_codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def expected_sources(self) -> tuple[str, ...]:
        return tuple(
            page.expected_source or ("native" if page.kind == "native" else "ocr")
            for page in self.pages
        )


_PAGE_1 = (
    "MASTER SERVICES AGREEMENT",
    "",
    "1. Definitions and Interpretation",
    "In this Agreement the following definitions apply unless the",
    "context requires otherwise.",
    "",
    "2. Services",
    "2.1 The Supplier shall provide the Services described in each",
    "Statement of Work.",
    "2.2 The Supplier shall perform the Services with reasonable",
    "skill and care.",
    "",
    "3. Payment Terms",
    "The Customer shall pay each undisputed invoice",
    "within ninety (90) days of receipt.",
)

_PAGE_2 = (
    "4. Limitation of Liability",
    "The Supplier shall have unlimited liability",
    "for all direct and indirect losses.",
    "",
    "5. Indemnity",
    "The Supplier shall indemnify and hold harmless the Customer",
    "from all claims without limit.",
    "",
    "6. Term and Renewal",
    "This Agreement shall automatically renew for successive",
    "terms of twelve months.",
    "",
    "7. Restrictive Covenant",
    "The Employee shall not compete with the Employer for six",
    "months after termination.",
)

_PAGE_3 = (
    "8. Confidentiality",
    "The Receiving Party shall keep the Confidential Information",
    "secret and shall not disclose it to any third party.",
    "",
    "9. Governing Law",
    "This Agreement is governed by the laws of England and Wales.",
    "",
    "10. Notices",
    "Notices must be in writing and delivered by hand or",
    "registered post.",
)

_MARKERS_1 = (
    "1. Definitions and Interpretation",
    "2. Services",
    "3. Payment Terms",
)
_MARKERS_2 = (
    "4. Limitation of Liability",
    "5. Indemnity",
    "6. Term and Renewal",
    "7. Restrictive Covenant",
)
_MARKERS_3 = ("8. Confidentiality", "9. Governing Law", "10. Notices")

_RISKS_PAGE_1 = ("EXTENDED_PAYMENT_TERMS",)
_RISKS_PAGE_2 = (
    "UNLIMITED_LIABILITY",
    "UNCAPPED_INDEMNITY",
    "AUTO_RENEWAL",
    "BROAD_NON_COMPETE",
)


def _scan(
    lines: tuple[str, ...],
    *,
    transforms: tuple[str, ...] = (),
    page_marker: str | None = None,
) -> PageSpec:
    return PageSpec(
        kind="scan",
        lines=lines,
        transforms=transforms,
        expected_source="ocr",
        page_marker=page_marker,
    )


def _native(
    lines: tuple[str, ...], *, page_marker: str | None = None
) -> PageSpec:
    return PageSpec(
        kind="native",
        lines=lines,
        expected_source="native",
        page_marker=page_marker,
    )


def _two_column() -> PageSpec:
    left = (
        "4. Limitation of Liability",
        "The Supplier shall have",
        "unlimited liability for all",
        "direct and indirect losses.",
    )
    right = (
        "5. Indemnity",
        "The Supplier shall indemnify",
        "and hold harmless the Customer",
        "from all claims without limit.",
    )
    return PageSpec(
        kind="scan",
        columns=(left, right),
        expected_source="ocr",
        page_marker="4. Limitation of Liability",
    )


def _table() -> PageSpec:
    return PageSpec(
        kind="scan",
        table_rows=(
            ("Party", "Amount", "Term"),
            ("Alice", "100", "30 days"),
            ("Bob", "250", "60 days"),
        ),
        expected_source="ocr",
    )


def benchmark_cases() -> tuple[BenchmarkCase, ...]:
    """Return the full deterministic benchmark corpus."""

    return (
        BenchmarkCase(
            case_id="clean_contract",
            category="clean_scanned_contract",
            description="Two-page clean scan with numbered clauses and risk wording.",
            pages=(
                _scan(_PAGE_1, page_marker=_MARKERS_1[0]),
                _scan(_PAGE_2, page_marker=_MARKERS_2[0]),
            ),
            clause_markers=_MARKERS_1 + _MARKERS_2,
            expected_risk_codes=_RISKS_PAGE_1 + _RISKS_PAGE_2,
            tags=("scan", "multi-page", "clauses"),
        ),
        BenchmarkCase(
            case_id="blurry_page",
            category="blurry_scan",
            description="Low-quality blurred scan with sensor noise.",
            pages=(
                _scan(
                    _PAGE_2,
                    transforms=("blur", "noise"),
                    page_marker=_MARKERS_2[0],
                ),
            ),
            clause_markers=_MARKERS_2,
            expected_risk_codes=_RISKS_PAGE_2,
            tags=("scan", "blur", "noise", "low-quality"),
        ),
        BenchmarkCase(
            case_id="rotated_page",
            category="rotated_scan",
            description="Sideways scan that must be rotated upright before OCR.",
            pages=(
                _scan(
                    _PAGE_2,
                    transforms=("rotate90",),
                    page_marker=_MARKERS_2[0],
                ),
            ),
            clause_markers=_MARKERS_2,
            expected_risk_codes=_RISKS_PAGE_2,
            tags=("scan", "rotation", "orientation"),
        ),
        BenchmarkCase(
            case_id="skewed_page",
            category="skewed_scan",
            description="Four-degree skewed scan that requires deskewing.",
            pages=(
                _scan(
                    _PAGE_2,
                    transforms=("skew",),
                    page_marker=_MARKERS_2[0],
                ),
            ),
            clause_markers=_MARKERS_2,
            expected_risk_codes=_RISKS_PAGE_2,
            tags=("scan", "skew", "deskew"),
        ),
        BenchmarkCase(
            case_id="two_column_page",
            category="multi_column_layout",
            description="Two-column clause layout with a vertical gutter.",
            pages=(_two_column(),),
            clause_markers=("4. Limitation of Liability", "5. Indemnity"),
            expected_risk_codes=(
                "UNLIMITED_LIABILITY",
                "UNCAPPED_INDEMNITY",
            ),
            tags=("scan", "layout", "columns", "reading-order"),
        ),
        BenchmarkCase(
            case_id="table_page",
            category="table_layout",
            description="Schedule-style table whose rows must not be interleaved.",
            pages=(_table(),),
            tags=("scan", "layout", "table"),
        ),
        BenchmarkCase(
            case_id="stamped_page",
            category="stamped_scan",
            description="Clean page with a red approval stamp over the margin.",
            pages=(
                _scan(
                    _PAGE_1,
                    transforms=("stamp",),
                    page_marker=_MARKERS_1[0],
                ),
            ),
            clause_markers=_MARKERS_1,
            expected_risk_codes=_RISKS_PAGE_1,
            tags=("scan", "stamp", "overlay"),
        ),
        BenchmarkCase(
            case_id="mixed_native_scan",
            category="mixed_native_and_scanned",
            description="Native-text page followed by an image-only scanned page.",
            pages=(
                _native(_PAGE_1, page_marker=_MARKERS_1[0]),
                _scan(_PAGE_2, page_marker=_MARKERS_2[0]),
            ),
            clause_markers=_MARKERS_1 + _MARKERS_2,
            expected_risk_codes=_RISKS_PAGE_1 + _RISKS_PAGE_2,
            tags=("mixed", "native", "scan", "merge"),
        ),
        BenchmarkCase(
            case_id="long_contract",
            category="long_document",
            description="Three-page scan exercising repeated page assembly and offsets.",
            pages=(
                _scan(_PAGE_1, page_marker=_MARKERS_1[0]),
                _scan(_PAGE_2, page_marker=_MARKERS_2[0]),
                _scan(_PAGE_3, page_marker=_MARKERS_3[0]),
            ),
            clause_markers=_MARKERS_1 + _MARKERS_2 + _MARKERS_3,
            expected_risk_codes=_RISKS_PAGE_1 + _RISKS_PAGE_2,
            tags=("scan", "long", "multi-page", "offsets"),
        ),
    )


def _render_scan_png(spec: PageSpec) -> tuple[bytes, int, int]:
    """Render a page to PNG, then apply the requested scan transforms."""

    import cv2
    import numpy as np
    import pymupdf

    source = pymupdf.open()
    try:
        page = source.new_page(width=612, height=792)
        if spec.columns:
            x_positions = (52.0, 318.0)
            for x, column in zip(x_positions, spec.columns):
                y = 90.0
                for line in column:
                    if line:
                        page.insert_text(
                            (x, y),
                            line,
                            fontsize=_COLUMN_FONT_SIZE,
                            fontname="helv",
                            color=(0, 0, 0),
                        )
                    y += _COLUMN_LEADING
        elif spec.table_rows:
            x_positions = (72.0, 260.0, 430.0)
            y = 110.0
            for row in spec.table_rows:
                for x, cell in zip(x_positions, row):
                    if cell:
                        page.insert_text(
                            (x, y),
                            cell,
                            fontsize=_TABLE_FONT_SIZE,
                            fontname="helv",
                            color=(0, 0, 0),
                        )
                y += _TABLE_LEADING
        else:
            y = 90.0
            for line in spec.lines:
                if line:
                    page.insert_text(
                        (72, y),
                        line,
                        fontsize=_FONT_SIZE,
                        fontname="helv",
                        color=(0, 0, 0),
                    )
                y += _LEADING
        pixmap = page.get_pixmap(dpi=DEFAULT_DPI, colorspace=pymupdf.csRGB)
        png = pixmap.tobytes("png")
    finally:
        source.close()

    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("The benchmark page could not be rasterised.")

    for transform in spec.transforms:
        if transform == "blur":
            image = cv2.GaussianBlur(image, (5, 5), 0)
        elif transform == "noise":
            noise = np.random.default_rng(20261105).normal(0, 12, image.shape)
            image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(
                np.uint8
            )
        elif transform == "rotate90":
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        elif transform == "skew":
            height, width = image.shape[:2]
            matrix = cv2.getRotationMatrix2D(
                (width / 2.0, height / 2.0), 4.0, 1.0
            )
            image = cv2.warpAffine(
                image,
                matrix,
                (width, height),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255),
            )
        elif transform == "stamp":
            overlay = image.copy()
            height, width = image.shape[:2]
            top_left = (int(width * 0.58), int(height * 0.72))
            bottom_right = (int(width * 0.94), int(height * 0.84))
            cv2.rectangle(overlay, top_left, bottom_right, (0, 0, 180), -1)
            cv2.putText(
                overlay,
                "APPROVED",
                (top_left[0] + 18, top_left[1] + 48),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.4,
                (255, 255, 255),
                3,
                cv2.LINE_AA,
            )
            image = cv2.addWeighted(overlay, 0.30, image, 0.70, 0)
        else:  # pragma: no cover - corpus only uses known transforms
            raise ValueError(f"Unknown benchmark transform: {transform}")

    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("The benchmark page could not be encoded.")
    return encoded.tobytes(), image.shape[1], image.shape[0]


def build_case_pdf(case: BenchmarkCase) -> bytes:
    """Build a valid PDF containing native text and/or scanned image pages."""

    import pymupdf

    document = pymupdf.open()
    try:
        for spec in case.pages:
            if spec.kind == "native":
                page = document.new_page(width=612, height=792)
                y = 90.0
                for line in spec.lines:
                    if line:
                        page.insert_text(
                            (72, y),
                            line,
                            fontsize=_FONT_SIZE,
                            fontname="helv",
                            color=(0, 0, 0),
                        )
                    y += _LEADING
                continue

            png, pixel_width, pixel_height = _render_scan_png(spec)
            width = pixel_width * 72.0 / DEFAULT_DPI
            height = pixel_height * 72.0 / DEFAULT_DPI
            page = document.new_page(width=width, height=height)
            page.insert_image(pymupdf.Rect(0, 0, width, height), stream=png)
        return document.tobytes()
    finally:
        document.close()


def case_pdf_sha256(case: BenchmarkCase) -> str:
    return hashlib.sha256(build_case_pdf(case)).hexdigest()


def manifest() -> dict:
    """Serialisable dataset manifest for review and reproducibility."""

    return {
        "version": BENCHMARK_VERSION,
        "disclaimer": DISCLAIMER,
        "generation": {
            "renderer": "PyMuPDF",
            "dpi": DEFAULT_DPI,
            "font_size": _FONT_SIZE,
            "leading": _LEADING,
            "transforms": ["blur", "noise", "rotate90", "skew", "stamp"],
        },
        "cases": [
            {
                "id": case.case_id,
                "category": case.category,
                "description": case.description,
                "tags": list(case.tags),
                "page_count": len(case.pages),
                "expected_sources": list(case.expected_sources()),
                "clause_markers": list(case.clause_markers),
                "expected_risk_codes": list(case.expected_risk_codes),
                "pages": [
                    {
                        "kind": page.kind,
                        "layout": (
                            "columns"
                            if page.columns
                            else "table"
                            if page.table_rows
                            else "single"
                        ),
                        "transforms": list(page.transforms),
                        "page_marker": page.page_marker,
                        "ground_truth": page.expected_text(),
                    }
                    for page in case.pages
                ],
            }
            for case in benchmark_cases()
        ],
    }


__all__ = [
    "BENCHMARK_VERSION",
    "BenchmarkCase",
    "DEFAULT_DPI",
    "DISCLAIMER",
    "PageSpec",
    "benchmark_cases",
    "build_case_pdf",
    "case_pdf_sha256",
    "manifest",
]
