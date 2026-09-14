"""Tách điểm theo category và liệt kê câu sai hạng 1 — xem experiments.md 14/09.

    python scripts/by_category.py                              # bộ vàng, mọi ngôn ngữ
    python scripts/by_category.py --golden data/holdout.yml    # chỉ để hiểu, không để chỉnh
    python scripts/by_category.py --lang vi

Chỉ đọc vector trong cache của harness --live, KHÔNG gọi API: client dựng không có key, nên
văn bản nào chưa có trong cache thì báo lỗi thay vì âm thầm gọi mạng. Chạy từ gốc repo.

Category của một câu là category của chunk đúng ĐẦU TIÊN trong expected.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.corpus import DEFAULT_GOLDEN, check_golden_against_kb, load_golden, load_kb  # noqa: E402
from eval.metrics import Retrieve, evaluate  # noqa: E402
from rag.bm25 import BM25Index  # noqa: E402
from rag.embed import EmbeddingClient, EmbeddingError  # noqa: E402
from rag.retriever import HybridRetriever  # noqa: E402
from rag.store import VectorStore  # noqa: E402
from rag.types import GoldenCase  # noqa: E402

CANDIDATES = 10


class CacheOnlyEmbedder:
    """Nhánh Vector đọc từ cache. Không có key: văn bản chưa cache ném EmbeddingError."""

    available = True

    def __init__(self) -> None:
        self.client = EmbeddingClient(api_key="")

    def embed(self, text: str) -> np.ndarray:
        return self.client.embed(text)


def fmt(hits: float, n: int) -> str:
    return f"{hits * 100:5.1f}% ({round(hits * n):>2}/{n:<2})"


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Điểm theo category và câu sai hạng 1")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN), help="bộ câu hỏi")
    parser.add_argument("--lang", help="chỉ chấm câu hỏi của ngôn ngữ này")
    args = parser.parse_args(argv)

    chunks = load_kb()
    cases = [c for c in load_golden(args.golden) if args.lang is None or c.lang == args.lang]
    if missing := check_golden_against_kb(cases, chunks):
        print(f"docId không tồn tại trong knowledge base: {missing}", file=sys.stderr)
        return 2
    category = {chunk.doc_id: chunk.category for chunk in chunks}

    embedder = CacheOnlyEmbedder()
    try:
        vectors = embedder.client.embed_all([chunk.embedding_text for chunk in chunks])
        embedder.client.embed_all([case.query for case in cases])
    except EmbeddingError as error:
        print(f"Thiếu vector trong cache — chạy harness --live trước: {error}", file=sys.stderr)
        return 2

    bm25 = BM25Index()
    bm25.load(chunks)
    store = VectorStore()
    store.load(chunks, vectors)
    retriever = HybridRetriever(bm25, store, embedder, candidates_per_branch=CANDIDATES)

    def lexical(case: GoldenCase, k: int) -> list[str]:
        return [hit.chunk.doc_id for hit in bm25.search(case.query, k, case.lang)]

    def hybrid(case: GoldenCase, k: int) -> list[str]:
        return [chunk.doc_id for chunk in retriever.retrieve(case.query, k, case.lang)]

    by_category: dict[str, list[GoldenCase]] = defaultdict(list)
    for case in cases:
        by_category[category[case.expected[0]]].append(case)

    def row(name: str, subset: list[GoldenCase], retrieve: Retrieve):
        return evaluate(name, subset, retrieve)

    rows = []
    for name, subset in by_category.items():
        rows.append((name, len(subset), row(name, subset, lexical), row(name, subset, hybrid)))
    rows.sort(key=lambda r: (r[3].precision_at_1, r[2].precision_at_1, r[0]))
    rows.append(("TỔNG", len(cases), row("TỔNG", cases, lexical), row("TỔNG", cases, hybrid)))

    print(f"\n{Path(args.golden).name}{f' · {args.lang}' if args.lang else ''} — + lọc lang")
    print(
        f"{'Category':<10} {'BM25 P@1':>14}   {'Hybrid P@1':>14} {'R@3':>7} {'MRR':>6} "
        f"{'nDCG@5':>7}"
    )
    print("-" * 66)
    for name, n, lex, hyb in rows:
        print(
            f"{name:<10} {fmt(lex.precision_at_1, n):>14}   {fmt(hyb.precision_at_1, n):>14} "
            f"{hyb.recall_at_3 * 100:6.1f}% {hyb.mrr:6.3f} {hyb.ndcg_at_5:7.3f}"
        )

    kinds: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    print("\nCâu Hybrid + lọc lang sai hạng 1:")
    for case in cases:
        top5 = hybrid(case, 5)
        if top5 and top5[0] in case.expected:
            continue
        want = category[case.expected[0]]
        semantic = [
            chunk.doc_id
            for chunk in retriever.retrieve_semantic_only(case.query, CANDIDATES, case.lang)
        ]
        rank = next((i for i, d in enumerate(top5, 1) if d in case.expected), None)
        if rank is None:
            kind = "trượt top-5"
        elif category[top5[0]] == want:
            kind = "nhầm chunk cùng category"
        else:
            kind = "nhầm sang category khác"
        source = "rỗng" if not top5 else "Vector" if top5[0] in semantic else "BM25 lấp"
        kinds[kind] += 1
        sources[source] += 1
        top3 = "  ".join(f"{i}.{d} ({category[d]})" for i, d in enumerate(top5[:3], 1))
        print(f'\n✗ [{want}] "{case.query}"')
        print(f"   đúng  : {sorted(case.expected)} — hạng {rank or '>5'}")
        print(f"   top-3 : {top3}")
        print(f"   nhãn  : {kind}; hạng 1 từ {source}; Vector trả {len(semantic)} ứng viên")

    print(f"\nTổng: {sum(kinds.values())} câu — {dict(kinds)}; hạng 1 từ {dict(sources)}")
    if retriever.embedding_failures:
        print(f"{retriever.embedding_failures} lần thiếu vector — số đo KHÔNG dùng được.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
