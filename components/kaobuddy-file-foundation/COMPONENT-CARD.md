# Component Card: kaobuddy-file-foundation

- Source: KaoBuddy `src/fileReaders.ts`, `src/legacyDoc.ts`, `src/App.tsx`, and `backend/app/video.py`.
- License: KaoBuddy repository declares MIT.
- Fixed libraries: `pdfjs-dist 4.10.38`, `mammoth 1.12.0`, `jszip 3.10.1`, `tsx 4.22.4`.
- Independent smoke command: generate fixtures with `python generate_fixtures.py`; run `npm ci && npm run smoke` in this directory.
- Real input: synthetic TXT, Markdown, Chinese text, PDF, DOCX, RTF, PPTX, legacy-DOC-like bytes, image, empty files, and corrupt containers under `H:/studybuddy-test/fixtures/kaobuddy-foundation`.
- Output contract: extracted text or explicit parse error in `H:/studybuddy-test/artifacts/kaobuddy-foundation/latest.json`.
- Scope: dependency-level extraction using KaoBuddy algorithms. It is not a browser UI upload/user-path pass.
- Verified: TXT, Markdown, Chinese UTF-8 text, text-layer PDF with page marker, DOCX body, RTF body, PPTX body in slide order, and heuristic legacy DOC output.
- Verified failures: corrupt PDF/DOCX/PPTX reject; empty RTF/PPTX and unusable DOC reject. Empty TXT/Markdown are silently accepted. Empty text-layer PDF is accepted by App fallback behavior, not rejected.
- Important finding: legacy DOC output included garbled prefix text. This is byte-decoding heuristics, not an OLE Compound File parser, and is unsuitable as a formal reliable DOC parser.
- Original-file retention: ordinary files retain filename plus extracted text only; original bytes are not stored. Handwriting images are retained as data URLs in IndexedDB. No local file copy is created.
- Display: material library only renders title and delete control; extracted material body is not directly viewable there.
- Browser/network: TXT/Markdown/DOCX/RTF/DOC/PPTX use browser File APIs; PDF additionally uses browser worker/canvas for `readPdfForAi`. Local parsing does not require network after assets are installed. Image OCR requires a configured multimodal AI provider. Video URL import runs in FastAPI and requires network/public page/subtitle availability.
- Migration assessment: TXT/Markdown can move trivially; PDF/DOCX/PPTX should be reimplemented behind FastAPI server-side adapters; RTF needs a real parser; DOC needs replacement/conversion; PPT is unsupported; image OCR/ASR are separate components; URL import needs SSRF, domain, timeout, and content-size controls.
- Windows prerequisites: Node/npm for this smoke. Installed dependencies consumed about 93 MB and were removed after testing; lock file remains for reproducibility.
- Smoke result: `smoke_passed` at parser/dependency level with findings; browser UI path remains `not_verified`.
- Integration result: `not started`
- Evidence path: `H:/studybuddy-test/artifacts/kaobuddy-foundation/latest.json`
