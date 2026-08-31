# B3 Report C0 Decision and C1 Smoke Plan

> Status: `candidate-selected / researching`.
> This freezes the Composer candidate boundary; it is not C1 evidence, Integration approval, or Formal authorization.

## C0 decision

The selected first candidate is an independently reimplemented, local deterministic report projection core. It must consume synthetic allowlisted facts and emit a fixed safe projection plus deterministic JSON and Markdown. It must not read or copy the legacy implementation into Formal.

The legacy reference mixes projection with delivery deduplication, email/Feishu formatting, and optional AI narrative. Those concerns are excluded from B3 because delivery belongs to B4 and generated narrative has no frozen privacy/citation contract.

First-scope formats are JSON and Markdown only. PDF is excluded from C1 because no fixed layout, renderer isolation, font embedding, output-resource, accessibility, or privacy evidence exists. HTML/email, Feishu cards, AI summaries, delivery state, real recipients, webhooks, network access, and scheduler/task execution are also excluded.

## Frozen input/output boundary

Inputs are synthetic, bounded, structured facts for `daily`, `weekly`, `monthly`, and `exam_alert`, with an IANA timezone and half-open date period. Fields are allowlisted counts, durations, status buckets, source-quality buckets, and exam proximity buckets. Source body text, answers, prompts, transcript/OCR text, local paths, credentials, SQL, and arbitrary JSON are forbidden.

Output contains a fixed version, normalized period, safe aggregate sections, quality flags, deterministic fingerprint, and deterministic JSON/Markdown serialization. Ordinary evidence records only stable statuses, counts, sizes, timings, hashes, and error codes, never report bodies.

## C1 smoke matrix

1. Empty projection for all four report kinds.
2. Normal synthetic projection with stable allowlisted aggregates.
3. IANA timezone and half-open period boundary; invalid timezone/date/range rejection.
4. `valid`, `stale`, `source_deleted`, and `source_unavailable` buckets without source identity leakage.
5. Stable ordering, repeat-call equality, fingerprint equality, and input-order independence.
6. JSON schema/key allowlist, deterministic Markdown, Unicode safety, and 1 MiB output limit.
7. Unsupported kind/format, malformed fact, negative/overflow count, arbitrary field, corrupt output, timeout, and oversized output failures.
8. Empty/no-op cleanup, controlled temporary directory, bounded runtime, and no residual exports.
9. Network denial with socket/HTTP guards; no implicit download or subprocess requirement.
10. Privacy scan over stdout/stderr/evidence for source text, report body, local paths, credentials, raw exceptions, and database statements.
11. Resource summary: wall time, peak working set, output bytes, and temporary-file count.

## Promotion rule

`report-core` remains `researching` until all C1 checks pass with sanitized evidence. C1 does not authorize Integration or Formal. C2 must combine the selected semantics with isolated StudyBuddy facts, project scope, source lifecycle, snapshot idempotency, and backup/restore non-repair. B3 never authorizes B4 delivery.
