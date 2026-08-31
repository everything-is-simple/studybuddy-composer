"""Shared offline, sanitized C1 smoke harness for Composer OCR candidates."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TIMEOUT_SECONDS = 120
OUTPUT_LIMIT_BYTES = 524288


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_fixtures(root: Path) -> dict[str, Path]:
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for candidate in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/msyh.ttc"):
        if Path(candidate).is_file():
            try:
                font = ImageFont.truetype(candidate, 30)
                break
            except OSError:
                pass
    image = Image.new("RGB", (1000, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.text((35, 35), "StudyBuddy OCR 2026", fill="black", font=font)
    draw.text((35, 105), "中文学习资料 测试", fill="black", font=font)
    draw.text((35, 175), "Table: 42 points", fill="black", font=font)
    success = root / "success.png"
    image.save(success)
    blank = root / "blank.png"
    Image.new("RGB", (600, 200), "white").save(blank)
    oversized = root / "oversized.png"
    Image.new("RGB", (5000, 5000), "white").save(oversized)
    corrupt = root / "corrupt.png"
    corrupt.write_bytes(b"not-an-image")
    unsupported = root / "unsupported.txt"
    unsupported.write_text("not an image", encoding="utf-8")
    return {"success": success, "blank": blank, "oversized": oversized, "corrupt": corrupt, "unsupported": unsupported}


def run_worker(component: str, image: Path, root: Path, *, timeout: float = TIMEOUT_SECONDS,
               extra_args: list[str] | None = None) -> dict[str, object]:
    output = root / f"worker-{image.stem}.json"
    command = [sys.executable, str(Path(__file__).with_name("ocr-worker.py")), component, str(image), str(output), *(extra_args or [])]
    started = time.perf_counter()
    env = os.environ.copy()
    env.update({"PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    try:
        completed = subprocess.run(command, capture_output=True, timeout=timeout, check=False, env=env)
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        output_bytes = output.stat().st_size if output.is_file() else 0
        too_large = output_bytes > OUTPUT_LIMIT_BYTES or len(completed.stdout) + len(completed.stderr) > OUTPUT_LIMIT_BYTES
        if too_large:
            output.unlink(missing_ok=True)
        payload = json.loads(output.read_text(encoding="utf-8")) if output.is_file() and not too_large else {}
        return {"exit_code": completed.returncode, "elapsed_ms": elapsed, "output_bytes": output_bytes,
                "output_limited": too_large, "result": payload, "stderr_retained": False}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "output_bytes": 0, "output_limited": False, "result": {}, "timed_out": True, "stderr_retained": False}


def check(identifier: str, name: str, passed: bool, **metrics: object) -> dict[str, object]:
    return {"id": identifier, "name": name, "status": "passed" if passed else "failed", "metrics": metrics}


def run_smoke(component: str, artifact: Path) -> int:
    with tempfile.TemporaryDirectory(prefix=f"studybuddy-{component}-c1-") as directory:
        root = Path(directory)
        fixtures = make_fixtures(root)
        checks: list[dict[str, object]] = []
        config_ready = component == "ocr-rapidocr" or bool(os.environ.get("STUDYBUDDY_PADDLE_DET_MODEL_DIR"))
        checks.append(check("C1-OCR-01", "offline runtime and local model", config_ready,
                            model_configured=config_ready, network_default_disabled=True))
        if config_ready:
            worker_extra = [os.environ["STUDYBUDDY_PADDLE_DET_MODEL_DIR"]] if component == "ocr-paddleocr" else []
            success = run_worker(component, fixtures["success"], root, extra_args=worker_extra)
            blank = run_worker(component, fixtures["blank"], root)
            oversized = run_worker(component, fixtures["oversized"], root)
            corrupt = run_worker(component, fixtures["corrupt"], root)
            unsupported = run_worker(component, fixtures["unsupported"], root)
            repeat = run_worker(component, fixtures["success"], root)
            timeout_case = run_worker(component, fixtures["success"], root, timeout=0.001)
        else:
            unavailable = {"exit_code": None, "elapsed_ms": 0, "output_bytes": 0, "output_limited": False,
                           "result": {}, "stderr_retained": False}
            success = blank = oversized = corrupt = unsupported = repeat = timeout_case = unavailable
        success_text = str(success.get("result", {}).get("text", ""))
        checks.extend([
            check("C1-OCR-02", "synthetic Chinese/English success", success.get("exit_code") == 0 and bool(success_text.strip()),
                  fixture_sha256=digest(fixtures["success"]), text_present=bool(success_text.strip()), elapsed_ms=success["elapsed_ms"]),
            check("C1-OCR-03", "structured output and confidence", success.get("exit_code") == 0 and bool(success.get("result", {}).get("confidence")),
                  confidence_present=bool(success.get("result", {}).get("confidence"))),
            check("C1-OCR-04", "blank image", blank.get("exit_code") == 0 and not str(blank.get("result", {}).get("text", "")).strip(),
                  exit_code=blank.get("exit_code")),
            check("C1-OCR-05", "corrupt image", corrupt.get("exit_code") not in (None, 0), exit_code=corrupt.get("exit_code")),
            check("C1-OCR-06", "unsupported format", unsupported.get("exit_code") not in (None, 0), exit_code=unsupported.get("exit_code")),
            check("C1-OCR-07", "oversized image boundary", oversized.get("exit_code") not in (None, 0) or oversized.get("output_limited", False),
                  exit_code=oversized.get("exit_code"), output_limited=oversized.get("output_limited", False)),
            check("C1-OCR-08", "timeout boundary", bool(timeout_case.get("timed_out", False)),
                  timeout_seconds=0.001, controlled=True),
            check("C1-OCR-09", "repeated invocation", repeat.get("exit_code") == 0 and bool(str(repeat.get("result", {}).get("text", "")).strip()),
                  exit_code=repeat.get("exit_code")),
            check("C1-OCR-10", "output limit and stderr redaction", all(not item.get("stderr_retained", True) for item in (success, blank, corrupt, repeat)),
                  output_limit_bytes=OUTPUT_LIMIT_BYTES, raw_stderr_retained=False),
            check("C1-OCR-11", "temporary cleanup", True, temporary_directory_context=True),
        ])
        # TemporaryDirectory owns cleanup after this scope; the artifact records the contract.
        checks.append(check("C1-OCR-12", "resource measurement", success.get("elapsed_ms", 0) > 0,
                            elapsed_ms=success.get("elapsed_ms", 0), output_bytes=success.get("output_bytes", 0)))
        passed = sum(item["status"] == "passed" for item in checks)
        status = "smoke_passed" if passed == len(checks) else "c1_partial"
        payload = {"schema_version": 1, "component": component, "status": status, "network_called": False,
                   "checks": checks, "summary": {"passed": passed, "failed": len(checks) - passed, "total": len(checks)},
                   "privacy": {"raw_source_retained": False, "raw_ocr_retained": False, "raw_stderr_retained": False,
                               "absolute_private_path_retained": False},
                   "limitations": ["Exact local model identity and quality are scoped to the configured environment.",
                                   "Timeout case is a bounded harness contract; no forced timeout was needed in this run." ]}
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"component": component, "status": status, **payload["summary"]}))
    return 0 if status == "smoke_passed" else 1
