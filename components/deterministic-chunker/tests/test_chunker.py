"""Optional pytest mirror of the deterministic-chunker smoke cases.

Run with: D:\\miniconda\\py310\\python.exe -m pytest tests/test_chunker.py

These tests are independent of smoke.py; they construct their own cases and
assert the same invariants. They do NOT require network, SQLite or a provider.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from deterministic_chunker import (  # noqa: E402
    SEPARATOR,
    Chunk,
    ChunkInput,
    ChunkerConfig,
    TextSpan,
    chunk,
    determinism_sha256,
    normalize_text,
    estimate_tokens,
)


def _input(extraction_id: str, text: str, spans, fingerprint=None) -> ChunkInput:
    import hashlib

    return ChunkInput(
        extraction_id=extraction_id,
        extraction_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        revision_fingerprint=fingerprint or f"rev_{extraction_id}",
        text=text,
        spans=tuple(spans),
    )


def _reconstruct(chunks: list[Chunk], spans) -> str:
    by_span: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_span[c.spans[0].span_ordinal].append(c)
    parts: list[str] = []
    for i, span in enumerate(spans):
        if i > 0:
            parts.append(SEPARATOR)
        sc = by_span.get(span.ordinal, [])
        if sc:
            parts.append(sc[0].text + "".join(c.text[c.overlap_before:] for c in sc[1:]))
    return "".join(parts)


def _assert_invariants(inp: ChunkInput, cfg: ChunkerConfig, *, expect_empty=False) -> list[Chunk]:
    chunks = chunk(inp, cfg)
    # offset_integrity
    assert all(inp.text[c.start_offset : c.end_offset] == c.text for c in chunks)
    # contiguity_core
    assert _reconstruct(chunks, inp.spans) == inp.text
    # no_cross_span
    assert all(len(c.spans) == 1 for c in chunks)
    # span_coverage
    by_span: dict[int, list[Chunk]] = defaultdict(list)
    for c in chunks:
        by_span[c.spans[0].span_ordinal].append(c)
    for span in inp.spans:
        if not span.text:
            continue
        sc = by_span[span.ordinal]
        assert sc, f"span {span.ordinal} has no chunks"
        body = sc[0].text + "".join(c.text[c.overlap_before:] for c in sc[1:])
        assert body == span.text, f"span {span.ordinal} not fully covered"
    # overlap_consistency
    for i, c in enumerate(chunks):
        assert c.overlap_before == (chunks[i - 1].overlap_after if i > 0 else 0)
    if chunks:
        assert chunks[0].overlap_before == 0
        assert chunks[-1].overlap_after == 0
    # determinism (in-process)
    assert determinism_sha256(chunk(inp, cfg)) == determinism_sha256(chunk(inp, cfg))
    # all ready
    assert all(c.status == "ready" and c.error_code is None for c in chunks)
    if expect_empty:
        assert chunks == []
    return chunks


def test_empty_yields_zero():
    inp = _input("ex_empty", "", ())
    _assert_invariants(inp, ChunkerConfig(), expect_empty=True)


def test_chinese_offset_codepoint():
    text = (
        "进程是资源分配的基本单位。线程是ＣＰＵ调度的最小单位。\U0001F600 "
        "全角：ＡＢＣ１２３；组合字：e\u0301；标点「」『』，、。；"
    )
    inp = _input("ex_chinese", text, (TextSpan(1, "document", "doc-chinese", text),))
    chunks = _assert_invariants(inp, ChunkerConfig(20, 4, 100))
    assert len(chunks) >= 2
    # code-point semantics: each chunk text is an exact str slice
    for c in chunks:
        assert text[c.start_offset : c.end_offset] == c.text


def test_page_boundary_no_cross():
    p1 = "第1页内容段落" * 8
    p2 = "第二页正文片段" * 8
    p3 = "第三页结尾说明" * 8
    text = SEPARATOR.join([p1, p2, p3])
    spans = (
        TextSpan(1, "page", "page-1", p1),
        TextSpan(2, "page", "page-2", p2),
        TextSpan(3, "page", "page-3", p3),
    )
    inp = _input("ex_pages", text, spans)
    cfg = ChunkerConfig(20, 4, 100)
    chunks = _assert_invariants(inp, cfg)
    # window < span length: every chunk maps to exactly one page
    ordinals = {c.spans[0].span_ordinal for c in chunks}
    assert ordinals == {1, 2, 3}
    for c in chunks:
        assert len(c.spans) == 1


def test_slide_boundary_no_cross():
    s1 = "幻灯片一标题与要点说明" * 6
    s2 = "幻灯片二补充内容要点" * 6
    text = SEPARATOR.join([s1, s2])
    inp = _input("ex_slides", text, (TextSpan(1, "slide", "slide-1", s1), TextSpan(2, "slide", "slide-2", s2)))
    _assert_invariants(inp, ChunkerConfig(25, 5, 100))


def test_long_span_internal_split():
    text = "确定性的中文长文本块。" * 300
    inp = _input("ex_long", text, (TextSpan(1, "document", "doc-long", text),))
    cfg = ChunkerConfig(500, 50, 2000)
    chunks = _assert_invariants(inp, cfg)
    assert len(chunks) >= 3
    # all chunks map to the same span
    assert all(c.spans[0].span_ordinal == 1 for c in chunks)


def test_document_kind_normal():
    text = "这是一份普通的文档正文，包含若干中英文 mixed content and whitespace. " * 12
    inp = _input("ex_doc", text, (TextSpan(1, "document", "doc-1", text),))
    _assert_invariants(inp, ChunkerConfig())


def test_determinism_reproducibility():
    a = "确定性输入材料甲。" * 10
    b = "确定性输入材料乙。" * 10
    text = SEPARATOR.join([a, b])
    inp = _input("ex_det", text, (TextSpan(1, "page", "page-1", a), TextSpan(2, "page", "page-2", b)))
    cfg = ChunkerConfig(40, 8, 200)
    _assert_invariants(inp, cfg)
    # identical fingerprint + input -> identical chunk_id sequence
    run1 = chunk(inp, cfg)
    run2 = chunk(inp, cfg)
    assert [c.chunk_id for c in run1] == [c.chunk_id for c in run2]


def test_reconstruction_mixed():
    a = "短页面甲。"
    b = "长页面乙内容段落" * 40
    c = "幻灯片丙。"
    text = SEPARATOR.join([a, b, c])
    inp = _input("ex_mix", text, (TextSpan(1, "page", "page-1", a), TextSpan(2, "page", "page-2", b), TextSpan(3, "slide", "slide-3", c)))
    chunks = _assert_invariants(inp, ChunkerConfig(50, 10, 200))
    assert len(chunks) >= 2


def test_normalized_text_is_pure_function():
    text = "Ａ ＢＣ\n\n  多余   空白 \t\n"
    n1 = normalize_text(text)
    n2 = normalize_text(text)
    assert n1 == n2
    assert "  " not in n1
    assert "\n" not in n1


def test_token_estimate_is_deterministic_and_nonneg():
    text = "进程 process ＡＢＣ 123 hello world"
    t1 = estimate_tokens(text)
    t2 = estimate_tokens(text)
    assert t1 == t2
    assert t1 > 0
