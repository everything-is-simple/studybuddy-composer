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
    assert "1 smoke_passed, 1 integration_passed, 7 researching candidates" in result.stdout

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
    assert all(
        candidate["status"] == "researching"
        for candidate in candidates
        if candidate["id"] not in {"asr-whisper-cpp", "ocr-rapidocr"}
    )
