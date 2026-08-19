from __future__ import annotations

import hashlib
import time
import zipfile
from pathlib import Path
from typing import Literal

from docx import Document
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader

Status = Literal["success", "empty", "rejected", "failed"]
SpanKind = Literal["document", "page", "slide"]


class ParseOptions(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    max_zip_members: int = Field(default=256, ge=1)
    max_uncompressed_bytes: int = Field(default=50 * 1024 * 1024, ge=1)


class TextSpan(BaseModel):
    ordinal: int = Field(ge=1)
    kind: SpanKind
    label: str
    text: str


class ParseResult(BaseModel):
    source_name: str
    source_suffix: str
    source_sha256: str
    parser_id: str
    parser_version: str
    status: Status
    text: str
    spans: list[TextSpan]
    warnings: list[str]
    error_code: str | None = None
    elapsed_ms: float


PARSER_VERSION = "1.0.0"
SUPPORTED_TEXT = {".txt", ".md", ".markdown"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _base(path: Path, digest: str, parser_id: str, started: float, **values: object) -> ParseResult:
    return ParseResult(
        source_name=path.name,
        source_suffix=path.suffix.lower(),
        source_sha256=digest,
        parser_id=parser_id,
        parser_version=PARSER_VERSION,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        **values,
    )


def _failure(path: Path, digest: str, parser_id: str, started: float, code: str, warning: str = "", status: Status = "failed") -> ParseResult:
    return _base(path, digest, parser_id, started, status=status, text="", spans=[], warnings=[warning] if warning else [], error_code=code)


def _zip_limits(path: Path, options: ParseOptions) -> None:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > options.max_zip_members:
            raise ValueError("zip_member_limit")
        total = sum(member.file_size for member in members)
        if total > options.max_uncompressed_bytes:
            raise ValueError("zip_uncompressed_limit")
        if any(member.file_size > options.max_uncompressed_bytes for member in members):
            raise ValueError("zip_member_size_limit")
        if any(member.compress_size and member.file_size / member.compress_size > 1000 for member in members):
            raise ValueError("zip_compression_ratio_limit")
        if any(member.file_size < 0 or member.compress_size < 0 for member in members):
            raise ValueError("zip_invalid_size")
        archive.testzip()


def _parse_text(path: Path, digest: str, started: float) -> ParseResult:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return _failure(path, digest, "backend-text", started, "invalid_utf8", "仅接受 UTF-8 文本。")
    status: Status = "empty" if not text else "success"
    spans = [] if not text else [TextSpan(ordinal=1, kind="document", label="document", text=text)]
    return _base(path, digest, "backend-text", started, status=status, text=text, spans=spans, warnings=[], error_code=None)


def parse_file(source_path: Path, declared_media_type: str | None = None, options: ParseOptions | None = None) -> ParseResult:
    started = time.perf_counter()
    options = options or ParseOptions()
    path = Path(source_path)
    suffix = path.suffix.lower()
    try:
        if not path.is_file():
            return _failure(path, "", "backend-file-parsers", started, "source_not_found")
        size = path.stat().st_size
        digest = _sha256(path)
        if size > options.max_bytes:
            return _failure(path, digest, "backend-file-parsers", started, "file_too_large", "超过单文件大小限制。", "rejected")
        if suffix in SUPPORTED_TEXT:
            return _parse_text(path, digest, started)
        if suffix == ".pdf":
            try:
                reader = PdfReader(str(path), strict=True)
                spans = [TextSpan(ordinal=i, kind="page", label=f"page-{i}", text=(page.extract_text() or "")) for i, page in enumerate(reader.pages, 1)]
            except Exception:
                return _failure(path, digest, "backend-pdf", started, "corrupt_pdf")
            text = "\n\n".join(span.text for span in spans)
            status: Status = "empty" if not text.strip() else "success"
            warnings = ["PDF 没有可提取的文字层；本阶段不执行 OCR。"] if status == "empty" else []
            return _base(path, digest, "backend-pdf", started, status=status, text=text, spans=spans, warnings=warnings, error_code=None)
        if suffix == ".docx":
            try:
                _zip_limits(path, options)
                document = Document(str(path))
                paragraphs = [paragraph.text for paragraph in document.paragraphs]
            except ValueError as exc:
                return _failure(path, digest, "backend-docx", started, str(exc))
            except Exception:
                return _failure(path, digest, "backend-docx", started, "corrupt_docx")
            text = "\n".join(paragraphs)
            status = "empty" if not text.strip() else "success"
            warnings = ["仅提取段落正文，复杂样式、文本框和嵌入对象未纳入本阶段契约。"]
            spans = [] if status == "empty" else [TextSpan(ordinal=1, kind="document", label="document", text=text)]
            return _base(path, digest, "backend-docx", started, status=status, text=text, spans=spans, warnings=warnings, error_code=None)
        if suffix == ".pptx":
            try:
                _zip_limits(path, options)
                with zipfile.ZipFile(path) as archive:
                    slide_names = sorted((name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")), key=lambda n: int(Path(n).stem.replace("slide", "")))
                    if not slide_names:
                        return _failure(path, digest, "backend-pptx", started, "no_slides", "没有可读取的幻灯片。", "empty")
                    import xml.etree.ElementTree as ET
                    spans = []
                    for ordinal, name in enumerate(slide_names, 1):
                        root = ET.fromstring(archive.read(name))
                        slide_text = " ".join((node.text or "").strip() for node in root.iter() if node.tag.endswith("}t") and (node.text or "").strip())
                        spans.append(TextSpan(ordinal=ordinal, kind="slide", label=f"slide-{ordinal}", text=slide_text))
            except ValueError as exc:
                return _failure(path, digest, "backend-pptx", started, str(exc))
            except Exception:
                return _failure(path, digest, "backend-pptx", started, "corrupt_pptx")
            text = "\n\n".join(span.text for span in spans)
            status = "empty" if not text.strip() else "success"
            return _base(path, digest, "backend-pptx", started, status=status, text=text, spans=spans, warnings=[], error_code=None)
        if suffix == ".rtf":
            return _failure(path, digest, "backend-file-parsers", started, "unsupported_rtf", "RTF 暂无可靠解析器，本阶段拒绝。", "rejected")
        if suffix in {".doc", ".ppt"}:
            return _failure(path, digest, "backend-file-parsers", started, "requires_converter", "旧格式需要受控转换器，本阶段拒绝。", "rejected")
        return _failure(path, digest, "backend-file-parsers", started, "unsupported_format", "不支持的文件格式。", "rejected")
    except OSError:
        return _failure(path, "", "backend-file-parsers", started, "source_unreadable")
    except Exception:
        return _failure(path, "", "backend-file-parsers", started, "parser_exception")
