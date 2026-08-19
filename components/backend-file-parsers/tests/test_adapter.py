from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from backend_file_parsers import ParseOptions, parse_file

FIXTURES = Path("H:/studybuddy-test/fixtures/kaobuddy-foundation")


def test_supported_and_boundaries():
    expected = {
        "sample.txt": "success", "sample.md": "success", "chinese.txt": "success",
        "empty.txt": "empty", "sample.pdf": "success", "corrupt.pdf": "failed",
        "sample.docx": "success", "empty.docx": "failed", "corrupt.docx": "failed",
        "sample.pptx": "success", "empty.pptx": "empty", "corrupt.pptx": "failed",
        "sample.rtf": "rejected", "sample.doc": "rejected", "sample.ppt": "rejected",
    }
    for name, status in expected.items():
        result = parse_file(FIXTURES / name)
        assert result.status == status, (name, result)
        assert result.source_sha256
        if result.status != "success":
            assert result.text == ""


def test_structured_spans():
    pdf = parse_file(FIXTURES / "sample.pdf")
    assert pdf.spans[0].kind == "page"
    assert "Synthetic PDF" in pdf.text
    pptx = parse_file(FIXTURES / "sample.pptx")
    assert [span.kind for span in pptx.spans] == ["slide", "slide"]
    assert "第一页合成内容" in pptx.text


def test_valid_empty_docx(tmp_path):
    from docx import Document
    path = tmp_path / "valid-empty.docx"
    Document().save(path)
    result = parse_file(path)
    assert result.status == "empty"
    assert result.error_code is None


def test_size_limit():
    result = parse_file(FIXTURES / "sample.txt", options=ParseOptions(max_bytes=1))
    assert result.status == "rejected"
    assert result.error_code == "file_too_large"
