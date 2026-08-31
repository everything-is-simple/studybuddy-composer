"""Run the RapidOCR ONNX fallback C1 smoke in the Composer sandbox."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocr_smoke_common import run_smoke

ARTIFACT = Path(__file__).resolve().parents[2] / "results" / "ocr-rapidocr" / "c1-smoke.json"

if __name__ == "__main__":
    if importlib.util.find_spec("rapidocr_onnxruntime") is None:
        raise SystemExit("rapidocr_onnxruntime package is not installed")
    raise SystemExit(run_smoke("ocr-rapidocr", ARTIFACT))
