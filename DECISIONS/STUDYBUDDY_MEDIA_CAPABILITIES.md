# StudyBuddy media capability decision

> Decision date: 2026-08-30
> Scope: local Windows development/test environment and Composer candidate governance.
> This document does not promote any candidate into the Formal system by itself.

## Decision summary

| Capability | Selected path | Role | Current evidence/status |
|---|---|---|---|
| ASR | `H:/WhisperCli` using `ggml-large-v3-turbo.bin` | One canonical local runtime | Real local Chinese MP3 smoke passed; B1 Composer/Integration/Formal gates remain |
| TTS | `edge-tts==7.2.8` | Free explicit online candidate | Package/voice-list smoke passed; network service, not offline; no purchased API key |
| OCR | `PaddleOCR==3.7.0` + `PaddlePaddle==3.3.1` | Primary Chinese/document OCR candidate | Python imports passed; model/image smoke pending; B2 gates remain |
| OCR fallback | `rapidocr_onnxruntime==1.4.4` | Lightweight ONNX fallback | Python import passed; image/model smoke pending |
| OCR compatibility fallback | Tesseract | Minimal compatibility option only | Not installed; not the Chinese primary |
| PPTX native text | StudyBuddy `formal-pptx` parser / `python-pptx` | Primary extraction of text boxes, tables, and slide order | Existing StudyBuddy parser and tests pass |
| PPTX conversion | MarkItDown 0.1.7 + `python-pptx` | Secondary document-to-Markdown path | Real generated PPTX -> Markdown smoke passed |
| PPTX image/scanned slides | Render slide then PaddleOCR | OCR only where native text is absent | Pending image-render/OCR integration smoke |

## ASR decision

`H:/WhisperCli` is the only canonical runtime. The copy under
`H:/studybuddy-composer/components/WhisperCli` is Composer evidence/input only;
it must not be configured as a second runtime.

Observed CLI contract:

- accepts audio files and supports Chinese language selection (`-l zh`)
- supports TXT, SRT, and VTT-style output modes
- supports CPU thread/process settings and bounded duration selection
- local test with `测试音频.mp3` produced TXT and SRT with exit code 0
- generated output was removed after the smoke; raw transcript is not committed

The existing `large-v3-turbo` model is large (~1.6 GB). Do not duplicate it or
copy it into StudyBuddy source. The future Formal adapter must enforce input
allowlist, timeout, cancellation, output limit, child-process cleanup, and
redacted evidence.

## TTS decision

Use `edge-tts==7.2.8` as the first TTS candidate because it has no purchased API
key requirement and exposes Chinese voices. It is not an offline engine: it
uses Microsoft's Edge online speech service. Therefore:

- it is an explicit user action only, never an implicit StudyBuddy background call;
- the generated audio is an artifact, not a learning fact or citation source;
- no credentials, raw service response, or full sensitive report text enters logs;
- network use must be opt-in in Composer smoke and must not be treated as B4 delivery;
- if a fully offline requirement appears, evaluate Piper/Kokoro separately rather
  than silently replacing Edge TTS.

## OCR decision

PaddleOCR is the primary candidate for Chinese text, printed documents, layout,
tables, and image/scanned PPT slides. RapidOCR ONNX is the lightweight fallback
for environments where Paddle's larger dependency/model footprint is unsuitable.
Tesseract remains a compatibility fallback only; it is not the primary Chinese
quality target.

Neither Python package import nor model installation is a B2 smoke pass. The
next Composer smoke must use synthetic non-sensitive images and cover clear
Chinese/English text, blank, corrupt, oversized, unsupported, timeout,
malformed output, repeat, cleanup, bounded output, and no raw-image/full-text
logging.

## PPTX decision

Use a layered pipeline:

1. Extract native slide text and tables using the StudyBuddy `formal-pptx`
   parser / `python-pptx`, preserving slide order and source spans.
2. Use MarkItDown for a consistent Markdown conversion surface and cross-format
   smoke.
3. For image-only, scanned, or text-in-image slides, render the slide and send
   the rendered image through the PaddleOCR candidate.

Native PPTX text extraction is not OCR. OCR output remains draft-first and
requires user confirmation before it becomes a normal material/revision source.

## StudyBuddy gate boundary

The current Formal system remains within the approved Phase 9D scope:

deterministic fake/loopback OCR/ASR -> transcript/OCR draft -> explicit user
confirmation -> material/revision/chunk/retrieval/citation.

Real WhisperCli, PaddleOCR/RapidOCR, and Edge TTS are Composer candidates until
B1/B2 and the relevant integration/formal gates pass. TTS is not in the approved
Phase 9D business scope. No package installation changes this status.

## Reproducible environment facts

- Python: `C:/miniconda/py310/python.exe`
- `edge-tts`: 7.2.8
- `paddleocr`: 3.7.0
- `paddlepaddle`: 3.3.1
- `rapidocr_onnxruntime`: 1.4.4
- `markitdown`: 0.1.7
- `python-pptx`: installed
- `H:/WhisperCli`: canonical local ASR runtime

No real user audio/image/report content was used in the smoke evidence.
