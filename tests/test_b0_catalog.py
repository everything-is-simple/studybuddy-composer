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
    assert "1 smoke_passed, 8 researching candidates" in result.stdout

    catalog = json.loads((ROOT / "manifests" / "b0-catalog.json").read_text(encoding="utf-8"))
    candidates = catalog["candidates"]
    asr = next(candidate for candidate in candidates if candidate["id"] == "asr-whisper-cpp")
    assert asr["status"] == "smoke_passed"
    assert asr["evidence_path"] == "results/asr-whisper-cpp/c1-smoke.json"
    assert all(
        candidate["status"] == "researching"
        for candidate in candidates
        if candidate["id"] != "asr-whisper-cpp"
    )
