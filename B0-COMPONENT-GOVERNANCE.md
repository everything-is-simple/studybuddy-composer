# B0 Component Governance

> Updated: 2026-08-30
> Status: governance scaffolded; selected candidate smoke and isolated Integration evidence are recorded where stated.

## Purpose

B0 establishes one auditable intake contract for ASR, OCR, report, and delivery candidates before any real capability is implemented in StudyBuddy. The official ASR 1.12.0, PaddleOCR, and `report-core` candidates are `integration_passed`; five candidates remain `researching` and RapidOCR is `smoke_passed`. C1/C2 use the public `SampleClips/jfk.wav` fixture where applicable; official release asset hash comparison remains not_verified. No B0 record authorizes import into `H:/studybuddy`.

## Required record

Every candidate must have a `COMPONENT-CARD.md` and a catalog record containing: source, exact version or revision, license, artifact hash, owner boundary, independent smoke command, deterministic or explicitly authorized fixture, output contract, failure boundaries, Windows prerequisites, resource measurements, network policy, cleanup behavior, privacy/logging restrictions, smoke evidence, and Integration evidence.

## Status transitions

`researching` → `smoke_passed` only after the independent Composer command passes with sanitized evidence.

`smoke_passed` → `integration_passed` only after isolated Integration evidence combines the candidate with the relevant local storage, lifecycle, task/operation, backup/restore, and failure boundaries.

`rejected` is final for the current evaluation and must include a stable rejection reason.

`integration_passed` does not automatically authorize Formal adoption; Formal must reimplement or assemble against a verified contract and run its own gates.

## Common safety contract

- Network is disabled by default. Smoke uses loopback/fake receivers only.
- Use a controlled temporary directory, bounded runtime, bounded output, and guaranteed child-process cleanup.
- Do not commit models, archives, executables, credentials, real source material, generated results, or raw provider/tool output.
- Evidence may contain stable codes, booleans, counts, sizes, timings, versions, and hashes, but not secrets, absolute private paths, source text, audio, images, transcripts, report bodies, or raw stderr.
- OCR/ASR/report outputs remain drafts or projections until the later Formal contract explicitly defines confirmation and lifecycle behavior.
- Delivery remains `off`; dry-run is never reported as sent; live delivery is out of scope for B0.

## Current catalog

The machine-readable source of truth is [`manifests/b0-catalog.json`](manifests/b0-catalog.json). Current candidate counts:

- ASR: 1 selected candidate (`integration_passed`) and 2 alternatives (`researching`); the selected candidate is `Const-me/Whisper 1.12.0`, while FunASR/SenseVoice remain unselected alternatives.
- OCR: PaddleOCR has `integration_passed` and RapidOCR ONNX has `smoke_passed`, each only for its exact local package/model scope; PaddleOCR uses PP-OCRv5_server_det/rec from the PaddleX official inference host. Neither has Formal authorization; CapsWriter remains a fit-assessment record, not a primary path.
- Report: `report-core` has `integration_passed` only for its independent synthetic 9A-9D-shaped SQLite scope, snapshot idempotency, source lifecycle, and backup/restore non-repair. JSON/Markdown projection only; PDF/AI/delivery remain excluded and Formal authorization is absent.
- Delivery: 2 candidates (`researching`)

## B0 completion checklist

- [x] Four capability categories have explicit candidate records.
- [x] Every candidate has a metadata-only component card.
- [x] Status vocabulary and promotion rules are frozen.
- [x] Network-off, temp-directory, timeout, output-limit, cleanup, and privacy rules are frozen.
- [x] Large binary/model/archive ignore rules are documented and applied to future artifacts.
- [x] Independent C1 smoke is complete for RapidOCR, PaddleOCR, and `report-core` in their declared local scopes; delivery candidates remain pending.
- [x] C2 Integration has passed for the selected ASR candidate, PaddleOCR, and `report-core`; RapidOCR and delivery Integration remain pending.
- [x] B3 report C0 audit/scope and independent C1/C2 evidence are complete; Formal contract/adoption work remains separate and pending.
- [ ] Formal contracts and adapters have been separately approved.

B0 is therefore **scaffolded but not closed**.
