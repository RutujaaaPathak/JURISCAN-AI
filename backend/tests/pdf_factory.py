"""Small helpers to build valid PDFs for extraction tests.

The project intentionally does not depend on a PDF *writer* library, so these
helpers assemble a minimal PDF by hand and use pypdf (already a dependency) only
to concatenate pages into multi-page documents.
"""

from __future__ import annotations

import io


def single_page_pdf(lines: list[str]) -> bytes:
    def esc(value: str) -> str:
        return value.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content = "BT\n/F1 11 Tf\n14 TL\n72 720 Td\n"
    content += "".join(f"({esc(line)}) Tj\nT*\n" for line in lines)
    content += "ET"
    body = content.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(body)).encode() + b" >>\nstream\n" + body + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF"
    ).encode()
    return out


def multi_page_pdf(pages: list[list[str]], *, encrypt: bool = False) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for lines in pages:
        writer.append(io.BytesIO(single_page_pdf(lines)))
    if encrypt:
        writer.encrypt(user_password="secret", owner_password="secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def image_only_pdf(lines: list[str], *, dpi: int = 200) -> bytes:
    """Rasterise a text page into an image-only PDF (no extractable text).

    Used to emulate a scanned document: the page contains a picture of words but
    no text layer, so extraction must fall back to OCR.
    """
    import pymupdf

    source = pymupdf.open(stream=single_page_pdf(lines), filetype="pdf")
    try:
        pixmap = source[0].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB)
        image = pixmap.tobytes("png")
    finally:
        source.close()

    document = pymupdf.open()
    try:
        page = document.new_page(width=612, height=792)
        page.insert_image(pymupdf.Rect(0, 0, 612, 792), stream=image)
        return document.tobytes()
    finally:
        document.close()


def mixed_pdf(spec: list[tuple[str, list[str]]], *, dpi: int = 200) -> bytes:
    """Build a PDF mixing native-text pages ("text") and scanned pages ("scan")."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for kind, lines in spec:
        if kind == "scan":
            writer.append(io.BytesIO(image_only_pdf(lines, dpi=dpi)))
        else:
            writer.append(io.BytesIO(single_page_pdf(lines)))
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
