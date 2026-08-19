from __future__ import annotations

import struct
import zlib
import zipfile
from pathlib import Path

ROOT = Path("H:/studybuddy-test/fixtures/kaobuddy-foundation")
ROOT.mkdir(parents=True, exist_ok=True)
(ROOT / "sample.txt").write_text("StudyBuddy synthetic TXT fixture.\nProcess and thread basics.\n", encoding="utf-8")
(ROOT / "sample.md").write_text("# Synthetic Markdown\n\n- Process\n- Thread\n", encoding="utf-8")
(ROOT / "chinese.txt").write_text("合成中文资料：进程是资源分配的基本单位。\n线程是调度的基本单位。\n", encoding="utf-8")
(ROOT / "empty.txt").write_bytes(b"")
(ROOT / "sample.rtf").write_text(r"{\rtf1\ansi Synthetic RTF\par Process and thread basics.}", encoding="ascii")
(ROOT / "empty.rtf").write_text(r"{\rtf1\ansi}", encoding="ascii")
(ROOT / "corrupt.pdf").write_bytes(b"%PDF-1.7\ncorrupt and intentionally incomplete")
(ROOT / "corrupt.docx").write_bytes(b"not a zip")
(ROOT / "corrupt.pptx").write_bytes(b"not a zip")
(ROOT / "sample.doc").write_bytes("binary-prefix\x00".encode() + "合成旧 DOC 文本：操作系统原理。".encode("utf-16le"))
(ROOT / "empty.doc").write_bytes(bytes([0, 1, 2, 3]))
(ROOT / "sample.ppt").write_bytes(b"synthetic legacy ppt placeholder; KaoBuddy rejects by extension")

# Minimal one-page PDF with a built-in Helvetica text layer.
stream = b"BT /F1 18 Tf 72 720 Td (Synthetic PDF process basics) Tj ET"
objects = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
]
pdf = bytearray(b"%PDF-1.4\n")
offsets = [0]
for index, obj in enumerate(objects, 1):
    offsets.append(len(pdf))
    pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
xref = len(pdf)
pdf.extend(f"xref\n0 {len(objects)+1}\n".encode())
pdf.extend(b"0000000000 65535 f \n")
for offset in offsets[1:]:
    pdf.extend(f"{offset:010d} 00000 n \n".encode())
pdf.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
(ROOT / "sample.pdf").write_bytes(pdf)

with zipfile.ZipFile(ROOT / "sample.docx", "w", zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("[Content_Types].xml", """<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>""")
    archive.writestr("_rels/.rels", """<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""")
    archive.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>合成 DOCX 正文：进程与线程。</w:t></w:r></w:p><w:sectPr/></w:body></w:document>""")

with zipfile.ZipFile(ROOT / "empty.docx", "w", zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>")

with zipfile.ZipFile(ROOT / "sample.pptx", "w", zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("[Content_Types].xml", "<Types></Types>")
    archive.writestr("ppt/slides/slide2.xml", "<p:sld xmlns:p=\"p\" xmlns:a=\"a\"><a:t>第二页合成内容</a:t></p:sld>")
    archive.writestr("ppt/slides/slide1.xml", "<p:sld xmlns:p=\"p\" xmlns:a=\"a\"><a:t>第一页合成内容</a:t></p:sld>")
with zipfile.ZipFile(ROOT / "empty.pptx", "w", zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("[Content_Types].xml", "<Types></Types>")
    archive.writestr("ppt/slides/slide1.xml", "<p:sld xmlns:p=\"p\" xmlns:a=\"a\"></p:sld>")

# 1x1 opaque white PNG, generated without image libraries.
def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
raw = b"\x00\xff\xff\xff\xff"
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
(ROOT / "sample.png").write_bytes(png)
print(f"generated fixtures in {ROOT}")
