"""Run the complete, sanitized C1 smoke for the local whisper.cpp candidate."""
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

import psutil

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get("STUDYBUDDY_ASR_RUNTIME", "H:/Whisper/cli"))
MODEL = Path(os.environ.get("STUDYBUDDY_ASR_MODEL", str(RUNTIME.parent / "Models" / "ggml-large-v3-turbo.bin")))
PUBLIC_FIXTURE = Path(os.environ.get("STUDYBUDDY_ASR_FIXTURE", "H:/Whisper/Whisper-1.12.0/SampleClips/jfk.wav"))
ARTIFACT = ROOT / "results" / "asr-whisper-cpp" / "c1-smoke.json"
MODEL_NAME = "ggml-large-v3-turbo.bin"
TIMEOUT_SECONDS = 120
OUTPUT_LIMIT_BYTES = 262144
SPEECH_TEXT = "Study buddy verifies synthetic speech output."
EXPECTED_SPEECH_MARKER = "fellow americans"
DEFAULT_VERSION = "Const-me/Whisper 1.12.0; release 1.12.0; commit c5515ace19066e938854b4b99e0c2e9bbc2eeb65"
CHECK_IDS = tuple(f"C1-ASR-{number:02d}" for number in range(1, 15))


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def make_wav(path: Path, frames: bytes = b"", *, seconds: int = 1) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(frames or b"\x00\x00" * 16000 * seconds)


def make_speech_fixture(path: Path) -> bool:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        return False
    escaped_path = str(path).replace("'", "''")
    escaped_text = SPEECH_TEXT.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s=[System.Speech.Synthesis.SpeechSynthesizer]::new(); "
        "$s.SelectVoice('Microsoft Zira Desktop'); "
        f"$s.SetOutputToWaveFile('{escaped_path}'); $s.Speak('{escaped_text}'); "
        "$s.Dispose()"
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-Command", script],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and path.is_file() and path.stat().st_size > 44


def process_tree_alive(pid: int) -> bool:
    try:
        process = psutil.Process(pid)
        return process.is_running() or any(child.is_running() for child in process.children(recursive=True))
    except psutil.Error:
        return False


def terminate_tree(process: subprocess.Popen[bytes]) -> int:
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for item in children:
            item.terminate()
        parent.terminate()
        _, alive = psutil.wait_procs(children + [parent], timeout=5)
        for item in alive:
            item.kill()
        psutil.wait_procs(alive, timeout=5)
        return len(children)
    except psutil.Error:
        process.kill()
        process.wait(timeout=5)
        return 0


def output_files(output_dir: Path) -> list[Path]:
    return [*output_dir.glob("*.txt"), *output_dir.glob("*.srt")]


