"""Offline preflight for the RapidOCR ONNX fallback candidate.

No OCR call occurs: default model acquisition must stay disabled until an explicit
C1 synthetic-fixture smoke controls the local model location and output evidence.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "results" / "ocr-rapidocr" / "preflight.json"


def version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> None:
    started = time.perf_counter()
    packages = {name: version(name) for name in ("rapidocr_onnxruntime", "onnxruntime")}
    payload = {
        "component": "ocr-rapidocr",
        "status": "researching_preflight_passed" if all(packages.values()) else "researching_preflight_failed",
        "network_called": False,
        "platform": platform.platform(),
        "packages": packages,
        "imports": {name: importlib.util.find_spec(name) is not None for name in ("rapidocr_onnxruntime", "onnxruntime")},
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "limitations": [
            "No OCR model was downloaded or initialized.",
            "No image was processed.",
            "This preflight is not a C1 smoke pass.",
            "C1 requires pre-provisioned local models, synthetic Chinese/English fixtures, timeout, cleanup, and sanitized evidence.",
        ],
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"component": payload["component"], "status": payload["status"]}))
    if payload["status"] != "researching_preflight_passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
