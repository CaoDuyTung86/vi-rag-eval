"""Tuần 9: tầng sinh có bịa không — sinh câu trả lời, rồi đo LLM-judge so với chấm tay.

    python scripts/faithfulness.py gen --bo dev --env-file ../WebProject/.env      # 30 câu tự nhiên
    python scripts/faithfulness.py gen --bo xacnhan --env-file ../WebProject/.env  # 20 câu
    # mở file của bộ, điền nhan_tay cho mọi câu
    python scripts/faithfulness.py judge --bo xacnhan --env-file ../WebProject/.env

Hai bộ, hai vai (experiments.md 15/09):
  dev      data/faithfulness.yml — 30 câu đã dùng để viết rubric v2. Chạy judge ở đây chỉ để kiểm
           tra không tụt.
  xacnhan  data/faithfulness_xacnhan.yml — 20 câu chưa ai nhìn, trong đó 8 câu có bịa do Gemini
           cài. Tiêu chí đạt tuần 9 tính trên bộ này. Kiểu cài nằm ở
           data/faithfulness_xacnhan_dapan.yml — không mở trước khi chấm xong.

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
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.corpus import ROOT, load_golden, load_kb, normalize_case_lang  # noqa: E402
from eval.judge import (  # noqa: E402
    LABELS,
    RUBRIC,
    RUBRIC_VERSION,
    agreement,
    judge_prompt,
    parse_label,
)
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

BO = {
    "dev": ROOT / "data" / "faithfulness.yml",
    "xacnhan": ROOT / "data" / "faithfulness_xacnhan.yml",
}
DAPAN = ROOT / "data" / "faithfulness_xacnhan_dapan.yml"
UNANSWERABLE = ROOT / "data" / "unanswerable.yml"
HOLDOUT = ROOT / "data" / "holdout.yml"

GEN_MODEL = "gemini-flash-lite-latest"
JUDGE_MODEL = "openai/gpt-oss-120b"

# ------------------------------------------------------------------ bộ dev (14/09, không đổi)

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

# ------------------------------------------------------------------ bộ xác nhận (15/09)

XACNHAN_SEED = 15
XACNHAN_UNANSWERABLE_MIX = {"kb_khong_co": 2, "can_tool": 1, "ngoai_le": 1}
# Mỗi kiểu 2 câu. Hai kiểu giữa là nghịch đảo đúng hai lỗi judge v1 mắc trên bộ dev (g12, g13).
BIA_KIEU = {
    "doi_so": "đổi một con số, thời hạn hoặc mức phí thành giá trị khác với TÀI LIỆU",
    "them_quy_dinh": (
        "thêm một quy định nghe như chuẩn chung ngoài đời (giấy tờ phải mang, thời gian phải có "
        "mặt, điều kiện phải đáp ứng) mà TÀI LIỆU không nhắc tới"
    ),
    "bo_gioi_han": (
        "bỏ một cụm giới hạn hoặc điều kiện (như 'số lượng lớn', 'tối đa', 'nếu', 'thường') để "
        "câu nói rộng hơn TÀI LIỆU; nếu câu trả lời không có cụm nào như vậy thì nói một quy định "
        "áp dụng cho phạm vi rộng hơn TÀI LIỆU"
    ),
    "them_kenh": (
        "thêm một số điện thoại, địa chỉ email hoặc đường dẫn hỗ trợ cụ thể không có trong "
        "TÀI LIỆU"
    ),
}
PERTURB = """Bạn tạo dữ liệu kiểm thử cho một bộ chấm độ trung thực. Bạn nhận TÀI LIỆU và một CÂU \
TRẢ LỜI có căn cứ. Viết lại câu trả lời, giữ giọng văn và độ dài gần như cũ, nhưng cài đúng MỘT \
lỗi bịa theo kiểu sau: {kieu}. Lỗi phải là thông tin cụ thể, nghe hợp lý, không lộ liễu, và không \
đúng với TÀI LIỆU. Chỉ trả về câu trả lời đã viết lại, không giải thích, không đánh dấu chỗ sửa."""

HEADER = """\
# Tuần 9 — {n} cặp câu hỏi / câu trả lời để chấm tay. Sinh bằng scripts/faithfulness.py gen.
#
# Việc của bạn: điền nhan_tay cho từng câu (ghi_chu tuỳ ý). Đọc chunks trong data/kb/faq-vi.yml
# theo docId — chatbot chỉ được đọc đúng các chunk đó, không hơn.
#
#   co_can_cu     có đưa thông tin, và mọi thông tin cụ thể về VigoTrip đều có trong chunks
#   bia           có ÍT NHẤT một thông tin cụ thể không có trong chunks, hoặc trái với chunks
#   tu_choi_dung  không đưa thông tin (từ chối, hỏi lại, mời liên hệ) và chunks đúng là không đủ
#   tu_choi_thua  không đưa thông tin, trong khi chunks đủ để trả lời
#
# Rubric đầy đủ judge dùng: eval/judge.py. Chấm xong mọi câu mới chạy `judge`.
"""
HEADER_XACNHAN = """\
#
# BỘ XÁC NHẬN: một số câu trả lời đã bị cài bịa, thứ tự đã xáo. Chấm như câu bình thường, và KHÔNG
# mở data/faithfulness_xacnhan_dapan.yml trước khi chấm xong.
"""


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str)


def write_items(path: Path, items: list[dict], header: str) -> None:
    body = yaml.dump(items, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=100)
    path.write_text(header + "\n" + body, encoding="utf-8")


def read_items(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def _unanswerable_by_kind(exclude: set[str]) -> dict[str, list[dict]]:
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for item in yaml.safe_load(UNANSWERABLE.read_text(encoding="utf-8")):
        if str(item["query"]) not in exclude:
            by_kind[item["loai"]].append(item)
    return by_kind


def _unanswerable_case(item: dict) -> dict:
    return {
        "nguon": "unanswerable",
        "loai": item["loai"],
        "lang": normalize_case_lang(item.get("lang")),
        "query": str(item["query"]),
        "expected": [],
        "cai_bia": None,
    }


def _golden_case(query: str, expected: list[str], nguon: str, cai_bia: str | None = None) -> dict:
    return {
        "nguon": nguon,
        "loai": "co_tai_lieu",
        "lang": "vi",
        "query": query,
        "expected": expected,
        "cai_bia": cai_bia,
    }


def pick_dev_cases() -> list[dict]:
    rng = random.Random(SEED)
    golden = [case for case in load_golden() if case.lang == "vi"]
    cases = [
        {"id": f"g{i:02d}", **_golden_case(c.query, list(c.expected), "golden")}
        for i, c in enumerate(rng.sample(golden, GOLDEN_N), 1)
    ]
    by_kind = _unanswerable_by_kind(set())
    picked = [item for kind, n in UNANSWERABLE_MIX.items() for item in rng.sample(by_kind[kind], n)]
    cases += [{"id": f"u{i:02d}", **_unanswerable_case(item)} for i, item in enumerate(picked, 1)]
    return cases


def _holdout_real_vi() -> list[dict]:
    """Phần "người thật gõ" của holdout.yml — nằm sau dòng kẻ có nhãn đó."""
    text = HOLDOUT.read_text(encoding="utf-8")
    marker = re.search(r"^# -+ người thật gõ\s*$", text, re.M)
    if marker is None:
        raise ValueError("holdout.yml không còn dòng kẻ 'người thật gõ'")
    entries = yaml.safe_load(text[marker.end() :]) or []
    return [e for e in entries if e.get("query") and normalize_case_lang(e.get("lang")) == "vi"]


def pick_xacnhan_cases(used: set[str]) -> list[dict]:
    rng = random.Random(XACNHAN_SEED)
    golden = [c for c in load_golden() if c.lang == "vi" and c.query not in used]
    golden = rng.sample(golden, 4 + 2 * len(BIA_KIEU))
    real = [e for e in _holdout_real_vi() if str(e["query"]) not in used]

    cases = [
        _golden_case(str(e["query"]), [str(d) for d in e["expected"]], "holdout_that")
        for e in rng.sample(real, 4)
    ]
    by_kind = _unanswerable_by_kind(used)
    cases += [
        _unanswerable_case(item)
        for kind, n in XACNHAN_UNANSWERABLE_MIX.items()
        for item in rng.sample(by_kind[kind], n)
    ]
    cases += [_golden_case(c.query, list(c.expected), "golden") for c in golden[:4]]
    kinds = [kind for kind in BIA_KIEU for _ in range(2)]
    cases += [
        _golden_case(c.query, list(c.expected), "golden", kind)
        for c, kind in zip(golden[4:], kinds, strict=True)
    ]
    rng.shuffle(cases)
    return [{"id": f"x{i:02d}", **case} for i, case in enumerate(cases, 1)]


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * len(ordered)) - 1))]


def cmd_gen(args: argparse.Namespace) -> int:
    out = BO[args.bo]
    if out.exists() and not args.force and any(i.get("nhan_tay") for i in read_items(out)):
        print(f"{out} đã có nhãn tay — thêm --force nếu thật sự muốn sinh lại.", file=sys.stderr)
        return 2

    chunks = load_kb()
    by_id = {chunk.doc_id: chunk for chunk in chunks}
    if args.bo == "dev":
        cases = pick_dev_cases()
    else:
        cases = pick_xacnhan_cases({str(item["query"]) for item in read_items(BO["dev"])})

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
    dapan: list[dict] = []
    latencies: list[float] = []
    for case in cases:
        top = retriever.retrieve(case["query"], TOP_K, case["lang"])
        ids = [chunk.doc_id for chunk in top]
        try:
            reply = chat.complete(system_prompt(top, case["lang"]), case["query"])
            answer = reply.text.strip()
            original = answer
            if case["cai_bia"]:
                perturbed = chat.complete(
                    PERTURB.replace("{kieu}", BIA_KIEU[case["cai_bia"]]),
                    f"TÀI LIỆU:\n{rag_context(top)}\nCÂU TRẢ LỜI:\n{answer}",
                )
                answer = perturbed.text.strip()
        except LlmError as error:
            print(f"{case['id']}: {error}", file=sys.stderr)
            return 1
        latencies.append(reply.latency_ms)
        rank = next((r for r, d in enumerate(ids, 1) if d in case["expected"]), None)
        item = {"id": case["id"]}
        if args.bo == "dev":
            # Bộ xác nhận giấu nguồn và loại: "golden" lộ ra câu nào có thể bị cài bịa.
            item |= {"nguon": case["nguon"], "loai": case["loai"]}
        item |= {
            "query": case["query"],
            "expected": case["expected"],
            "chunks": ids,
            "hang_chunk_dung": rank,
            "tra_loi": answer,
            "latency_ms": round(reply.latency_ms),
            "nhan_tay": "",
            "ghi_chu": "",
        }
        items.append(item)
        dapan.append(
            {
                "id": case["id"],
                "nguon": case["nguon"],
                "loai": case["loai"],
                "cai_bia": case["cai_bia"],
                "tra_loi_goc": original if case["cai_bia"] else None,
            }
        )
        took = "cache" if reply.cached else f"{reply.latency_ms:5.0f}ms"
        print(f"{case['id']} {took}  {case['query'][:60]}")

    if failures:
        print(f"{len(failures)} lời gọi embedding hỏng — không ghi file.", file=sys.stderr)
        return 1
    unknown = {d for item in items for d in item["chunks"] if d not in by_id}
    assert not unknown, unknown

    header = HEADER.format(n=len(items))
    if args.bo == "xacnhan":
        header += HEADER_XACNHAN
        write_items(DAPAN, dapan, "# Đáp án bộ xác nhận — chỉ mở sau khi chấm tay xong.\n")
    write_items(out, items, header)
    with_answer = [i for i in items if i["expected"]]
    print(
        f"\nĐã ghi {out.relative_to(ROOT)}: {len(items)} câu. Lời gọi chat {chat.api_calls}, "
        f"embedding {embedder.api_calls}."
    )
    found = sum(item["hang_chunk_dung"] is not None for item in with_answer)
    print(f"Chunk đúng nằm trong top-{TOP_K}: {found}/{len(with_answer)} câu có tài liệu.")
    p50, p95 = percentile(latencies, 0.5), percentile(latencies, 0.95)
    print(f"Độ trễ sinh: p50 {p50:.0f} ms, p95 {p95:.0f} ms.")
    return 0


JUDGE_COMPARE_DIR = ROOT / "data" / "judge_compare"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
# Nhãn judge trong data/faithfulness*.yml là MỐC đã commit: judge Groq, rubric đã chốt. Mọi tổ hợp
# khác — judge khác, hoặc rubric đang thử — ghi sang data/judge_compare/ để mốc không bị một lần
# thử nghiệm đè lên. Chốt rubric mới thì sửa hằng số này rồi chạy lại để làm mới mốc.
RUBRIC_DA_CHOT = "v3"


def judge_client(name: str) -> ChatClient:
    """Judge mặc định là Groq. Tên khác được hiểu là tag Ollama, tức judge chạy trên máy mình.

    Có để trả lời câu "phòng thí nghiệm này chạy được khi không còn hạn mức API nào không".
    Tầng sinh và tầng nhúng đã có bản local; judge là chỗ cuối cùng còn buộc phải gọi ra ngoài.
    """
    if name == "groq":
        return ChatClient(
            os.environ.get("GROQ_API_KEY"),
            model=JUDGE_MODEL,
            base_url=GROQ_BASE_URL,
            # Rubric bắt judge liệt kê từng ý, medium nghĩ lâu hơn low: 2000 token dễ hết dở.
            max_tokens=4000,
            temperature=0,
            extra_body={"reasoning_effort": "medium", "response_format": {"type": "json_object"}},
        )
    return ChatClient(
        "ollama",
        model=name,
        base_url=OLLAMA_BASE_URL,
        max_tokens=4000,
        temperature=0,
        # Tắt suy nghĩ như tuần 10, và ép JSON để parse_label không phải đoán.
        extra_body={"reasoning_effort": "none", "response_format": {"type": "json_object"}},
        min_interval_s=0.0,
        timeout_s=600.0,
    )


def cmd_judge(args: argparse.Namespace) -> int:
    path = BO[args.bo]
    items = read_items(path)
    missing = [item["id"] for item in items if item.get("nhan_tay") not in LABELS]
    if missing:
        print(f"Chấm tay trước. Còn {len(missing)} câu thiếu nhan_tay: {missing}", file=sys.stderr)
        return 2

    by_id = {chunk.doc_id: chunk for chunk in load_kb()}
    judge = judge_client(args.judge_model)
    # Judge khác, hoặc rubric đang thử, thì GHI RA CHỖ KHÁC — xem RUBRIC_DA_CHOT.
    if args.judge_model != "groq" or RUBRIC_VERSION != RUBRIC_DA_CHOT:
        JUDGE_COMPARE_DIR.mkdir(parents=True, exist_ok=True)
        slug = args.judge_model.replace(":", "-")
        path = JUDGE_COMPARE_DIR / f"{args.bo}_{slug}_{RUBRIC_VERSION}.yml"
    for item in items:
        context = rag_context([by_id[d] for d in item["chunks"]])
        try:
            reply = judge.complete(RUBRIC, judge_prompt(item["query"], context, item["tra_loi"]))
            item["nhan_judge"], item["ly_do_judge"] = parse_label(reply.text)
            item["rubric"] = RUBRIC_VERSION
        except (LlmError, ValueError) as error:
            print(f"{item['id']}: {error}", file=sys.stderr)
            return 1
    header = HEADER.format(n=len(items)) + (HEADER_XACNHAN if args.bo == "xacnhan" else "")
    write_items(path, items, header)

    r = agreement([(item["nhan_tay"], item["nhan_judge"]) for item in items])
    print(
        f"\nJudge {judge.model} rubric {RUBRIC_VERSION}, bộ {args.bo}, "
        f"{r.n} câu, {judge.api_calls} lời gọi thật:"
    )
    print(f"  cùng nhãn        {r.exact}/{r.n} = {r.exact / r.n:.0%}")
    print(f"  bắt bịa          {r.bia_caught}/{r.bia_human} câu bạn chấm bia")
    print(f"  báo bịa giả      {r.bia_false} câu")
    print("\nMa trận (hàng = tay, cột = judge):")
    print(" " * 14 + "".join(f"{label:>14}" for label in LABELS))
    for human in LABELS:
        print(f"{human:<14}" + "".join(f"{r.confusion[(human, j)]:>14}" for j in LABELS))

    if args.bo == "xacnhan":
        missed = r.bia_human - r.bia_caught
        checks = [
            ("1. trượt tối đa 1 câu bịa", missed <= 1),
            ("2. báo bịa giả tối đa 1 câu", r.bia_false <= 1),
            ("3. cùng nhãn ≥ 80%", r.exact >= 0.8 * r.n),
        ]
        print("\nTiêu chí đạt (tiêu chí 4 xem ở lần chạy --bo dev):")
        for name, ok in checks:
            print(f"  {'ĐẠT ' if ok else 'TRƯỢT'} {name}")
        if DAPAN.exists():
            key = {entry["id"]: entry for entry in read_items(DAPAN)}
            caught: Counter[str] = Counter()
            total: Counter[str] = Counter()
            for item in items:
                kind = key[item["id"]]["cai_bia"]
                if kind:
                    total[kind] += 1
                    caught[kind] += item["nhan_judge"] == "bia"
            print("\nTheo kiểu cài (judge gắn bia / số câu cài; nhãn tay mới là đáp án):")
            for kind in BIA_KIEU:
                print(f"  {kind:<14} {caught[kind]}/{total[kind]}")

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
    parser.add_argument("--bo", choices=tuple(BO), default="dev", help="bộ câu hỏi")
    parser.add_argument("--env-file", help="file .env chứa GEMINI_API_KEY / GROQ_API_KEY")
    parser.add_argument(
        "--judge-model",
        default="groq",
        help="groq (mặc định) hoặc tag Ollama, ví dụ qwen3.5:9b — judge chạy trên máy mình",
    )
    parser.add_argument("--force", action="store_true", help="gen: ghi đè cả khi đã có nhãn tay")
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    return cmd_gen(args) if args.command == "gen" else cmd_judge(args)


if __name__ == "__main__":
    raise SystemExit(main())