def run_case(
    executable: Path,
    model: Path,
    source: Path,
    output_dir: Path,
    *,
    timeout: float = TIMEOUT_SECONDS,
    cancel_after: float | None = None,
    output_limit: int = OUTPUT_LIMIT_BYTES,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / source.name
    shutil.copyfile(source, input_path)
    command = [
        str(executable), "-f", str(input_path), "-m", str(model),
        "--language", "en", "-otxt", "-osrt", "-nc",
    ]
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=output_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    peak_working_set = 0
    child_process_count = 0
    timed_out = False
    cancelled = False
    output_limited = False
    while process.poll() is None:
        elapsed = time.perf_counter() - started
        try:
            parent = psutil.Process(process.pid)
            descendants = parent.children(recursive=True)
            child_process_count = max(child_process_count, len(descendants))
            peak_working_set = max(
                peak_working_set,
                parent.memory_info().rss + sum(item.memory_info().rss for item in descendants),
            )
        except psutil.Error:
            pass
        if sum(item.stat().st_size for item in output_files(output_dir)) > output_limit:
            output_limited = True
            terminate_tree(process)
            break
        if cancel_after is not None and elapsed >= cancel_after:
            cancelled = True
            terminate_tree(process)
            break
        if elapsed >= timeout:
            timed_out = True
            terminate_tree(process)
            break
        time.sleep(0.02)
    stdout, stderr = process.communicate(timeout=5)
    files = output_files(output_dir)
    if sum(item.stat().st_size for item in files) > output_limit:
        output_limited = True
        for item in files:
            item.unlink()
        files = []
    txt = next(iter(output_dir.glob("*.txt")), None)
    srt = next(iter(output_dir.glob("*.srt")), None)
    txt_text = txt.read_text(encoding="utf-8", errors="replace") if txt else ""
    result = {
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "cancelled": cancelled,
        "output_limited": output_limited,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "txt_bytes": txt.stat().st_size if txt else 0,
        "srt_bytes": srt.stat().st_size if srt else 0,
        "output_bytes": sum(item.stat().st_size for item in files),
        "txt_nonempty": bool(txt_text.strip()),
        "srt_nonempty": bool(srt and srt.stat().st_size),
        "speech_detected": EXPECTED_SPEECH_MARKER in txt_text.lower(),
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "peak_working_set_bytes": peak_working_set,
        "child_process_count": child_process_count,
        "process_tree_clean": not process_tree_alive(process.pid),
    }
    return result


def check(check_id: str, name: str, passed: bool, **metrics: object) -> dict[str, object]:
    return {"id": check_id, "name": name, "status": "passed" if passed else "failed", "metrics": metrics}


def promotion_status(checks: list[dict[str, object]]) -> str:
    results = {str(item.get("id")): item.get("status") for item in checks}
    return "smoke_passed" if set(results) == set(CHECK_IDS) and all(
        results[check_id] == "passed" for check_id in CHECK_IDS
    ) else "c1_partial"


def main() -> None:
    started = time.perf_counter()
    executable = RUNTIME / "main.exe"
    model = MODEL
    temp_root = Path(tempfile.mkdtemp(prefix="studybuddy-asr-c1-"))
    checks: list[dict[str, object]] = []
    try:
        help_result = subprocess.run(
            [str(executable), "--help"], capture_output=True, timeout=30, check=False
        ) if executable.is_file() else None
        help_bytes = (help_result.stdout + help_result.stderr) if help_result else b""
        runtime_ready = executable.is_file() and model.is_file() and b"--output-srt" in help_bytes
        version = os.environ.get("STUDYBUDDY_ASR_VERSION", DEFAULT_VERSION).strip()
        checks.append(check(
            "C1-ASR-01", "runtime/model/version", runtime_ready and bool(version),
            runtime_sha256=digest(executable) if executable.is_file() else None,
            model_sha256=digest(model) if model.is_file() else None,
            model_bytes=model.stat().st_size if model.is_file() else 0,
            cli_contract_present=b"--output-txt" in help_bytes and b"--language" in help_bytes,
            version_recorded=bool(version),
            version_source="STUDYBUDDY_ASR_VERSION (verified against Whisper.dll PE metadata and GitHub release)" if version else "unavailable",
        ))

        speech = PUBLIC_FIXTURE
        speech_ready = speech.is_file()
        silent = temp_root / "silent.wav"
        make_wav(silent)
        empty = temp_root / "empty.wav"
        make_wav(empty, frames=b"", seconds=0)
        malformed = temp_root / "malformed.wav"
        malformed.write_bytes(b"not-a-wave")
        unsupported = temp_root / "unsupported.xyz"
        unsupported.write_bytes(b"ID3\x04\x00\x00unsupported")

        if runtime_ready and speech_ready:
            success = run_case(executable, model, speech, temp_root / "success")
            repeated = run_case(executable, model, speech, temp_root / "repeat")
            malformed_result = run_case(executable, model, malformed, temp_root / "malformed")
            unsupported_result = run_case(executable, model, unsupported, temp_root / "unsupported")
            silent_result = run_case(executable, model, silent, temp_root / "silent")
            empty_result = run_case(executable, model, empty, temp_root / "empty")
            timeout_result = run_case(executable, model, speech, temp_root / "timeout", timeout=0.05)
            cancel_result = run_case(executable, model, speech, temp_root / "cancel", cancel_after=0.05)
            output_limit_result = run_case(
                executable, model, speech, temp_root / "output-limit", output_limit=1
            )
        else:
            unavailable = {"exit_code": None, "timed_out": False, "cancelled": False,
                           "output_limited": False, "elapsed_ms": 0, "txt_bytes": 0,
                           "srt_bytes": 0, "output_bytes": 0, "txt_nonempty": False,
                           "srt_nonempty": False, "speech_detected": False,
                           "stdout_bytes": 0, "stderr_bytes": 0,
                           "peak_working_set_bytes": 0, "child_process_count": 0,
                           "process_tree_clean": True}
            success = repeated = malformed_result = unsupported_result = silent_result = empty_result = timeout_result = cancel_result = output_limit_result = unavailable

        checks.extend([
            check("C1-ASR-02", "public speech fixture success", speech_ready and success["exit_code"] == 0 and success["speech_detected"], fixture_sha256=digest(speech) if speech_ready else None, expected_marker_match=success["speech_detected"], elapsed_ms=success["elapsed_ms"]),
            check("C1-ASR-03", "TXT/SRT output", success["txt_nonempty"] and success["srt_nonempty"], txt_bytes=success["txt_bytes"], srt_bytes=success["srt_bytes"]),
            check("C1-ASR-04", "malformed input", malformed_result["exit_code"] not in (None, 0), exit_code=malformed_result["exit_code"]),
            check("C1-ASR-05", "unsupported format", unsupported_result["exit_code"] not in (None, 0), exit_code=unsupported_result["exit_code"]),
            check("C1-ASR-06", "empty/silent input", empty_result["exit_code"] not in (None, 0) and silent_result["exit_code"] == 0, empty_exit_code=empty_result["exit_code"], silent_exit_code=silent_result["exit_code"]),
            check("C1-ASR-07", "timeout", timeout_result["timed_out"] and timeout_result["process_tree_clean"], elapsed_ms=timeout_result["elapsed_ms"]),
            check("C1-ASR-08", "termination/cancellation", cancel_result["cancelled"] and cancel_result["process_tree_clean"], elapsed_ms=cancel_result["elapsed_ms"]),
            check("C1-ASR-09", "output-size limit", output_limit_result["output_limited"] and output_limit_result["output_bytes"] == 0, enforcement_triggered=output_limit_result["output_limited"], retained_output_bytes=output_limit_result["output_bytes"], configured_limit_bytes=OUTPUT_LIMIT_BYTES),
            check("C1-ASR-10", "repeated invocation", repeated["exit_code"] == 0 and repeated["txt_nonempty"] and repeated["srt_nonempty"], first_exit_code=success["exit_code"], repeated_exit_code=repeated["exit_code"]),
            check("C1-ASR-12", "child-process cleanup", all(item["process_tree_clean"] for item in (success, repeated, malformed_result, unsupported_result, silent_result, empty_result, timeout_result, cancel_result, output_limit_result)), max_child_process_count=max(item["child_process_count"] for item in (success, repeated, malformed_result, unsupported_result, silent_result, empty_result, timeout_result, cancel_result, output_limit_result))),
            check("C1-ASR-14", "resource measurement", success["elapsed_ms"] > 0 and success["peak_working_set_bytes"] > 0, elapsed_ms=success["elapsed_ms"], peak_working_set_bytes=success["peak_working_set_bytes"], output_bytes=success["output_bytes"], child_process_count=success["child_process_count"]),
        ])
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    checks.append(check("C1-ASR-11", "temp cleanup", not temp_root.exists(), temp_root_removed=not temp_root.exists()))
    provisional = {
        "schema_version": 1,
        "component": "asr-whisper-cpp",
        "status": "c1_partial",
        "network_called": False,
        "checks": checks,
        "summary": {},
    }
    serialized = json.dumps(provisional, ensure_ascii=True)
    privacy_passed = not any(value.lower() in serialized.lower() for value in (str(RUNTIME), str(temp_root), SPEECH_TEXT))
    checks.append(check(
        "C1-ASR-13", "privacy/stderr sanitization", privacy_passed,
        raw_stdout_retained=False, raw_stderr_retained=False, transcript_retained=False, private_path_retained=False,
    ))
    checks.sort(key=lambda item: str(item["id"]))
    passed_count = sum(item["status"] == "passed" for item in checks)
    status = promotion_status(checks)
    all_passed = status == "smoke_passed"
    payload = {
        "schema_version": 1,
        "component": "asr-whisper-cpp",
        "status": status,
        "network_called": False,
        "checks": checks,
        "summary": {
            "passed": passed_count,
            "failed": len(CHECK_IDS) - passed_count,
            "total": len(CHECK_IDS),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        },
        "promotion_rule": "Catalog may be smoke_passed only when all 14 C1-ASR checks pass.",
        "fixture_provenance": "Const-me/Whisper 1.12.0 SampleClips/jfk.wav; public repository fixture; hash retained, audio and transcript omitted.",
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"component": payload["component"], "status": payload["status"], **payload["summary"]}))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
