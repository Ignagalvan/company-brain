"""
Tests for pdf_service.extract_text.

Three cases:
- valid PDF with selectable text  → returns the text
- corrupted / non-PDF bytes       → returns None (does NOT raise)
- valid PDF with no text content  → returns None
"""

import io
import tempfile
from pathlib import Path

from src.services.pdf_service import extract_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf_with_text(text: str) -> bytes:
    """Build a minimal valid PDF containing one page with selectable text."""
    stream_content = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET\n".encode("latin-1")

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        4: (
            b"<< /Length " + str(len(stream_content)).encode() + b" >>\n"
            b"stream\n" + stream_content + b"endstream"
        ),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }

    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}

    for num, content in objects.items():
        offsets[num] = buf.tell()
        buf.write(f"{num} 0 obj\n".encode())
        buf.write(content)
        buf.write(b"\nendobj\n")

    xref_offset = buf.tell()
    count = len(objects) + 1  # includes free entry 0
    buf.write(f"xref\n0 {count}\n".encode())
    buf.write(b"0000000000 65535 f \n")
    for i in range(1, count):
        buf.write(f"{offsets[i]:010d} 00000 n \n".encode())

    buf.write(b"trailer\n")
    buf.write(f"<< /Size {count} /Root 1 0 R >>\n".encode())
    buf.write(b"startxref\n")
    buf.write(f"{xref_offset}\n".encode())
    buf.write(b"%%EOF\n")

    return buf.getvalue()


def _make_pdf_without_text() -> bytes:
    """Build a valid PDF with a single blank page (no text content)."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _tmp_pdf(content: bytes) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_extract_text_valid_pdf_returns_text():
    path = _tmp_pdf(_make_pdf_with_text("Hello World"))
    try:
        result = extract_text(path)
        assert result is not None
        assert "Hello" in result
    finally:
        path.unlink()


def test_extract_text_corrupted_pdf_returns_none():
    path = _tmp_pdf(b"this is not a valid pdf file")
    try:
        result = extract_text(path)
        assert result is None
    finally:
        path.unlink()


def test_extract_text_pdf_without_selectable_text_returns_none():
    path = _tmp_pdf(_make_pdf_without_text())
    try:
        result = extract_text(path)
        assert result is None
    finally:
        path.unlink()
