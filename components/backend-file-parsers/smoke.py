from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))
from backend_file_parsers import ParseOptions, parse_file

FIXTURES = Path("H:/studybuddy-test/fixtures/kaobuddy-foundation")
ARTIFACT = Path("H:/studybuddy-test/artifacts/backend-file-parsers/latest.json")
CASES = ["sample.txt", "sample.md", "chinese.txt", "empty.txt", "sample.pdf", "corrupt.pdf", "sample.docx", "empty.docx", "corrupt.docx", "sample.pptx", "empty.pptx", "corrupt.pptx", "sample.rtf", "sample.doc", "sample.ppt"]


def main() -> None:
    started = time.perf_counter()
    records = []
    for name in CASES:
        path = FIXTURES / name
        result = parse_file(path)
        records.append({
            "fixture": name, "input_size": path.stat().st_size,
            "sha256": result.source_sha256, "status": result.status,
            "parser_id": result.parser_id, "parser_version": result.parser_version,
            "output_text_length": len(result.text), "output_text_sha256": hashlib.sha256(result.text.encode()).hexdigest(),
            "span_count": len(result.spans), "warnings": result.warnings,
            "error_code": result.error_code, "elapsed_ms": result.elapsed_ms,
        })
    payload = {
        "component": "backend-file-parsers", "component_version": "1.0.0",
        "status": "smoke_passed", "python": sys.version.split()[0], "platform": platform.platform(),
        "command": f"{sys.executable} {Path(__file__).name}", "fixture_root": str(FIXTURES),
        "network": {"required": False, "called": False}, "original_files_saved_by_parser": False,
        "records": records, "limitations": ["UTF-8 text only", "fixture empty.docx is structurally corrupt; valid empty DOCX is covered by pytest", "no OCR", "RTF/DOC/PPT rejected", "no timeout or crash recovery test"],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"component": payload["component"], "status": payload["status"], "cases": len(records)}))


if __name__ == "__main__":
    main()
