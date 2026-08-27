# Component Card: backend-file-parsers

- Source: newly reimplemented StudyBuddy Composer adapter; behavior informed by the KaoBuddy audit only. No reference source is imported.
- License: project-owned test implementation; dependencies retain their upstream licenses.
- Version: `1.0.0`.
- Runtime: `C:\miniconda\py310\python.exe` in the component `.venv`.
- Dependencies: `pydantic==2.12.5`, `pypdf==6.4.2`, `python-docx==1.2.0`, `pytest==8.4.2`.
- Command: `H:\studybuddy-composer\components\backend-file-parsers\.venv\Scripts\python.exe smoke.py`.
- Contract: `parse_file(Path, declared_media_type, ParseOptions) -> ParseResult`; SHA-256, parser identity, status, text, page/slide spans, warnings and error code are returned.
- Verified fixtures: synthetic TXT, Markdown, Chinese TXT, empty TXT, PDF, DOCX, PPTX, corrupt containers, RTF and legacy DOC/PPT.
- Decisions: RTF returns `rejected/unsupported_rtf`; legacy DOC/PPT return `rejected/requires_converter`. No fake decode path is provided.
- Security/resource limits: 10 MiB source limit, ZIP member/count/expanded-size/compression-ratio checks. No network and no full body logging/stdout.
- Windows limits: PDF text extraction requires a text layer; OCR, legacy conversion and crash recovery are not covered. DOCX paragraph extraction excludes complex embedded/text-box content.
- Original retention: parser does not copy files; Integration owns retained originals.
- Result: `smoke_passed` after real fixture execution; evidence in `H:\studybuddy-test\artifacts\backend-file-parsers\latest.json`.
- Integration: `integration_passed` for `H:\studybuddy-integration\file-storage-foundation\run_integration.py`; the synthetic composition verifies parser output → retained originals → SQLite persist/reopen → rollback → backup/restore. This does not approve OCR, legacy conversion, or direct formal-system imports.
