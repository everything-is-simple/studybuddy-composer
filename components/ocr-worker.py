"""Private Composer worker; stdout/stderr are never copied into evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    component, image_name, output_name = sys.argv[1:4]
    image = Path(image_name)
    if image.stat().st_size > 10 * 1024 * 1024:
        return 3
    from PIL import Image
    with Image.open(image) as opened:
        if opened.width * opened.height > 12_000_000:
            return 3
    result: dict[str, object]
    if component == "ocr-rapidocr":
        from rapidocr_onnxruntime import RapidOCR
        boxes, elapsed = RapidOCR()(str(image))
        texts = []
        scores = []
        for item in boxes or []:
            if len(item) >= 2:
                value = item[1]
                if isinstance(value, (list, tuple)):
                    texts.append(str(value[0]))
                    if len(value) > 1:
                        scores.append(float(value[1]))
                else:
                    texts.append(str(value))
                if len(item) >= 3 and not isinstance(value, (list, tuple)):
                    scores.append(float(item[2]))
        if not scores and texts:
            scores = [1.0] * len(texts)
        result = {"text": "\n".join(texts), "confidence": scores, "elapsed": elapsed}
    elif component == "ocr-paddleocr":
        from paddleocr import PaddleOCR
        model_root = sys.argv[4] if len(sys.argv) > 4 else None
        kwargs = {"lang": "ch", "use_doc_orientation_classify": False, "use_doc_unwarping": False,
                  "use_textline_orientation": False, "text_detection_model_name": "PP-OCRv5_server_det",
                  "text_recognition_model_name": "PP-OCRv5_server_rec", "enable_mkldnn": False,
                  "device": "cpu"}
        if model_root:
            kwargs["text_detection_model_dir"] = str(Path(model_root) / "PP-OCRv5_server_det")
            kwargs["text_recognition_model_dir"] = str(Path(model_root) / "PP-OCRv5_server_rec")
        output = PaddleOCR(**kwargs).predict(str(image))
        texts = []
        scores = []
        for page in output or []:
            data = page.json if hasattr(page, "json") else page
            if isinstance(data, str):
                data = json.loads(data)
            for value in data.get("res", {}).get("rec_texts", []):
                texts.append(str(value))
            scores.extend(float(value) for value in data.get("res", {}).get("rec_scores", []))
        result = {"text": "\n".join(texts), "confidence": scores}
    else:
        raise ValueError("unsupported component")
    Path(output_name).write_text(json.dumps(result, ensure_ascii=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Stable failure only; diagnostics stay local to the process.
        raise SystemExit(2)
