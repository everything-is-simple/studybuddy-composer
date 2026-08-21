"""Deterministic chunker for StudyBuddy Composer.

This is a Composer-only feasibility component. It does NOT touch the formal
StudyBuddy SQLite schema, FTS5, or any provider. It consumes an extraction
contract (full text + page/slide spans, exactly as produced by the
`backend-file-parsers` adapter) and emits deterministic chunks aligned to the
formal `chunks` / `chunk_spans` column set defined in
`H:/studybuddy/backend/app/migrations/runner.py` (`_create_ai_schema`).

Design invariants (verified by smoke.py):

* offsets are Python Unicode code-point indices (NOT byte offsets);
* the chunker never crosses a span boundary: each chunk maps to exactly one
  span, even when the target window is larger than a span;
* empty extraction yields zero chunks;
* identical ``(extraction_sha256, revision_fingerprint, spans, config,
  strategy, chunking_version)`` reproduces byte-identical chunks across
  processes.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from typing import Literal

SpanKind = Literal["document", "page", "slide"]
Status = Literal["ready"]
Strategy = Literal["codepoint-window-v1"]

CHUNKING_VERSION = "1.0.0"
DEFAULT_STRATEGY: Strategy = "codepoint-window-v1"
SEPARATOR = "\n\n"


@dataclass(frozen=True)
class TextSpan:
    """A single page/slide/document span from the parser adapter.

    Matches `backend_file_parsers.TextSpan`: ``text`` is the span body and
    the extraction ``text`` is ``"\\n\\n".join(span.text for span in spans)``.
    """

    ordinal: int
    kind: SpanKind
    label: str
    text: str


@dataclass(frozen=True)
class ChunkInput:
    """Derived extraction input consumed by the chunker.

    ``revision_fingerprint`` is a placeholder produced by the (not-yet-built)
    ``material_revisions`` layer in the formal system. Here it is a synthetic
    deterministic string; it is part of the determinism input.
    """

    extraction_id: str
    extraction_sha256: str
    revision_fingerprint: str
    text: str
    spans: tuple[TextSpan, ...]


@dataclass(frozen=True)
class ChunkSpanLink:
    """Link from a chunk to the span it covers.

    ``overlap_start`` / ``overlap_end`` are code-point offsets RELATIVE to
    ``span.text`` (not relative to the extraction text). This reference frame
    is chosen so a citation renderer can locate "the slice on page N" without
    recomputing the global span position. The global extraction offsets are
    carried on the chunk itself (``start_offset`` / ``end_offset``).
    """

    span_ordinal: int
    overlap_start: int
    overlap_end: int


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    text: str
    normalized_text: str
    start_offset: int
    end_offset: int
    token_count_estimate: int
    overlap_before: int
    overlap_after: int
    strategy: str
    chunking_version: str
    status: Status
    error_code: str | None
    spans: tuple[ChunkSpanLink, ...]
    chunk_id: str


@dataclass(frozen=True)
class ChunkerConfig:
    target_codepoints: int = 500
    overlap_codepoints: int = 50
    hard_max_codepoints: int = 2000
    strategy: str = DEFAULT_STRATEGY
    chunking_version: str = CHUNKING_VERSION


def _is_cjkish(char: str) -> bool:
    """True for wide / fullwidth / ambiguous East-Asian characters.

    These are counted as one token each; everything else is word-split.
    Uses ``unicodedata.east_asian_width`` so CJK ideographs, fullwidth
    punctuation and CJK-compatible forms are all handled deterministically.
    """
    return unicodedata.east_asian_width(char) in ("W", "F", "A")


def estimate_tokens(text: str) -> int:
    """Deterministic token-count estimate.

    Algorithm: each wide/fullwidth/ambiguous East-Asian character counts as
    one token; the remaining characters are split on whitespace and each
    non-empty token counts as one. No external tokenizer is used.
    """
    cjk = 0
    non_cjk_chars: list[str] = []
    for char in text:
        if _is_cjkish(char):
            cjk += 1
            non_cjk_chars.append(" ")
        else:
            non_cjk_chars.append(char)
    words = "".join(non_cjk_chars).split()
    return cjk + len(words)


def normalize_text(text: str) -> str:
    """Deterministic normalization used for the future chunk FTS5 index.

    ``NFKC`` normalization followed by whitespace folding (any run of
    whitespace -> a single space) and ``strip()``. This is a pure function of
    ``text`` and does not affect reconstruction (which uses raw ``chunk.text``).
    """
    nfkc = unicodedata.normalize("NFKC", text)
    return " ".join(nfkc.split())


def _segment_span(
    span_text: str, target: int, overlap: int, hard_max: int
) -> list[tuple[int, int]]:
    """Split one span's text into ``(local_start, local_end)`` code-point
    segments using a window + overlap. Never returns an empty segment.

    If ``span_text`` is empty, returns ``[]``. If the span fits in one window,
    returns a single segment covering the whole span.
    """
    n = len(span_text)
    if n == 0:
        return []
    window = min(target, hard_max)
    if window < 1:
        window = 1
    if overlap < 0:
        overlap = 0
    if overlap >= window:
        # Overlap must be strictly smaller than the window so the step stays
        # positive and progress is guaranteed.
        overlap = 0
    step = window - overlap
    if step < 1:
        step = 1
    segments: list[tuple[int, int]] = []
    pos = 0
    while pos < n:
        end = min(pos + window, n)
        segments.append((pos, end))
        if end >= n:
            break
        next_pos = pos + step
        if next_pos <= pos:
            # Defensive guard against non-progressing loops.
            next_pos = pos + 1
        pos = next_pos
    return segments


def _global_span_starts(spans: tuple[TextSpan, ...]) -> list[int]:
    """Return the code-point offset of each span inside the extraction text.

    The extraction text is ``"\\n\\n".join(span.text)`` so a span is followed
    by ``len(SEPARATOR)`` separator code points before the next span.
    """
    starts: list[int] = []
    pos = 0
    for span in spans:
        starts.append(pos)
        pos += len(span.text) + len(SEPARATOR)
    return starts


def chunk(input: ChunkInput, config: ChunkerConfig = ChunkerConfig()) -> list[Chunk]:
    """Produce deterministic chunks from an extraction.

    Returns ``[]`` for empty extraction text. Each chunk maps to exactly one
    span; long spans are split internally with overlap, short spans become a
    single chunk. Adjacent chunks within a span share overlap; adjacent chunks
    across spans do not overlap (the ``"\\n\\n"`` separator is never part of a
    chunk but is restored by the reconstruction invariant, see smoke.py).
    """
    if not input.text:
        return []

    global_starts = _global_span_starts(input.spans)
    chunks: list[Chunk] = []
    chunk_index = 0

    for span_idx, span in enumerate(input.spans):
        segments = _segment_span(
            span.text,
            config.target_codepoints,
            config.overlap_codepoints,
            config.hard_max_codepoints,
        )
        if not segments:
            continue
        g_start = global_starts[span_idx]
        prev_overlap_after = 0
        for seg_i, (local_start, local_end) in enumerate(segments):
            text = span.text[local_start:local_end]
            start_offset = g_start + local_start
            end_offset = g_start + local_end
            if seg_i < len(segments) - 1:
                next_local_start = segments[seg_i + 1][0]
                overlap_after = local_end - next_local_start
                if overlap_after < 0:
                    overlap_after = 0
            else:
                overlap_after = 0
            overlap_before = prev_overlap_after
            chunk_id = (
                "chunk_"
                + hashlib.sha256(
                    (input.revision_fingerprint + ":" + str(chunk_index)).encode(
                        "utf-8"
                    )
                ).hexdigest()[:16]
            )
            chunks.append(
                Chunk(
                    chunk_index=chunk_index,
                    text=text,
                    normalized_text=normalize_text(text),
                    start_offset=start_offset,
                    end_offset=end_offset,
                    token_count_estimate=estimate_tokens(text),
                    overlap_before=overlap_before,
                    overlap_after=overlap_after,
                    strategy=config.strategy,
                    chunking_version=config.chunking_version,
                    status="ready",
                    error_code=None,
                    spans=(
                        ChunkSpanLink(
                            span_ordinal=span.ordinal,
                            overlap_start=local_start,
                            overlap_end=local_end,
                        ),
                    ),
                    chunk_id=chunk_id,
                )
            )
            prev_overlap_after = overlap_after
            chunk_index += 1

    return chunks


def serialize_chunks(chunks: list[Chunk]) -> list[dict[str, object]]:
    """Stable, privacy-safe serialization for determinism hashing.

    Chunk body text is never serialized; only a sha256 of the (normalized)
    text is included so two chunk runs can be compared for equality without
    persisting source content.
    """
    out: list[dict[str, object]] = []
    for c in chunks:
        out.append(
            {
                "chunk_index": c.chunk_index,
                "text_sha256": hashlib.sha256(c.text.encode("utf-8")).hexdigest(),
                "normalized_text_sha256": hashlib.sha256(
                    c.normalized_text.encode("utf-8")
                ).hexdigest(),
                "start_offset": c.start_offset,
                "end_offset": c.end_offset,
                "token_count_estimate": c.token_count_estimate,
                "overlap_before": c.overlap_before,
                "overlap_after": c.overlap_after,
                "strategy": c.strategy,
                "chunking_version": c.chunking_version,
                "status": c.status,
                "error_code": c.error_code,
                "chunk_id": c.chunk_id,
                "spans": [
                    {
                        "span_ordinal": s.span_ordinal,
                        "overlap_start": s.overlap_start,
                        "overlap_end": s.overlap_end,
                    }
                    for s in c.spans
                ],
            }
        )
    return out


def determinism_sha256(chunks: list[Chunk]) -> str:
    """Stable hash of a chunk list for cross-run / cross-process comparison."""
    import json

    payload = json.dumps(
        serialize_chunks(chunks), sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
