"""Tuần 9: tầng sinh có bịa không — sinh câu trả lời, rồi đo LLM-judge so với chấm tay.

    python scripts/faithfulness.py gen --env-file ../WebProject/.env    # → data/faithfulness.yml
    # mở data/faithfulness.yml, điền nhan_tay cho cả 30 câu
    python scripts/faithfulness.py judge --env-file ../WebProject/.env  # mức đồng ý với chấm tay

Sinh: cấu hình tầng CHAT của VigoTrip — gemini-flash-lite-latest, temperature 0.7, tối đa 800 token,
prompt data/prompts/vigotrip_chat.txt, top-4 chunk từ Hybrid + lọc lang. Chấm: Groq gpt-oss-120b,
temperature 0 — khác họ model với bên sinh, để judge không chấm bài của chính mình.

`judge` từ chối chạy khi còn câu chưa có nhan_tay: thấy nhãn judge trước thì chấm tay sẽ nghiêng
theo, và con số đồng ý mất nghĩa. Chạy từ gốc repo.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.corpus import ROOT, load_golden, load_kb, normalize_case_lang  # noqa: E402
from eval.judge import LABELS, RUBRIC, agreement, judge_prompt, parse_label  # noqa: E402
from rag.bm25 import BM25Index  # noqa: E402
from rag.embed import EmbeddingClient, EmbeddingError  # noqa: E402
from rag.generate import TOP_K, rag_context, system_prompt  # noqa: E402
from rag.llm import (  # noqa: E402
    GEMINI_BASE_URL,
    GROQ_BASE_URL,
    ChatClient,
    LlmError,
    load_env_file,
)
from rag.retriever import HybridRetriever  # noqa: E402
from rag.store import VectorStore  # noqa: E402

OUT = ROOT / "data" / "faithfulness.yml"
UNANSWERABLE = ROOT / "data" / "unanswerable.yml"

SEED = 9
GOLDEN_N = 15
# 15 câu KB không trả lời được, rải theo loại. kb_khong_co nhiều nhất: đó là chỗ model dễ lấy hiểu
# biết chung ra nói thay.
UNANSWERABLE_MIX = {
    "kb_khong_co": 4,
    "ngoai_le": 2,
    "injection": 2,
    "can_ngu_canh": 2,
    "can_tool": 1,
    "mo_ho": 1,
    "phan_nan": 1,
    "de_doa": 1,
    "tro_chuyen": 1,
}

GEN_MODEL = "gemini-flash-lite-latest"
JUDGE_MODEL = "openai/gpt-oss-120b"

HEADER = """\
# Tuần 9 — 30 cặp câu hỏi / câu trả lời để chấm tay. Sinh bằng scripts/faithfulness.py gen.
#
# Việc của bạn: điền nhan_tay cho từng câu (ghi_chu tuỳ ý). Đọc chunks trong data/kb/faq-vi.yml
# theo docId — chatbot chỉ được đọc đúng các chunk đó, không hơn.
#
#   co_can_cu     có đưa thông tin, và mọi thông tin cụ thể về VigoTrip đều có trong chunks
#   bia           có ÍT NHẤT một thông tin cụ thể không có trong chunks, hoặc trái với chunks
#   tu_choi_dung  không đưa thông tin (từ chối, hỏi lại, mời liên hệ) và chunks đúng là không đủ
#   tu_choi_thua  không đưa thông tin, trong khi chunks đủ để trả lời
#
# Rubric đầy đủ judge dùng: eval/judge.py. Chấm xong cả 30 câu mới chạy `judge`.
"""


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str)


def write_items(path: Path, items: list[dict]) -> None:
    body = yaml.dump(items, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=100)
    path.write_text(HEADER + "\n" + body, encoding="utf-8")


def read_items(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def pick_cases() -> list[dict]:
    rng = random.Random(SEED)
    golden = [case for case in load_golden() if case.lang == "vi"]
    cases = [
        {
            "id": f"g{i:02d}",
            "nguon": "golden",
            "loai": "co_tai_lieu",
            "lang": case.lang,
            "query": case.query,
            "expected": list(case.expected),
        }
        for i, case in enumerate(rng.sample(golden, GOLDEN_N), 1)
    ]
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for item in yaml.safe_load(UNANSWERABLE.read_text(encoding="utf-8")):
        by_kind[item["loai"]].append(item)
    picked = [item for kind, n in UNANSWERABLE_MIX.items() for item in rng.sample(by_kind[kind], n)]
    for i, item in enumerate(picked, 1):
        cases.append(
            {
                "id": f"u{i:02d}",
                "nguon": "unanswerable",
                "loai": item["loai"],
                "lang": normalize_case_lang(item.get("lang")),
                "query": str(item["query"]),
                "expected": [],
            }
        )
    return cases


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * len(ordered)) - 1))]


def cmd_gen(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if out.exists() and not args.force and any(i.get("nhan_tay") for i in read_items(out)):
        print(f"{out} đã có nhãn tay — thêm --force nếu thật sự muốn sinh lại.", file=sys.stderr)
        return 2

    chunks = load_kb()
    by_id = {chunk.doc_id: chunk for chunk in chunks}
    cases = pick_cases()

    embedder = EmbeddingClient()
    if not embedder.available:
        print("Thiếu GEMINI_API_KEY — truyền --env-file.", file=sys.stderr)
        return 2
    try:
        vectors = embedder.embed_all([chunk.embedding_text for chunk in chunks])
        embedder.embed_all([case["query"] for case in cases])
    except EmbeddingError as error:
        print(f"Sinh embedding thất bại: {error}", file=sys.stderr)
        return 1

    bm25 = BM25Index()
    bm25.load(chunks)
    store = VectorStore()
    store.load(chunks, vectors)
    failures: list[str] = []
    retriever = HybridRetriever(
        bm25, store, embedder, on_embedding_error=lambda q, e: failures.append(f"{q!r}: {e}")
    )
    chat = ChatClient(
        os.environ.get("GEMINI_API_KEY"),
        model=GEN_MODEL,
        base_url=GEMINI_BASE_URL,
        max_tokens=800,
        temperature=0.7,
    )

    items: list[dict] = []
    latencies: list[float] = []
    for case in cases:
        top = retriever.retrieve(case["query"], TOP_K, case["lang"])
        ids = [chunk.doc_id for chunk in top]
        try:
            reply = chat.complete(system_prompt(top, case["lang"]), case["query"])
        except LlmError as error:
            print(f"{case['id']}: {error}", file=sys.stderr)
            return 1
        latencies.append(reply.latency_ms)
        rank = next((r for r, d in enumerate(ids, 1) if d in case["expected"]), None)
        items.append(
            {
                "id": case["id"],
                "nguon": case["nguon"],
                "loai": case["loai"],
                "query": case["query"],
                "expected": case["expected"],
                "chunks": ids,
                "hang_chunk_dung": rank,
                "tra_loi": reply.text.strip(),
                "latency_ms": round(reply.latency_ms),
                "nhan_tay": "",
                "ghi_chu": "",
            }
        )
        took = "cache" if reply.cached else f"{reply.latency_ms:5.0f}ms"
        print(f"{case['id']} {took}  {case['query'][:60]}")

    if failures:
        print(f"{len(failures)} lời gọi embedding hỏng — không ghi file.", file=sys.stderr)
        return 1
    unknown = {d for item in items for d in item["chunks"] if d not in by_id}
    assert not unknown, unknown

    write_items(out, items)
    golden = [i for i in items if i["nguon"] == "golden"]
    print(
        f"\nĐã ghi {out.relative_to(ROOT)}: {len(items)} câu. Lời gọi chat {chat.api_calls}, "
        f"embedding {embedder.api_calls}."
    )
    found = sum(item["hang_chunk_dung"] is not None for item in golden)
    print(f"Chunk đúng nằm trong top-{TOP_K}: {found}/{len(golden)} câu golden.")
    p50, p95 = percentile(latencies, 0.5), percentile(latencies, 0.95)
    print(f"Độ trễ sinh: p50 {p50:.0f} ms, p95 {p95:.0f} ms.")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    path = Path(args.out)
    items = read_items(path)
    missing = [item["id"] for item in items if item.get("nhan_tay") not in LABELS]
    if missing:
        print(f"Chấm tay trước. Còn {len(missing)} câu thiếu nhan_tay: {missing}", file=sys.stderr)
        return 2

    by_id = {chunk.doc_id: chunk for chunk in load_kb()}
    judge = ChatClient(
        os.environ.get("GROQ_API_KEY"),
        model=JUDGE_MODEL,
        base_url=GROQ_BASE_URL,
        max_tokens=2000,
        temperature=0,
        extra_body={"reasoning_effort": "low", "response_format": {"type": "json_object"}},
    )
    for item in items:
        context = rag_context([by_id[d] for d in item["chunks"]])
        try:
            reply = judge.complete(RUBRIC, judge_prompt(item["query"], context, item["tra_loi"]))
            item["nhan_judge"], item["ly_do_judge"] = parse_label(reply.text)
        except (LlmError, ValueError) as error:
            print(f"{item['id']}: {error}", file=sys.stderr)
            return 1
    write_items(path, items)

    result = agreement([(item["nhan_tay"], item["nhan_judge"]) for item in items])
    print(f"\nJudge {JUDGE_MODEL} so với chấm tay, {result.n} câu:")
    print(f"  cùng nhãn        {result.exact}/{result.n} = {result.exact / result.n:.0%}")
    print(f"  cùng ý có bịa    {result.bia_match}/{result.n} = {result.bia_match / result.n:.0%}")
    print("\nMa trận (hàng = tay, cột = judge):")
    print(" " * 14 + "".join(f"{label:>14}" for label in LABELS))
    for human in LABELS:
        print(f"{human:<14}" + "".join(f"{result.confusion[(human, j)]:>14}" for j in LABELS))
    print("\nCâu lệch:")
    for item in items:
        if item["nhan_tay"] != item["nhan_judge"]:
            labels = f"tay={item['nhan_tay']} judge={item['nhan_judge']}"
            print(f"  {item['id']} {labels}  {item['query'][:50]}")
            print(f"      judge: {item['ly_do_judge']}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Tầng sinh có bịa không (tuần 9)")
    parser.add_argument("command", choices=("gen", "judge"))
    parser.add_argument("--env-file", help="file .env chứa GEMINI_API_KEY / GROQ_API_KEY")
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--force", action="store_true", help="gen: ghi đè cả khi đã có nhãn tay")
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    return cmd_gen(args) if args.command == "gen" else cmd_judge(args)


if __name__ == "__main__":
    raise SystemExit(main())
