# KaoBuddy File Capability Matrix

Evidence labels: `real-library-pass`, `real-library-fail`, `code-only`, `external-not-verified`.

| Format | Implementation / library | Input -> output | Numbering | Original retained | Empty / corrupt behavior | Network / browser | FastAPI migration | Evidence |
|---|---|---|---|---|---|---|---|---|
| TXT | `fileReaders.ts: readTextFile`; `File.text()` | file picker -> raw string | No | No; filename + text only | Empty silently succeeds; arbitrary bytes may decode with replacement | Browser File API; offline | Reimplement with encoding detection, limits, and explicit empty policy | `real-library-pass` incl. Chinese and empty |
| Markdown | same as TXT; extension only sets kind | file picker -> raw Markdown string | No | No | Same as TXT; no Markdown parse/sanitize at import | Browser File API; offline | Reimplement as text ingestion; preserve raw + normalized text separately | `real-library-pass` incl. empty |
| PDF | `readPdfText`; `pdfjs-dist` | file picker -> `第 N 页` text blocks | Yes, generated page labels | No | Corrupt rejects; empty text layer is saved with fallback message | Browser arrayBuffer + PDF worker; local | Reimplement server-side; preserve page spans and original file; scanned PDF is separate OCR path | `real-library-pass`; corrupt `real-library-fail` |
| DOCX | `readDocumentText`; `mammoth.extractRawText` | file picker -> `Word 正文` + body/warnings | No | No | Empty body explicitly rejects; corrupt ZIP rejects | Browser arrayBuffer; local | Suitable conceptually, but use backend library/process and preserve source structure metadata | `real-library-pass`; empty/corrupt fail verified |
| RTF | `stripRtf`; regex | file picker -> `RTF 正文` + stripped text | No | No | Empty rejects; malformed RTF may silently produce bad text | Browser text decode; local | Must replace with a real RTF parser or conversion service | body pass and empty fail verified; corruption robustness unproven |
| PPTX | `readPresentationText`; `jszip` + XML regex | file picker -> `PPT 正文`, `第 N 页` blocks | Yes, generated slide labels | No | No slides/body rejects; corrupt ZIP rejects | Browser arrayBuffer; local | Reimplement backend parser preserving slide number; consider notes/tables/order | `real-library-pass`; empty/corrupt fail verified |
| legacy DOC | `legacyDoc.ts`; UTF-16LE/UTF-8 heuristic | file picker -> guessed text | No | No | Empty-like bytes reject; real OLE structure is not parsed; false positives/garbling | Browser TextDecoder; local | Replace completely with controlled LibreOffice/antiword conversion or reject | `real-library-pass-with-garbling`; reliability rejected |
| legacy PPT | explicit error in `readPresentationText` | file picker -> error | No | No | Always rejects before parsing | Browser only; offline | Add controlled conversion or reject with guidance | `code-only`, intentionally unsupported |
| image | `readAsDataUrl` -> `/api/ocr/handwriting` -> multimodal provider | image picker -> base64 data URL -> AI text | No | Yes, base64 in IndexedDB for handwriting | No local image validation beyond browser; empty AI rejected downstream | Browser FileReader + backend + external AI network | Separate OCR adapter; do not couple to generic chat provider | `external-not-verified`; fixture exists only |
| handwriting PDF | `readPdfText` only in `handleHandwriting` | PDF -> text layer, no rendered-page OCR | Yes | No | Scanned/no-text PDF becomes fallback text | Browser PDF worker; no AI for PDF pages in current UI | Reimplement PDF text + OCR routing | `code-only`; ordinary text-layer PDF tested |
| video subtitle / URL | `api.ts importVideo` -> FastAPI `video.py` using `httpx`, HTML regex, public subtitle JSON | URL -> title/description/subtitles/warnings | No timestamp retention | Source URL retained; video not downloaded | Missing subtitles returns warnings; HTTP/parse route errors become 502 | Requires network; no browser parser | Reimplement with domain allowlist/SSRF guard, size cap, redirects policy, provenance and timestamps | `external-not-verified` by instruction |
| ODT | accepted by UI and routed to `readDocumentText` | picker -> unsupported-format error | No | No | Always fails because implementation has no ODT branch | Browser | Remove from accept list or implement explicitly | `code-only` mismatch |

## Cross-cutting Findings

- KaoBuddy stores extracted text, not original ordinary files. This cannot satisfy a formal local-file evidence model without redesign.
- The material library does not display extracted body. Users cannot inspect extraction quality from the material list.
- PDF/PPTX labels preserve page/slide position only as text prefixes; there is no structured page-span schema.
- Parser exceptions appear in upload queue. Successful empty TXT/Markdown and textless PDF do not block import.
- No file-size limit, MIME sniffing, hash, duplicate detection, encoding selection, archive bomb protection, or extraction timeout is present in the reviewed import path.
