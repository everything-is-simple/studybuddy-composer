# Next Phase Execution Plan

This plan remains before S1-S7 product reconstruction. It converts the audit into integration-ready component contracts.

## Gate A: Evidence Closure

1. Review and commit Composer cards, synthetic fixtures, sanitized artifacts, and dependency locks. Exclude `node_modules`, `.venv`, databases with user content, and secrets.
2. Update `initial-catalog.json` only after review: set `sqlite-local` to `smoke_passed`; keep document conversion and provider overall at `researching` because their required product boundaries are incomplete.
3. Add artifact schema fields shared by all smokes: component version, source identity, command, runtime, start/end time, result, limitations, and credential/network declaration.

Exit: every claim links to reproducible evidence and no status exceeds its evidence layer.

## Gate B: Backend File Parser Trials

Create separate Composer components for `text-ingest`, `pdf-text`, `docx-text`, and `pptx-text`. Do not copy KaoBuddy implementations.

Required contract:

```text
input: local fixture path + declared media type
output: source hash, original filename, parser/version, structured page or slide spans,
        normalized full text, warnings, empty-content classification, elapsed time
```

Required tests: current fixtures; Chinese text; encoding mismatch; zero bytes; malformed containers; oversize/zip-bomb limits; timeout; duplicate hash; restart reproducibility. Preserve original fixture copies in the isolated test run. RTF and legacy DOC/PPT remain rejected until dedicated converters pass independent security/resource tests.

Exit: each parser is independently `smoke_passed`; extracted body is inspectable and numbering is structured.

## Gate C: Durable Storage Contract

Use SQLite smoke results to design migrations and a repository contract, still in Composer/Integration:

- project, material, material_file, extraction, page_span, knowledge_module minimum schema;
- foreign keys, uniqueness, transaction boundaries, timestamps, schema version;
- WAL checkpoint/backup behavior, busy timeout, one-writer policy;
- backup during active reads/writes, corrupt-copy detection, restore to a new run root;
- filesystem layout and atomic original-file placement.

Exit: restart readback, integrity check, backup/restore, and parser-output persistence pass under `H:/studybuddy-test`.

## Gate D: Provider Adapter Hardening

Reimplement a small provider adapter contract in Composer without importing KaoBuddy:

- preserve upstream status category (auth, forbidden, rate limit, provider, timeout, protocol);
- wrap invalid JSON;
- require `[DONE]` or an explicit transport completion policy for SSE;
- define partial-stream failure output;
- redact upstream bodies and never log prompts/full outputs/API keys;
- expose optional usage without inventing cost;
- move DeepSeek quirks into explicit provider capability configuration;
- store credentials outside SQLite exports and define Windows secret-storage decision.

Run the same offline cases through adapter API and a visible test client. Real provider remains a separately authorized test with provider/time/cost summary only.

Exit: offline protocol `smoke_passed`, then local provider + SQLite composition in Integration.

## Gate E: Launch Shell Trial

Define a StudyBuddy development launch command that never installs on every start. Separate commands for bootstrap, build, dev, and production launch. Verify:

- clean preflight reports missing dependencies without modifying the machine;
- backend health and frontend asset existence;
- occupied ports and stale processes;
- browser page loads with nonblank root and no missing assets;
- shutdown leaves no child process;
- all run data points to `H:/studybuddy-test/runs/...`.

Exit: desktop browser and narrow viewport screenshots/DOM plus restart readback. This is the first point at which launch may be marked real-pass.

## First Integration Slice

Only after Gates B-D pass independently:

```text
UI file picker -> FastAPI upload -> retained synthetic original -> extraction
-> SQLite transaction -> UI material detail showing extracted body/page spans
-> restart -> same body visible -> backup -> restore -> same body visible
```

No AI generation is needed in this first slice. After it passes, add local offline provider request -> structured result -> SQLite persistence -> restart readback. Formal `H:/studybuddy` implementation begins only after these integration paths pass and is newly implemented against the approved contracts.
