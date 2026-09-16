"""So hai model embedding trên cùng bộ câu — xem experiments.md 15/09 (bge-m3).

    python scripts/embed_compare.py --model gemini            # chỉ đọc cache, 0 lời gọi API
    python scripts/embed_compare.py --model bge-m3            # gọi Ollama local, lần đầu điền cache
    python scripts/embed_compare.py --model bge-m3 --latency  # đo độ trễ, bỏ qua cache

In P@1 / R@3 / MRR của Vector + lọc lang và Hybrid + lọc lang (Bù BM25) ở hai ngưỡng cosine
(0.55 và 0), trên golden, holdout vi và holdout_codes; câu vi tách thêm có dấu / không dấu.
Chạy từ gốc repo.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import unicodedata
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.corpus import check_golden_against_kb, load_golden, load_kb  # noqa: E402
from eval.metrics import Metrics, evaluate  # noqa: E402
from rag.bm25 import BM25Index  # noqa: E402
from rag.embed import EmbeddingClient, EmbeddingError  # noqa: E402
from rag.retriever import HybridRetriever  # noqa: E402
from rag.store import VectorStore  # noqa: E402
from rag.types import GoldenCase  # noqa: E402

CANDIDATES = 10
THRESHOLDS = (0.55, 0.0)
SETS = (
    ("golden", "data/golden.yml", None),
    ("holdout vi", "data/holdout.yml", "vi"),
    ("holdout_codes vi", "data/holdout_codes.yml", "vi"),
)
OLLAMA_URL = "http://127.0.0.1:11434/v1"


class CacheOnlyClient(EmbeddingClient):
    """Không key nhưng vẫn `available`: nếu không, HybridRetriever lặng lẽ bỏ nhánh Vector và
    bảng chỉ còn là BM25. Văn bản chưa có trong cache ném EmbeddingError thay vì gọi mạng."""

    @property
    def available(self) -> bool:
        return True

    def _call_api(self, batch: list[str]):
        raise EmbeddingError(f"Thiếu {len(batch)} vector trong cache, không gọi API")


def make_client(model: str) -> EmbeddingClient:
    if model == "gemini":
        return CacheOnlyClient(
            api_key="", model="gemini-embedding-001", dimensions=768, min_interval_s=0
        )
    # bge-m3 có số chiều cố định, không gửi `dimensions`.
    return EmbeddingClient(
        api_key="ollama", model=model, dimensions=0, base_url=OLLAMA_URL, min_interval_s=0
    )


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def has_accents(case: GoldenCase) -> bool:
    return strip_accents(case.query) != case.query.lower()


def fmt(m: Metrics) -> str:
    hits = round(m.precision_at_1 * m.n)
    return (
        f"{m.precision_at_1 * 100:5.1f}% ({hits:>3}/{m.n:<3}) "
        f"{m.recall_at_3 * 100:6.1f}% {m.mrr:6.3f}"
    )


def latency(client: EmbeddingClient, queries: Sequence[str], texts: Sequence[str]) -> None:
    client._call_api([queries[0]])  # nạp model lên GPU, không tính
    times = []
    for query in queries:
        start = time.perf_counter()
        client._call_api([query])
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    p95 = times[max(0, round(0.95 * len(times)) - 1)]
    print(
        f"Nhúng từng câu hỏi ({len(times)} câu): p50 {statistics.median(times):.0f} ms, "
        f"p95 {p95:.0f} ms, max {times[-1]:.0f} ms"
    )
    start = time.perf_counter()
    for i in range(0, len(texts), client.batch_size):
        client._call_api(list(texts[i : i + client.batch_size]))
    print(
        f"Nhúng {len(texts)} chunk theo lô {client.batch_size}: {time.perf_counter() - start:.1f} s"
    )


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="So model embedding")
    parser.add_argument("--model", choices=("gemini", "bge-m3"), required=True)
    parser.add_argument("--latency", action="store_true", help="đo độ trễ, không chấm điểm")
    args = parser.parse_args(argv)

    chunks = load_kb()
    client = make_client(args.model)
    if args.latency:
        golden = load_golden("data/golden.yml")
        latency(client, [c.query for c in golden], [c.embedding_text for c in chunks])
        return 0

    bm25 = BM25Index()
    bm25.load(chunks)
    try:
        vectors = client.embed_all([chunk.embedding_text for chunk in chunks])
    except EmbeddingError as error:
        print(f"Không nhúng được chunk: {error}", file=sys.stderr)
        return 2
    store = VectorStore()
    store.load(chunks, vectors)
    print(f"{args.model}: {len(chunks)} chunk, {vectors.shape[1]} chiều")

    failures = 0
    for set_name, path, lang in SETS:
        cases = [c for c in load_golden(path) if lang is None or c.lang == lang]
        if missing := check_golden_against_kb(cases, chunks):
            print(f"docId không tồn tại: {missing}", file=sys.stderr)
            return 2
        try:
            client.embed_all([case.query for case in cases])
        except EmbeddingError as error:
            print(f"Không nhúng được câu hỏi {set_name}: {error}", file=sys.stderr)
            return 2

        vi = [c for c in cases if c.lang == "vi"]
        subsets = [("tất cả", cases)]
        if lang is None:
            subsets.append(("vi", vi))
        subsets += [
            ("vi có dấu", [c for c in vi if has_accents(c)]),
            ("vi không dấu", [c for c in vi if not has_accents(c)]),
        ]

        print(f"\n== {set_name} — + lọc lang")
        print(f"{'Ngưỡng':<6} {'Cấu hình':<8} {'Tập':<13} {'P@1':>16} {'R@3':>7} {'MRR':>6}")
        for threshold in THRESHOLDS:
            retriever = HybridRetriever(
                bm25, store, client, candidates_per_branch=CANDIDATES, min_similarity=threshold
            )
            configs = (
                (
                    "Vector",
                    lambda c, k, r=retriever: [
                        x.doc_id for x in r.retrieve_semantic_only(c.query, k, c.lang)
                    ],
                ),
                (
                    "Hybrid",
                    lambda c, k, r=retriever: [x.doc_id for x in r.retrieve(c.query, k, c.lang)],
                ),
            )
            for config, retrieve in configs:
                for subset_name, subset in subsets:
                    if subset:
                        m = evaluate(config, subset, retrieve)
                        print(f"{threshold:<6g} {config:<8} {subset_name:<13} {fmt(m)}")
            if not any(retriever.retrieve_semantic_only(c.query, 5, c.lang) for c in cases):
                print("Nhánh Vector trả rỗng mọi câu — số đo KHÔNG dùng được.", file=sys.stderr)
                return 3
            failures += retriever.embedding_failures

    print(
        f"\nLời gọi API embedding: {client.api_calls}, thử lại vì 429: {client.rate_limit_retries}"
    )
    if failures:
        print(f"{failures} lần nhúng hỏng — số đo KHÔNG dùng được.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
