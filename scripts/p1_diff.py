"""Chẩn đoán P@1: câu nào Vector xếp đúng hạng 1 mà Hybrid RRF thì không, và vì sao.

Hybrid ở đây ghim fusion="rrf" — cách ghép cũ. Mặc định giờ là Bù BM25, không bao giờ đổi
hạng 1 của Vector, nên chạy với mặc định thì câu trả lời luôn là 0.

    python scripts/p1_diff.py              # tiếng Việt, có lọc lang — đường production đi
    python scripts/p1_diff.py --lang en
    python scripts/p1_diff.py --golden data/holdout.yml   # chỉ để hiểu, không để chỉnh

Dùng lại vector trong cache của harness --live; câu hỏi chưa có trong cache thì cần
GEMINI_API_KEY. Chạy từ gốc repo.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.corpus import DEFAULT_GOLDEN, load_golden, load_kb  # noqa: E402
from rag.bm25 import BM25Index  # noqa: E402
from rag.embed import EmbeddingClient  # noqa: E402
from rag.fusion import DEFAULT_RRF_K  # noqa: E402
from rag.retriever import HybridRetriever  # noqa: E402
from rag.store import VectorStore  # noqa: E402
from rag.synonyms import matched_entries  # noqa: E402

CANDIDATES = 10


def rank(ids: Sequence[str], doc_id: str) -> int | None:
    """Hạng tính từ 1, không có thì None."""
    return ids.index(doc_id) + 1 if doc_id in ids else None


def fused_score(doc_id: str, *branches: Sequence[str]) -> float:
    return sum(1.0 / (DEFAULT_RRF_K + r) for ids in branches if (r := rank(ids, doc_id)))


def show(label: str, ids: Sequence[str], expected: set[str], limit: int = 5) -> str:
    cells = [f"{i}.{d}{' ✓' if d in expected else ''}" for i, d in enumerate(ids[:limit], 1)]
    return f"   {label:<7}: " + ("  ".join(cells) if cells else "(rỗng)")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Câu nào Vector đúng hạng 1 mà Hybrid sai")
    parser.add_argument("--lang", default="vi")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN), help="bộ câu hỏi")
    args = parser.parse_args()

    chunks = load_kb()
    cases = [case for case in load_golden(args.golden) if case.lang == args.lang]
    embedder = EmbeddingClient()
    store = VectorStore()
    store.load(chunks, embedder.embed_all([chunk.embedding_text for chunk in chunks]))
    embedder.embed_all([case.query for case in cases])

    bm25 = BM25Index()
    bm25.load(chunks)
    plain = BM25Index(synonyms={})
    plain.load(chunks)
    retriever = HybridRetriever(
        bm25, store, embedder, candidates_per_branch=CANDIDATES, fusion="rrf"
    )

    lost: list[str] = []
    gained: list[str] = []
    in_both = synonym_driven = 0
    for case in cases:
        expected = set(case.expected)
        lang = case.lang
        vec = [c.doc_id for c in retriever.retrieve_semantic_only(case.query, CANDIDATES, lang)]
        lex = [hit.chunk.doc_id for hit in bm25.search(case.query, CANDIDATES, lang)]
        hyb = [c.doc_id for c in retriever.retrieve(case.query, 5, lang)]
        vec_ok = bool(vec) and vec[0] in expected
        hyb_ok = bool(hyb) and hyb[0] in expected

        if hyb_ok and not vec_ok:
            gained.append(case.query)
        if not (vec_ok and not hyb_ok):
            continue

        lost.append(case.query)
        wrong, right = hyb[0], vec[0]
        both = rank(lex, wrong) is not None and rank(vec, wrong) is not None
        in_both += both

        plain_ids = [hit.chunk.doc_id for hit in plain.search(case.query, CANDIDATES, lang)]
        wrong_plain, right_plain = rank(plain_ids, wrong), rank(plain_ids, right)
        # "Do đồng nghĩa": có mở rộng thì BM25 xếp chunk sai trên chunk đúng, bỏ mở rộng thì hết.
        lex_wrong_above = (rank(lex, wrong) or 99) < (rank(lex, right) or 99)
        plain_wrong_above = (wrong_plain or 99) < (right_plain or 99)
        driven = lex_wrong_above and not plain_wrong_above
        synonym_driven += driven

        keys = [key for key, _ in matched_entries(case.query, lang)]
        print(f'\n✗ "{case.query}"')
        print(f"   đúng   : {sorted(expected)}")
        print(show("Vector", vec, expected))
        print(show("BM25", lex, expected))
        print(show("Hybrid", hyb, expected))
        print(
            f"   RRF    : {wrong} {fused_score(wrong, lex, vec):.4f} "
            f"(BM25 hạng {rank(lex, wrong)}, Vector hạng {rank(vec, wrong)})  vs  "
            f"{right} {fused_score(right, lex, vec):.4f} "
            f"(BM25 hạng {rank(lex, right)}, Vector hạng 1)"
        )
        print(f"   khoá   : {keys or '(không khoá nào)'}")
        print(
            f"   bỏ đồng nghĩa: BM25 xếp {wrong} hạng {wrong_plain}, {right} hạng {right_plain}"
            f"{'  → DO ĐỒNG NGHĨA' if driven else ''}"
        )

    print(f"\n=== {args.lang}: {len(cases)} câu ===")
    print(f"Vector đúng hạng 1 mà Hybrid sai : {len(lost)}")
    print(f"  chunk sai có mặt ở cả hai nhánh: {in_both}/{len(lost)}")
    print(f"  do đồng nghĩa                  : {synonym_driven}/{len(lost)}")
    print(f"Hybrid đúng hạng 1 mà Vector sai : {len(gained)}")
    for query in gained:
        print(f'  + "{query}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
