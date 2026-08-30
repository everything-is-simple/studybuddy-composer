# B0 Component Governance

> Updated: 2026-08-30
> Status: governance scaffolded; candidate smoke and Integration are pending.

## Purpose

B0 establishes one auditable intake contract for ASR, OCR, report, and delivery candidates before any real capability is implemented in StudyBuddy. The catalog is not a pass list. Every candidate currently remains `researching`; no B0 record authorizes import into `H:/studybuddy` or `H:/studybuddy-integration`.

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

- ASR: 3 candidates (`researching`)
- OCR: 3 candidates (`researching`)
- Report: 1 candidate (`researching`)
- Delivery: 2 candidates (`researching`)

## B0 completion checklist

- [x] Four capability categories have explicit candidate records.
- [x] Every candidate has a metadata-only component card.
- [x] Status vocabulary and promotion rules are frozen.
- [x] Network-off, temp-directory, timeout, output-limit, cleanup, and privacy rules are frozen.
- [x] Large binary/model/archive ignore rules are documented and applied to future artifacts.
- [ ] Independent smoke has passed for the selected candidates.
- [ ] Integration has passed for the selected candidates.
- [ ] Formal contracts and adapters have been separately approved.

B0 is therefore **scaffolded but not closed**.
