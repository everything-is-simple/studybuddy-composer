"""Offline preflight for the selected whisper.cpp ASR candidate.

This is intentionally not C1 smoke evidence: it does not transcribe user media,
change catalog status, or authorize Formal adoption.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get("STUDYBUDDY_ASR_RUNTIME", "H:/WhisperCli"))
ARTIFACT = ROOT / "results" / "asr-whisper-cpp" / "preflight.json"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> None:
    started = time.perf_counter()
    executable = RUNTIME / "main.exe"
    model = RUNTIME / "Models" / "ggml-large-v3-turbo.bin"
    result = subprocess.run(
        [str(executable), "--help"], capture_output=True, text=True, timeout=30, check=False
    ) if executable.is_file() else None
    # This wrapper writes usage to stderr and exits 1 for --help; accept that
    # documented behavior while still requiring the expected CLI switches.
    help_text = (result.stdout + result.stderr) if result else ""
    contract = {
        "output_txt": "--output-txt" in help_text,
        "output_srt": "--output-srt" in help_text,
        "language": "--language" in help_text,
        "duration": "--duration" in help_text,
    }
    ready = bool(result and result.returncode in {0, 1} and model.is_file() and all(contract.values()))
    payload = {
        "component": "asr-whisper-cpp",
        "status": "researching_preflight_passed" if ready else "researching_preflight_failed",
        "network_called": False,
        "runtime_present": executable.is_file(),
        "model_present": model.is_file(),
        "model_size_bytes": model.stat().st_size if model.is_file() else None,
        "model_sha256": digest(model) if model.is_file() else None,
        "cli_contract": contract,
        "exit_code": result.returncode if result else None,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "limitations": [
            "No audio was transcribed.",
            "This preflight is not a C1 smoke pass.",
            "Timeout, cancellation, malformed audio, cleanup, and sanitized output remain required.",
        ],
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"component": payload["component"], "status": payload["status"]}))
    if payload["status"] != "researching_preflight_passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
