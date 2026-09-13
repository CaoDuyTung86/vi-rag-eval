"""Bộ khung chạy đánh giá — bản Python của RagRetrievalQualityTest.

    python -m eval.harness           # BM25, không cần API key, có cổng ngưỡng theo ngôn ngữ
    python -m eval.harness --live    # thêm Vector và Hybrid, gọi API embedding
    python -m eval.harness --json    # in JSON (kèm nDCG@5 và danh sách câu trượt)

Cách chấm khớp từng dòng với bản Java để hai bảng đặt cạnh nhau so được: mỗi câu lấy top-5,
chấm riêng từng ngôn ngữ CÂU HỎI rồi thêm dòng gộp, và mỗi nhánh chạy hai cấu hình — trên
corpus hỗn hợp, và có lọc theo ngôn ngữ câu hỏi (đường mà lượt chat thật đi qua).

--live không bật mặc định, giống RAG_EVAL_LIVE bên Java: nó ăn vào hạn mức API, và một lệnh
gõ nhầm không nên làm việc đó.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

from eval.corpus import check_golden_against_kb, load_golden, load_kb
from eval.metrics import ALL_LANGS, Metrics, Retrieve, evaluate_by_lang
from rag.bm25 import BM25Index
from rag.embed import EmbeddingClient, EmbeddingError
from rag.retriever import HybridRetriever
from rag.store import VectorStore
from rag.types import Chunk, GoldenCase

# Ngưỡng theo từng ngôn ngữ, khớp MIN_RECALL_AT_3 / MIN_MRR bên Java. Thêm ngôn ngữ mới vào
# golden.yml mà quên thêm ngưỡng ở đây thì cổng báo hỏng — cố ý, để không ai lỡ thêm câu hỏi
# mà quên chốt chặn.
MIN_RECALL_AT_3 = {"vi": 0.85, "en": 0.85, "ja": 0.85, "zh": 0.85}
MIN_MRR = {"vi": 0.70, "en": 0.70, "ja": 0.70, "zh": 0.70}

EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_BAD_DATA = 2
EXIT_LIVE_FAILED = 3


def print_table(results: Sequence[Metrics]) -> None:
    rule = "-" * 65
    print()
    print("==================== CHẤT LƯỢNG TRUY HỒI RAG ====================")
    print(
        f"{'Cấu hình':<22} {'Câu':>5} {'P@1':>8} {'R@3':>8} "
        f"{'R@5':>8} {'P@3':>8} {'F1@3':>8} {'MRR':>8}"
    )
    print(rule)
    for m in results:
        print(
            f"{m.name:<22} {m.n:>5} {m.precision_at_1 * 100:7.1f}% {m.recall_at_3 * 100:7.1f}% "
            f"{m.recall_at_5 * 100:7.1f}% {m.precision_at_3:7.3f} {m.f1_at_3:7.3f} {m.mrr:7.3f}"
        )
    print(rule)
    print("P@1 = tỉ lệ kết quả đầu tiên đã đúng (gần nhất với 'accuracy')")
    print("R@k = tỉ lệ câu hỏi tìm được chunk đúng trong top-k")
    print("P@3 bị chặn trên ở 0.333 vì hầu hết câu hỏi chỉ có 1 chunk đúng")
    print("Dòng '· vi', '· en'... chấm theo ngôn ngữ CÂU HỎI; corpus luôn là corpus hỗn hợp")
    print("'+ lọc lang' = chỉ chấm chunk cùng ngôn ngữ với câu hỏi (đường production đi)")
    print("=================================================================")
    for m in results:
        if m.misses:
            print(f"\n[{m.name}] {len(m.misses)} câu trượt hoàn toàn (không có trong top-5):")
            for miss in m.misses:
                print(miss)
    print()


def check_thresholds(
    by_lang: dict[str, Metrics],
    min_recall3: float | None = None,
    min_mrr: float | None = None,
) -> list[str]:
    """Danh sách vi phạm ngưỡng; rỗng là đạt. Dòng gộp không bị chấm ngưỡng.

    min_recall3 / min_mrr khác None thì ghi đè ngưỡng cho mọi ngôn ngữ.
    """
    failures: list[str] = []
    for lang, m in by_lang.items():
        if lang == ALL_LANGS:
            continue
        need_r3 = min_recall3 if min_recall3 is not None else MIN_RECALL_AT_3.get(lang)
        need_mrr = min_mrr if min_mrr is not None else MIN_MRR.get(lang)
        if need_r3 is None or need_mrr is None:
            failures.append(
                f"{m.name}: chưa khai báo ngưỡng cho ngôn ngữ '{lang}' "
                "trong MIN_RECALL_AT_3/MIN_MRR"
            )
            continue
        if m.recall_at_3 < need_r3:
            failures.append(f"{m.name}: recall@3 {m.recall_at_3:.3f} < {need_r3}")
        if m.mrr < need_mrr:
            failures.append(f"{m.name}: MRR {m.mrr:.3f} < {need_mrr}")
    return failures


def _doc_ids(chunks: Sequence[Chunk]) -> list[str]:
    return [chunk.doc_id for chunk in chunks]


def run_live(
    chunks: list[Chunk],
    cases: list[GoldenCase],
    bm25: BM25Index,
    *,
    candidates: int,
    min_similarity: float,
    embedder: EmbeddingClient | None = None,
) -> tuple[list[Metrics], str | None]:
    """Đo bốn cấu hình dùng embedding. Trả (kết quả, thông báo lỗi hoặc None)."""
    embedder = embedder or EmbeddingClient()
    if not embedder.available:
        return [], "--live cần GEMINI_API_KEY hoặc EMBEDDING_API_KEY."

    print(
        f"[Live] Sinh embedding cho {len(chunks)} chunk và {len(cases)} câu hỏi "
        f"bằng {embedder.model} ({embedder.dimensions} chiều)...",
        file=sys.stderr,
    )
    try:
        vectors = embedder.embed_all([chunk.embedding_text for chunk in chunks])
        # Nhúng trước mọi câu hỏi theo lô: vài lời gọi thay vì hơn trăm lời gọi lẻ, và từ đó
        # cả bốn cấu hình đọc vector câu hỏi từ cache.
        embedder.embed_all([case.query for case in cases])
    except EmbeddingError as error:
        return [], f"Sinh embedding thất bại: {error}"

    store = VectorStore()
    store.load(chunks, vectors)
    failures: list[str] = []
    retriever = HybridRetriever(
        bm25,
        store,
        embedder,
        candidates_per_branch=candidates,
        min_similarity=min_similarity,
        on_embedding_error=lambda query, error: failures.append(f"{query!r}: {error}"),
    )

    configs: list[tuple[str, Retrieve]] = [
        ("Vector", lambda c, k: _doc_ids(retriever.retrieve_semantic_only(c.query, k))),
        (
            "Vector + lọc lang",
            lambda c, k: _doc_ids(retriever.retrieve_semantic_only(c.query, k, c.lang)),
        ),
        ("Hybrid (RRF)", lambda c, k: _doc_ids(retriever.retrieve(c.query, k))),
        ("Hybrid + lọc lang", lambda c, k: _doc_ids(retriever.retrieve(c.query, k, c.lang))),
    ]
    results: list[Metrics] = []
    for name, retrieve in configs:
        results.extend(evaluate_by_lang(name, cases, retrieve).values())

    print(
        f"[Live] Lời gọi API embedding: {embedder.api_calls}, "
        f"thử lại vì 429: {embedder.rate_limit_retries}, lời gọi hỏng hẳn: {len(failures)}",
        file=sys.stderr,
    )
    if failures:
        # Chốt chặn quan trọng nhất của chế độ live, giống bản Java: suy giảm êm về BM25 là
        # hành vi ĐÚNG khi chạy thật, nhưng khi ĐO thì nó biến nhánh Vector thành BM25 trá
        # hình mà bảng không có dấu hiệu gì. Thà báo hỏng còn hơn in một con số không biết là
        # của cái gì.
        return results, (
            f"{len(failures)} lời gọi embedding hỏng hẳn — số đo Vector/Hybrid KHÔNG dùng được."
        )
    return results, None


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Đo chất lượng truy hồi RAG")
    parser.add_argument("--live", action="store_true", help="đo thêm Vector và Hybrid")
    parser.add_argument("--json", action="store_true", help="in JSON thay vì bảng")
    parser.add_argument("--candidates", type=int, default=10, help="ứng viên mỗi nhánh (live)")
    parser.add_argument("--min-similarity", type=float, default=0.55, help="ngưỡng cosine (live)")
    parser.add_argument("--min-recall3", type=float, help="ghi đè ngưỡng recall@3 mọi ngôn ngữ")
    parser.add_argument("--min-mrr", type=float, help="ghi đè ngưỡng MRR mọi ngôn ngữ")
    parser.add_argument("--no-gate", action="store_true", help="chỉ in số, không áp ngưỡng")
    args = parser.parse_args(argv)

    info = sys.stderr if args.json else sys.stdout

    chunks = load_kb()
    cases = load_golden()
    missing = check_golden_against_kb(cases, chunks)
    if missing:
        print("docId trong golden.yml không tồn tại trong knowledge base:", file=sys.stderr)
        for doc_id in missing:
            print(f"  - {doc_id}", file=sys.stderr)
        return EXIT_BAD_DATA

    bm25 = BM25Index()
    bm25.load(chunks)

    lexical = evaluate_by_lang(
        "BM25", cases, lambda c, k: [hit.chunk.doc_id for hit in bm25.search(c.query, k)]
    )
    lexical_filtered = evaluate_by_lang(
        "BM25 + lọc lang",
        cases,
        lambda c, k: [hit.chunk.doc_id for hit in bm25.search(c.query, k, c.lang)],
    )
    results = [*lexical.values(), *lexical_filtered.values()]

    live_error: str | None = None
    if args.live:
        live_results, live_error = run_live(
            chunks,
            cases,
            bm25,
            candidates=args.candidates,
            min_similarity=args.min_similarity,
        )
        results.extend(live_results)
    else:
        print(
            "\n[Bỏ qua nhánh ngữ nghĩa] Chạy với --live và đặt GEMINI_API_KEY "
            "để đo thêm cấu hình Vector và Hybrid.",
            file=info,
        )

    if args.json:
        print(json.dumps([asdict(m) for m in results], ensure_ascii=False, indent=2))
    else:
        print_table(results)

    if live_error:
        print(f"CHẾ ĐỘ LIVE HỎNG: {live_error}", file=sys.stderr)
        return EXIT_LIVE_FAILED

    if not args.no_gate:
        failures = [
            *check_thresholds(lexical, args.min_recall3, args.min_mrr),
            *check_thresholds(lexical_filtered, args.min_recall3, args.min_mrr),
        ]
        if failures:
            print("CỔNG CHẤT LƯỢNG HỎNG:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return EXIT_GATE_FAILED

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
