"""Bộ khung chạy đánh giá (eval harness) — chạy được từ dòng lệnh.

Hạ tầng đã viết sẵn: nạp dữ liệu, dựng chỉ mục, chạy từng nhánh, in bảng, cổng ngưỡng,
mã thoát. Bạn chỉ cần cài đặt rag/* và eval/metrics.py là nó chạy.

    python -m eval.harness
    python -m eval.harness --branch lexical --min-recall3 0.85 --min-mrr 0.70
    python -m eval.harness --json > baseline.json

Vì sao là CLI chứ không phải một JUnit test như bản Java: bộ đo chỉ có giá trị khi bạn
chạy nó thường xuyên, kể cả lúc đang thử một ý tưởng nửa vời. Nấp trong test runner là
nó chỉ được chạy lúc CI.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from eval.corpus import check_golden_against_kb, load_golden, load_kb
from eval.metrics import Metrics, evaluate
from rag.bm25 import BM25Index
from rag.embed import EmbeddingClient, EmbeddingError
from rag.fusion import rrf
from rag.store import VectorStore
from rag.types import Chunk, GoldenCase

BRANCHES = ("lexical", "semantic", "hybrid")


def _fmt(metrics: Metrics) -> str:
    return (
        f"{metrics.name:<10} "
        f"{metrics.precision_at_1 * 100:6.1f}% "
        f"{metrics.recall_at_3 * 100:8.1f}% "
        f"{metrics.recall_at_5 * 100:8.1f}% "
        f"{metrics.precision_at_3:9.3f} "
        f"{metrics.f1_at_3:7.3f} "
        f"{metrics.mrr:7.3f}"
    )


def _header() -> str:
    head = (
        f"{'nhánh':<10} {'P@1':>7} {'R@3':>9} {'R@5':>9} {'P@3':>9} {'F1@3':>7} {'MRR':>7}"
    )
    return head + "\n" + "-" * len(head)


def run_branch(
    branch: str,
    cases: list[GoldenCase],
    chunks: list[Chunk],
    bm25: BM25Index,
    store: VectorStore,
    embedder: EmbeddingClient,
    top_k: int,
    min_similarity: float,
) -> Metrics:
    """Chạy một nhánh trên toàn bộ câu hỏi vàng và chấm điểm."""
    results: list[tuple[list[str], list[str]]] = []

    for case in cases:
        lexical = bm25.search(case.query, top_k) if branch in ("lexical", "hybrid") else []

        semantic = []
        if branch in ("semantic", "hybrid") and embedder.available and len(store):
            try:
                qv = embedder.embed(case.query)
                semantic = store.search(qv, top_k, min_similarity)
            except EmbeddingError as e:
                # Suy giảm êm, giống HybridRetriever.semanticSearch: embedding hỏng thì
                # nhánh này rỗng, không làm sập cả lượt đo.
                print(f"  [cảnh báo] embedding hỏng cho {case.query!r}: {e}", file=sys.stderr)

        if branch == "lexical":
            retrieved = [s.chunk.doc_id for s in lexical]
        elif branch == "semantic":
            retrieved = [s.chunk.doc_id for s in semantic]
        else:
            retrieved = [c.doc_id for c in rrf([lexical, semantic], top_k)]

        results.append((retrieved, case.expected))

    return evaluate(branch, results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Đo chất lượng truy hồi RAG")
    parser.add_argument("--branch", choices=(*BRANCHES, "all"), default="all")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-similarity", type=float, default=0.55)
    parser.add_argument("--lang", default=None, help="Lọc knowledge base theo lang (tuần 8)")
    parser.add_argument("--min-recall3", type=float, default=None, help="Cổng CI")
    parser.add_argument("--min-mrr", type=float, default=None, help="Cổng CI")
    parser.add_argument("--json", action="store_true", help="In JSON thay vì bảng")
    args = parser.parse_args(argv)

    chunks = load_kb(lang=args.lang)
    cases = load_golden()

    missing = check_golden_against_kb(cases, chunks)
    if missing:
        print("docId trong golden.yml không tồn tại trong knowledge base:", file=sys.stderr)
        for doc_id in missing:
            print(f"  - {doc_id}", file=sys.stderr)
        return 2

    bm25 = BM25Index()
    bm25.load(chunks)

    store = VectorStore()
    embedder = EmbeddingClient()
    if embedder.available:
        vectors = embedder.embed_all([c.indexed_text for c in chunks])
        store.load(chunks, vectors)
    else:
        print(
            "[chú ý] Chưa có EMBEDDING_API_KEY — chỉ đo được nhánh từ khoá.\n",
            file=sys.stderr,
        )

    branches = BRANCHES if args.branch == "all" else (args.branch,)
    all_metrics: list[Metrics] = []

    started = time.perf_counter()
    for branch in branches:
        if branch in ("semantic", "hybrid") and not embedder.available:
            continue
        all_metrics.append(
            run_branch(
                branch, cases, chunks, bm25, store, embedder, args.top_k, args.min_similarity
            )
        )
    elapsed = time.perf_counter() - started

    if args.json:
        print(json.dumps([m.__dict__ for m in all_metrics], ensure_ascii=False, indent=2))
    else:
        print(f"\n{len(chunks)} chunk · {len(cases)} câu hỏi vàng · {elapsed:.1f}s\n")
        print(_header())
        for m in all_metrics:
            print(_fmt(m))
        print()

    # Cổng chất lượng: áp lên nhánh cuối cùng được chạy (nhánh tốt nhất hiện có).
    if all_metrics and (args.min_recall3 is not None or args.min_mrr is not None):
        gate = all_metrics[-1]
        failed = []
        if args.min_recall3 is not None and gate.recall_at_3 < args.min_recall3:
            failed.append(f"recall@3 {gate.recall_at_3:.3f} < {args.min_recall3}")
        if args.min_mrr is not None and gate.mrr < args.min_mrr:
            failed.append(f"MRR {gate.mrr:.3f} < {args.min_mrr}")
        if failed:
            print(f"CỔNG CHẤT LƯỢNG HỎNG ({gate.name}):", file=sys.stderr)
            for f in failed:
                print(f"  - {f}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
