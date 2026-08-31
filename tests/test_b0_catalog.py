import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_b0_catalog_validation_passes():
    script = ROOT / "scripts" / "validate-b0-catalog.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 smoke_passed, 2 integration_passed, 5 researching candidates" in result.stdout

    catalog = json.loads((ROOT / "manifests" / "b0-catalog.json").read_text(encoding="utf-8"))
    candidates = catalog["candidates"]
    asr = next(candidate for candidate in candidates if candidate["id"] == "asr-whisper-cpp")
    assert asr["status"] == "integration_passed"
    assert asr["evidence_path"] == "H:/studybuddy-test/artifacts/asr-whisper-cpp-integration/latest.json"
    assert "C1 and isolated C2 Integration evidence pass" in asr["notes"]
    assert asr["version"] == "Const-me/Whisper 1.12.0 (Whisper.dll PE product version 1.12.0.0)"
    assert asr["source_revision"] == "Const-me/Whisper@c5515ace19066e938854b4b99e0c2e9bbc2eeb65"
    rapidocr = next(candidate for candidate in candidates if candidate["id"] == "ocr-rapidocr")
    assert rapidocr["status"] == "smoke_passed"
    assert rapidocr["evidence_path"] == "H:/studybuddy-composer/results/ocr-rapidocr/c1-smoke.json"
    paddleocr = next(candidate for candidate in candidates if candidate["id"] == "ocr-paddleocr")
    assert paddleocr["status"] == "integration_passed"
    assert paddleocr["evidence_path"] == "H:/studybuddy-composer/results/ocr-paddleocr/c1-smoke.json"
    assert paddleocr["integration_evidence_path"] == "H:/studybuddy-integration/results/ocr-paddleocr-c2/integration.json"
    report = next(candidate for candidate in candidates if candidate["id"] == "report-core")
    assert report["status"] == "smoke_passed"
    assert report["version"] == "b3-report-projection-candidate-v1"
    assert report["license_status"] == "project_owned"
    assert report["evidence_path"] == "H:/studybuddy-composer/results/report-core/c1-smoke.json"
    assert "C1 smoke passed" in report["notes"]
    assert "JSON/Markdown only" in report["notes"]
    assert "PDF" in report["notes"] and "delivery state" in report["notes"]
    plan = (ROOT / "components" / "report-core" / "C0-DECISION-AND-C1-PLAN.md").read_text(encoding="utf-8")
    evidence = json.loads((ROOT / "results/report-core/c1-smoke.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "passed"
    assert evidence["gate"] == "B3-C1"
    assert evidence["measurements"]["temporary_files"] == 0
    for marker in ("half-open", "source_deleted", "source_unavailable", "Network denial", "PDF is excluded"):
        assert marker in plan
    assert all(
        candidate["status"] == "researching"
        for candidate in candidates
        if candidate["id"] not in {"asr-whisper-cpp", "ocr-rapidocr", "ocr-paddleocr", "report-core"}
    )
