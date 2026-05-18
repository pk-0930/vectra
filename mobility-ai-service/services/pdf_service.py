from io import BytesIO


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class PdfService:
    def render_simple_pdf(self, title: str, lines: list[str]) -> bytes:
        stream = BytesIO()
        content_lines = ["BT", "/F1 16 Tf", "50 780 Td", f"({_escape_pdf_text(title)}) Tj"]
        y_offset = 0
        for line in lines:
            y_offset -= 18
            content_lines.append(f"0 {y_offset} Td")
            content_lines.append(f"({_escape_pdf_text(line)}) Tj")
        content_lines.append("ET")
        content = "\n".join(content_lines).encode("latin-1", errors="replace")

        objects: list[bytes] = []
        objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
        objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
        objects.append(
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        )
        objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
        objects.append(
            f"5 0 obj << /Length {len(content)} >> stream\n".encode("latin-1")
            + content
            + b"\nendstream endobj\n"
        )

        stream.write(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(stream.tell())
            stream.write(obj)
        xref_position = stream.tell()
        stream.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        stream.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            stream.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
        stream.write(
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF".encode(
                "latin-1"
            )
        )
        return stream.getvalue()
