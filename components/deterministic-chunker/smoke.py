"""Independent smoke test for the deterministic-chunker Composer component.

Runs 8 cases and asserts the 7 invariants below. Produces an artifact JSON at
``H:/studybuddy-test/artifacts/deterministic-chunker/latest.json`` (and a
per-run ``result.json``) plus a one-line stdout summary. Chunk body text is
never written to stdout or the artifact; only sha256 / counts / booleans are
recorded.

Invariants (every non-empty case asserts the applicable ones):
  offset_integrity       extraction.text[start:end] == chunk.text for all chunks
  contiguity_core        chunks (overlap removed) reconstruct the extraction text
  no_cross_span           every chunk maps to exactly one span
  span_coverage          every non-empty span's text is fully covered by its chunks
  overlap_consistency    adjacent chunks' overlap_before/after agree; first/last are 0
  determinism            same input -> same determinism_sha256 (in-process + cross-process)
  empty_yields_zero      empty extraction -> 0 chunks, status ready
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from deterministic_chunker import (  # noqa: E402
    SEPARATOR,
    Chunk,
    ChunkInput,
    ChunkerConfig,
    TextSpan,
    chunk,
    determinism_sha256,
)

ARTIFACT_DIR = Path(
    "H:/studybuddy-test/artifacts/deterministic-chunker"
)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT = ARTIFACT_DIR / "latest.json"

DEFAULT_CONFIG = ChunkerConfig()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_input(
    extraction_id: str,
    text: str,
    spans: tuple[TextSpan, ...],
    fingerprint: str | None = None,
) -> ChunkInput:
    return ChunkInput(
        extraction_id=extraction_id,
        extraction_sha256=sha256(text),
        revision_fingerprint=fingerprint or f"rev_{extraction_id}",
        text=text,
        spans=spans,
    )


def reconstruct_text(chunks: list[Chunk], spans: tuple[TextSpan, ...]) -> str:
    """Rebuild extraction.text from chunks by grouping per span and restoring
    the ``"\\n\\n"`` separators the chunker deliberately leaves unchunked."""
    by_span: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_span[c.spans[0].span_ordinal].append(c)
    parts: list[str] = []
    for i, span in enumerate(spans):
        if i > 0:
            parts.append(SEPARATOR)
        sc = by_span.get(span.ordinal, [])
        if sc:
            body = sc[0].text + "".join(c.text[c.overlap_before:] for c in sc[1:])
            parts.append(body)
    return "".join(parts)


def check_invariants(
    inp: ChunkInput,
    config: ChunkerConfig,
    *,
    expect_empty: bool = False,
    check_cross_process: bool = True,
) -> dict[str, object]:
    chunks = chunk(inp, config)
    inv: dict[str, object] = {}

    # offset_integrity: extraction.text[start:end] == chunk.text
    inv["offset_integrity"] = all(
        inp.text[c.start_offset : c.end_offset] == c.text for c in chunks
    )

    # contiguity_core: overlap-removed reconstruction == extraction.text
    reconstructed = reconstruct_text(chunks, inp.spans)
    inv["contiguity_core"] = reconstructed == inp.text

    # no_cross_span: each chunk maps to exactly one span
    inv["no_cross_span"] = all(len(c.spans) == 1 for c in chunks)

    # span_coverage: every non-empty span fully covered by its chunks
    coverage_ok = True
    by_span: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_span[c.spans[0].span_ordinal].append(c)
    for span in inp.spans:
        if not span.text:
            continue
        sc = by_span.get(span.ordinal, [])
        if not sc:
            coverage_ok = False
            break
        body = sc[0].text + "".join(c.text[c.overlap_before:] for c in sc[1:])
        if body != span.text:
            coverage_ok = False
            break
    inv["span_coverage"] = coverage_ok

    # overlap_consistency: adjacent agree, first/last are 0
    overlap_ok = True
    for i, c in enumerate(chunks):
        if c.overlap_before != (chunks[i - 1].overlap_after if i > 0 else 0):
            overlap_ok = False
            break
    if chunks:
        if chunks[0].overlap_before != 0 or chunks[-1].overlap_after != 0:
            overlap_ok = False
    inv["overlap_consistency"] = overlap_ok

    # determinism (in-process: run twice)
    det1 = determinism_sha256(chunk(inp, config))
    det2 = determinism_sha256(chunk(inp, config))
    inv["determinism_inproc"] = det1 == det2

    # determinism (cross-process)
    if check_cross_process:
        inv["determinism_crossproc"] = det1 == _cross_process_hash(inp, config)
    else:
        inv["determinism_crossproc"] = True

    inv["determinism_sha256"] = det1

    # empty_yields_zero
    if expect_empty:
        inv["empty_yields_zero"] = len(chunks) == 0

    inv["chunk_count"] = len(chunks)
    inv["all_ready"] = all(c.status == "ready" and c.error_code is None for c in chunks)
    return inv


def _cross_process_hash(inp: ChunkInput, config: ChunkerConfig) -> str:
    """Run the chunker in a fresh Python process with the same input and
    return its determinism_sha256, proving cross-process reproducibility."""
    payload = {
        "extraction_id": inp.extraction_id,
        "extraction_sha256": inp.extraction_sha256,
        "revision_fingerprint": inp.revision_fingerprint,
        "text": inp.text,
        "spans": [
            {
                "ordinal": s.ordinal,
                "kind": s.kind,
                "label": s.label,
                "text": s.text,
            }
            for s in inp.spans
        ],
        "config": {
            "target_codepoints": config.target_codepoints,
            "overlap_codepoints": config.overlap_codepoints,
            "hard_max_codepoints": config.hard_max_codepoints,
            "strategy": config.strategy,
            "chunking_version": config.chunking_version,
        },
    }
    script = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        "from deterministic_chunker import ("
        "ChunkInput, TextSpan, ChunkerConfig, chunk, determinism_sha256)\n"
        "data = json.loads(sys.stdin.read())\n"
        "spans = tuple(TextSpan(**s) for s in data['spans'])\n"
        "inp = ChunkInput(extraction_id=data['extraction_id'],"
        "extraction_sha256=data['extraction_sha256'],"
        "revision_fingerprint=data['revision_fingerprint'],"
        "text=data['text'], spans=spans)\n"
        "cfg = ChunkerConfig(**data['config'])\n"
        "sys.stdout.write(determinism_sha256(chunk(inp, cfg)))\n"
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    if proc.returncode != 0:
        return "SUBPROCESS_FAILED:" + proc.stderr[:200]
    return proc.stdout.strip()


def build_cases() -> list[tuple[str, ChunkInput, ChunkerConfig, dict[str, bool]]]:
    """Return (name, input, config, flags) for the 8 smoke cases."""
    cases: list[tuple[str, ChunkInput, ChunkerConfig, dict[str, bool]]] = []

    # 1. empty
    cases.append(
        (
            "empty",
            make_input("ex_empty", "", ()),
            DEFAULT_CONFIG,
            {"expect_empty": True, "check_cross_process": False},
        )
    )

    # 2. chinese_offset: CJK heavy text with fullwidth punctuation, emoji, combining marks
    chinese_text = (
        "进程是资源分配的基本单位。线程是ＣＰＵ调度的最小单位。\U0001F600 "
        "全角：ＡＢＣ１２３；组合字：e\u0301；标点「」『』，、。；"
    )
    cases.append(
        (
            "chinese_offset",
            make_input(
                "ex_chinese",
                chinese_text,
                (TextSpan(1, "document", "doc-chinese", chinese_text),),
            ),
            ChunkerConfig(target_codepoints=20, overlap_codepoints=4, hard_max_codepoints=100),
            {},
        )
    )

    # 3. page_boundary: multiple pages, window smaller than a single page
    page_cfg = ChunkerConfig(target_codepoints=20, overlap_codepoints=4, hard_max_codepoints=100)
    p1 = "第1页内容段落" * 8  # length 48
    p2 = "第二页正文片段" * 8  # length 48
    p3 = "第三页结尾说明" * 8  # length 48
    page_text = SEPARATOR.join([p1, p2, p3])
    cases.append(
        (
            "page_boundary",
            make_input(
                "ex_pages",
                page_text,
                (
                    TextSpan(1, "page", "page-1", p1),
                    TextSpan(2, "page", "page-2", p2),
                    TextSpan(3, "page", "page-3", p3),
                ),
            ),
            page_cfg,
            {},
        )
    )

    # 4. slide_boundary: multiple slides, window smaller than a single slide
    s1 = "幻灯片一标题与要点说明" * 6  # length 60
    s2 = "幻灯片二补充内容要点" * 6  # length 60
    slide_text = SEPARATOR.join([s1, s2])
    cases.append(
        (
            "slide_boundary",
            make_input(
                "ex_slides",
                slide_text,
                (
                    TextSpan(1, "slide", "slide-1", s1),
                    TextSpan(2, "slide", "slide-2", s2),
                ),
            ),
            ChunkerConfig(target_codepoints=25, overlap_codepoints=5, hard_max_codepoints=100),
            {},
        )
    )

    # 5. long_span: single document span far larger than the window
    long_text = "确定性的中文长文本块。" * 300  # length 3600
    cases.append(
        (
            "long_span",
            make_input(
                "ex_long",
                long_text,
                (TextSpan(1, "document", "doc-long", long_text),),
            ),
            ChunkerConfig(target_codepoints=500, overlap_codepoints=50, hard_max_codepoints=2000),
            {},
        )
    )

    # 6. document_kind: a normal single document span, mid-size
    doc_text = "这是一份普通的文档正文，包含若干中英文 mixed content and whitespace. " * 12
    cases.append(
        (
            "document_kind",
            make_input(
                "ex_doc",
                doc_text,
                (TextSpan(1, "document", "doc-1", doc_text),),
            ),
            DEFAULT_CONFIG,
            {},
        )
    )

    # 7. determinism_reproducibility: dedicated multi-span input exercised for
    #    in-process and cross-process equality (invariants also asserted)
    det_text_a = "确定性输入材料甲。" * 10
    det_text_b = "确定性输入材料乙。" * 10
    det_text = SEPARATOR.join([det_text_a, det_text_b])
    cases.append(
        (
            "determinism_reproducibility",
            make_input(
                "ex_det",
                det_text,
                (
                    TextSpan(1, "page", "page-1", det_text_a),
                    TextSpan(2, "page", "page-2", det_text_b),
                ),
            ),
            ChunkerConfig(target_codepoints=40, overlap_codepoints=8, hard_max_codepoints=200),
            {},
        )
    )

    # 8. reconstruction: mixed short page + long page + short slide, full
    #    extraction text reconstruction (contiguity_core) is the focus
    mix_a = "短页面甲。"  # short
    mix_b = "长页面乙内容段落" * 40  # long, length 320
    mix_c = "幻灯片丙。"  # short
    mix_text = SEPARATOR.join([mix_a, mix_b, mix_c])
    cases.append(
        (
            "reconstruction",
            make_input(
                "ex_mix",
                mix_text,
                (
                    TextSpan(1, "page", "page-1", mix_a),
                    TextSpan(2, "page", "page-2", mix_b),
                    TextSpan(3, "slide", "slide-3", mix_c),
                ),
            ),
            ChunkerConfig(target_codepoints=50, overlap_codepoints=10, hard_max_codepoints=200),
            {},
        )
    )

    return cases


def main() -> None:
    started = time.perf_counter()
    cases_records = []
    all_pass = True

    for name, inp, config, flags in build_cases():
        case_start = time.perf_counter()
        inv = check_invariants(
            inp,
            config,
            expect_empty=flags.get("expect_empty", False),
            check_cross_process=flags.get("check_cross_process", True),
        )
        elapsed_ms = round((time.perf_counter() - case_start) * 1000, 3)

        # Required invariant set for this case
        required = [
            "offset_integrity",
            "contiguity_core",
            "no_cross_span",
            "span_coverage",
            "overlap_consistency",
            "determinism_inproc",
            "determinism_crossproc",
            "all_ready",
        ]
        if flags.get("expect_empty"):
            required.append("empty_yields_zero")
        case_pass = all(bool(inv.get(k)) for k in required)
        if not case_pass:
            all_pass = False

        cases_records.append(
            {
                "name": name,
                "extraction_sha256": inp.extraction_sha256,
                "span_count": len(inp.spans),
                "text_length": len(inp.text),
                "config": {
                    "target_codepoints": config.target_codepoints,
                    "overlap_codepoints": config.overlap_codepoints,
                    "hard_max_codepoints": config.hard_max_codepoints,
                    "strategy": config.strategy,
                    "chunking_version": config.chunking_version,
                },
                "chunk_count": inv["chunk_count"],
                "determinism_sha256": inv["determinism_sha256"],
                "invariants": {k: inv.get(k) for k in required},
                "elapsed_ms": elapsed_ms,
            }
        )

    payload = {
        "component": "deterministic-chunker",
        "component_version": "1.0.0",
        "status": "smoke_passed" if all_pass else "smoke_failed",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "command": f"{sys.executable} smoke.py",
        "chunking_version": "1.0.0",
        "strategy": "codepoint-window-v1",
        "config": {
            "target_codepoints": DEFAULT_CONFIG.target_codepoints,
            "overlap_codepoints": DEFAULT_CONFIG.overlap_codepoints,
            "hard_max_codepoints": DEFAULT_CONFIG.hard_max_codepoints,
        },
        "network": {"required": False, "called": False},
        "cases": cases_records,
        "limitations": [
            "纯算法试炼，不落 SQLite，不建 FTS5，不接 provider。",
            "不测真实 PDF/DOCX/PPTX 二进制；输入是合成的 extraction 契约。",
            "chunker 永不跨 span，即使窗口大于 span 也不合并多个 span 进一个 chunk。",
            "offset 参照系为 Python Unicode code-point index，非 byte offset。",
            "跨进程确定性在同 Python 版本下验证；不同 Python 版本的 unicodedata 表可能轻微差异。",
        ],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="deterministic-chunker-", dir=str(ARTIFACT_DIR)))
    payload["run_dir"] = str(run_dir)
    (run_dir / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ARTIFACT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "component": payload["component"],
        "status": payload["status"],
        "cases": len(cases_records),
    }
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
