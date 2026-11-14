"""Tiny dependency-free PDF writer (R13.1).

The oss profile cannot install reportlab/weasyprint (no network). This writes a
minimal but valid multi-page PDF containing wrapped monospaced text — enough for
a readable evidence pack. It is intentionally small: one Type1 font (Courier),
Latin-1 text, fixed line grid.

If a richer renderer is available later it can replace this without changing the
report's content model (``aca.report.build``).
"""

from __future__ import annotations

from pathlib import Path

_PAGE_W, _PAGE_H = 595, 842  # A4 points
_MARGIN = 54
_FONT_SIZE = 10
_LEADING = 13
_MAX_CHARS = 92  # chars per line at Courier 10pt within the margins
_LINES_PER_PAGE = int((_PAGE_H - 2 * _MARGIN) / _LEADING)


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap(lines: list[str]) -> list[str]:
    wrapped: list[str] = []
    for raw in lines:
        raw = raw.rstrip("\n")
        if raw == "":
            wrapped.append("")
            continue
        while len(raw) > _MAX_CHARS:
            cut = raw.rfind(" ", 0, _MAX_CHARS)
            if cut <= 0:
                cut = _MAX_CHARS
            wrapped.append(raw[:cut])
            raw = raw[cut:].lstrip()
        wrapped.append(raw)
    return wrapped


def _paginate(lines: list[str]) -> list[list[str]]:
    wrapped = _wrap(lines)
    return [wrapped[i : i + _LINES_PER_PAGE] for i in range(0, len(wrapped), _LINES_PER_PAGE)] or [[]]


def _content_stream(page_lines: list[str]) -> bytes:
    parts = ["BT", f"/F1 {_FONT_SIZE} Tf", f"{_LEADING} TL", f"{_MARGIN} {_PAGE_H - _MARGIN} Td"]
    for i, line in enumerate(page_lines):
        if i > 0:
            parts.append("T*")
        parts.append(f"({_escape(line)}) Tj")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", "replace")


def write_pdf(text: str, path: str | Path) -> Path:
    """Render ``text`` (newline-separated) to a minimal PDF at ``path``."""
    pages = _paginate(text.split("\n"))

    objects: list[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)  # 1-based object number

    font_num = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_obj_nums: list[int] = []
    content_nums: list[int] = []
    # Reserve the Pages object number (created after we know kid numbers).
    pages_num = len(objects) + 1 + 2 * len(pages) + 1  # placeholder; fixed below

    # Build content + page objects; Parent points to the Pages object number.
    pages_obj_number = 2 + 2 * len(pages)  # font=1, then pairs, then pages, then catalog
    for page_lines in pages:
        stream = _content_stream(page_lines)
        content = (
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
        cnum = add(content)
        content_nums.append(cnum)
        page = (
            b"<< /Type /Page /Parent " + str(pages_obj_number).encode() + b" 0 R "
            b"/MediaBox [0 0 " + str(_PAGE_W).encode() + b" " + str(_PAGE_H).encode() + b"] "
            b"/Resources << /Font << /F1 " + str(font_num).encode() + b" 0 R >> >> "
            b"/Contents " + str(cnum).encode() + b" 0 R >>"
        )
        pnum = add(page)
        page_obj_nums.append(pnum)

    kids = b" ".join(str(n).encode() + b" 0 R" for n in page_obj_nums)
    pages_obj = add(
        b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_obj_nums)).encode() + b" >>"
    )
    catalog_num = add(b"<< /Type /Catalog /Pages " + str(pages_obj).encode() + b" 0 R >>")

    # Serialise with a cross-reference table.
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0] * (len(objects) + 1)
    for i, obj in enumerate(objects, start=1):
        offsets[i] = len(out)
        out += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for i in range(1, len(objects) + 1):
        out += f"{offsets[i]:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode()
        + b" /Root " + str(catalog_num).encode() + b" 0 R >>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    )

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(bytes(out))
    return p
