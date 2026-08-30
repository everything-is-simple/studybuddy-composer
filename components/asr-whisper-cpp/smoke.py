"""C1 smoke for the selected local whisper.cpp runtime.

The command is opt-in and writes only sanitized evidence. No source audio,
transcript, stderr, or private path is retained in the result.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get("STUDYBUDDY_ASR_RUNTIME", "H:/WhisperCli"))
ARTIFACT = ROOT / "results" / "asr-whisper-cpp" / "c1-smoke.json"
TIMEOUT = 120
OUTPUT_LIMIT = 262144


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def fixture(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 16000)


def run_case(executable: Path, model: Path, audio: Path, output_dir: Path, *, seconds: int = 10) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_audio = output_dir / audio.name
    shutil.copyfile(audio, input_audio)
    command = [
        str(executable), "-f", str(input_audio), "-m", str(model),
        "--language", "en", "--duration", str(seconds * 1000),
        "-otxt", "-osrt", "-nc",
    ]
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command, cwd=output_dir, capture_output=True, timeout=TIMEOUT, check=False
        )
        timed_out = False
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = None
    return {
        "timed_out": timed_out,
        "exit_code": exit_code,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "txt_bytes": next((p.stat().st_size for p in output_dir.glob("*.txt")), 0),
        "srt_bytes": next((p.stat().st_size for p in output_dir.glob("*.srt")), 0),
    }


def main() -> None:
    started = time.perf_counter()
    executable = RUNTIME / "main.exe"
    model = RUNTIME / "Models" / "ggml-large-v3-turbo.bin"
    checks = {"runtime_present": executable.is_file(), "model_present": model.is_file()}
    temp_root = Path(tempfile.mkdtemp(prefix="studybuddy-asr-c1-"))
    try:
        audio = temp_root / "fixture.wav"
        fixture(audio)
        checks["fixture_sha256"] = digest(audio)
        checks["fixture_bytes"] = audio.stat().st_size
        if executable.is_file() and model.is_file():
            checks["success"] = run_case(executable, model, audio, temp_root / "success")
            bad_audio = temp_root / "bad.wav"
            bad_audio.write_bytes(b"not-a-wave")
            checks["malformed_input"] = run_case(executable, model, bad_audio, temp_root / "malformed")
        else:
            checks["success"] = {"skipped": True}
            checks["malformed_input"] = {"skipped": True}
        checks["output_limit_ok"] = all(
            checks[key].get("txt_bytes", 0) + checks[key].get("srt_bytes", 0) <= OUTPUT_LIMIT
            for key in ("success", "malformed_input")
        )
        checks["timeout_configured"] = TIMEOUT == 120
        checks["cleanup_required"] = True
        passed = (
            checks["runtime_present"] and checks["model_present"]
            and checks["success"].get("exit_code") == 0
            and checks["success"].get("txt_bytes", 0) <= OUTPUT_LIMIT
            and checks["success"].get("srt_bytes", 0) <= OUTPUT_LIMIT
            and checks["malformed_input"].get("exit_code") not in (None, 0)
            and checks["output_limit_ok"]
        )
        payload = {
            "component": "asr-whisper-cpp",
            "status": "smoke_passed" if passed else "researching_smoke_failed",
            "network_called": False,
            "timeout_seconds": TIMEOUT,
            "output_limit_bytes": OUTPUT_LIMIT,
            "checks": checks,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "limitations": [
                "Synthetic silence fixture proves process and output boundaries only; it is not an accuracy claim.",
                "Cancellation/termination is not directly exercised by this CLI smoke and remains required for Integration/Formal.",
            ],
        }
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"component": payload["component"], "status": payload["status"]}))
    if payload["status"] != "smoke_passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
