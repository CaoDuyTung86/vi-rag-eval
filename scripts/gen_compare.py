"""Tuần 10: đổi model ở tầng sinh, xem bịa thêm bao nhiêu và nhanh chậm ra sao.

    python scripts/gen_compare.py gen   --model qwen3.5:9b
    python scripts/gen_compare.py gen   --model qwen3.5:9b --prompt khong_noi_manh
    python scripts/gen_compare.py gen   --model qwen3.5:9b --prompt khong_noi_manh --temperature 0
    python scripts/gen_compare.py gen   --model gemini --env-file ../WebProject/.env
    python scripts/gen_compare.py judge --model qwen3.5:9b --env-file ../WebProject/.env
    python scripts/gen_compare.py cham  --model qwen3.5:9b
    python scripts/gen_compare.py bang

Một biến duy nhất mỗi lần chạy. Mặc định biến ấy là model sinh câu trả lời; `--prompt <tên>` đổi
biến sang một biến thể prompt trong data/prompts/vigotrip_chat_<tên>.txt và giữ nguyên model.
Đừng đổi cả hai trong một lần: bảng sẽ không nói được cái nào gây ra chênh lệch.

Câu hỏi, chunk, top-k giữ nguyên
của tuần 9. `--temperature` đổi được nhiệt độ: production chạy 0.7 và bảng tuần 10 đo ở đó,
nhưng kết luận 16/09 (e) là một mẻ ở 0.7 không xếp hạng được — chênh lệch giữa hai mẻ của
CÙNG một cấu hình lớn hơn chênh lệch giữa hai cấu hình. So hai prompt thì chạy ở 0 — `chunks` đọc thẳng từ data/faithfulness.yml, KHÔNG chạy lại retrieval, nên lệnh `gen`
tốn 0 lời gọi embedding và chênh lệch giữa các model không thể do bốc tài liệu khác nhau.

`--model` nhận: `gemini` (cấu hình tầng CHAT của VigoTrip, đọc cache tuần 9 nên 0 lời gọi), `groq`,
hoặc bất kỳ tag Ollama nào (`qwen3.5:9b`, `qwen3:8b`, `glm4:9b`) — tag lạ thì gọi $OLLAMA_BASE_URL,
mặc định http://127.0.0.1:11434/v1, key giả vì Ollama không kiểm. Server phải đang chạy
(`ollama serve`); lời gọi đầu nạp model vào VRAM nên lâu hơn hẳn các lời sau.

Model local chạy với `reasoning_effort: none` — xem chú thích ở cmd_gen. Bật suy nghĩ là một
thí nghiệm khác, cần mục riêng trong experiments.md.

CẢNH BÁO khi --model groq: bên sinh trùng model với judge (`openai/gpt-oss-120b`), tức là nó tự
chấm bài mình. Tuần 9 cố ý tránh chuyện đó. Dòng groq trong bảng chỉ để tham khảo, không dùng để
kết luận model nào bịa ít hơn.

Judge chỉ là BỘ LỌC (kết luận tuần 9: v3 báo bịa giả 3/20 ở bộ xác nhận). Nó nói không bịa thì tin;
nói bịa thì `judge` để trống `nhan_tay` cho bạn chấm lại, và `bang` đếm riêng hai con số.
Chạy từ gốc repo.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from faithfulness import (  # noqa: E402
    BO,
    GEN_MODEL,
    JUDGE_MODEL,
    judge_client,
    percentile,
    pick_dev_cases,
    read_items,
    write_items,
)

from eval.corpus import ROOT, load_kb  # noqa: E402
from eval.judge import (  # noqa: E402
    LABELS,
    RUBRIC,
    RUBRIC_VERSION,
    judge_prompt,
    parse_label,
)
from rag.generate import prompt_file, rag_context, system_prompt  # noqa: E402
from rag.llm import (  # noqa: E402
    DEFAULT_MIN_INTERVAL_S,
    GEMINI_BASE_URL,
    GROQ_BASE_URL,
    ChatClient,
    LlmError,
    load_env_file,
)

OUT_DIR = ROOT / "data" / "gen_compare"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
OLLAMA_BIN = os.environ.get("OLLAMA_BIN", "ollama")
# Nhiệt độ tầng CHAT của VigoTrip, cũng là nhiệt độ bảng tuần 10 đã đo.
DEFAULT_TEMPERATURE = 0.7

HEADER = """\
# {n} câu trả lời do {model} sinh với prompt {prompt}, trên ĐÚNG các chunk của
# data/faithfulness.yml. Sinh bằng scripts/gen_compare.py. Xem experiments.md 16/09 và 17/09.
#
# nhan_judge do judge v3 gắn. Judge chỉ là bộ lọc: câu nào nó gắn `bia` thì nhan_tay để trống chờ
# bạn chấm lại (điền co_can_cu / bia / tu_choi_dung / tu_choi_thua). Câu nó KHÔNG gắn bia thì
# nhan_tay = nhan_judge luôn, không cần đọc.
"""


@dataclass(frozen=True, slots=True)
class Provider:
    name: str
    model: str
    base_url: str
    api_key: str
    local: bool


def provider(name: str) -> Provider:
    if name == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        return Provider(name, GEN_MODEL, GEMINI_BASE_URL, key, False)
    if name == "groq":
        key = os.environ.get("GROQ_API_KEY", "")
        return Provider(name, JUDGE_MODEL, GROQ_BASE_URL, key, False)
    # Còn lại là tag Ollama. Key giả: Ollama không kiểm, nhưng ChatClient.available cần khác rỗng.
    return Provider(name, name, OLLAMA_BASE_URL, "ollama", True)


def slug(name: str) -> str:
    return name.replace(":", "-").replace("/", "-")


def out_path(name: str, prompt: str | None = None, temperature: float = DEFAULT_TEMPERATURE) -> Path:
    """Mỗi tổ hợp (model, prompt, nhiệt độ) một file: bảng so được, không đè nhau."""
    stem = slug(name) if prompt is None else f"{slug(name)}__{slug(prompt)}"
    if temperature != DEFAULT_TEMPERATURE:
        stem += f"__t{temperature:g}"
    return OUT_DIR / f"{stem}.yml"


def ollama_ps(model: str) -> str | None:
    """Dòng `ollama ps` của model đang nạp — cột SIZE và PROCESSOR là VRAM và phần chạy trên GPU."""
    try:
        run = subprocess.run(
            [OLLAMA_BIN, "ps"], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in run.stdout.splitlines()[1:]:
        parts = line.split()
        if parts and parts[0] == model:
            return " ".join(parts)
    return None


# ------------------------------------------------------------------ gen


def cmd_gen(args: argparse.Namespace) -> int:
    p = provider(args.model)
    # Dừng ngay nếu tên biến thể sai, trước khi nạp model vào VRAM.
    prompt_path = prompt_file(args.prompt)
    out = out_path(p.name, args.prompt, args.temperature)
    if out.exists() and not args.force:
        print(f"{out} đã có — thêm --force nếu muốn sinh lại.", file=sys.stderr)
        return 2
    if not p.api_key:
        # Không chặn: câu nào đã có trong cache đĩa vẫn chạy được, và dòng gemini của tuần 10
        # nằm trọn trong cache tuần 9 — hết hạn mức vẫn dựng lại được bảng.
        print(
            f"Không có API key cho {p.name} — chỉ những câu đã có trong cache mới chạy được.",
            file=sys.stderr,
        )
    if p.name == "groq":
        print(
            "CẢNH BÁO: groq sinh bằng đúng model mà judge dùng, nó tự chấm bài mình.\n"
            "          Dòng này chỉ để tham khảo, không dùng để kết luận.\n",
            file=sys.stderr,
        )

    src = read_items(BO["dev"])
    cases = {case["id"]: case for case in pick_dev_cases()}
    lech = [i["id"] for i in src if cases.get(i["id"], {}).get("query") != i["query"]]
    if lech:
        print(
            f"Bộ dev không dựng lại được như cũ, {len(lech)} câu lệch: {lech}.\n"
            "Dừng: sinh tiếp sẽ dùng lang sai, prompt khác tuần 9, hai bảng hết so được.",
            file=sys.stderr,
        )
        return 1

    by_id = {chunk.doc_id: chunk for chunk in load_kb()}
    chat = ChatClient(
        p.api_key,
        model=p.model,
        base_url=p.base_url,
        max_tokens=800,
        temperature=args.temperature,
        # Model local họ Qwen3.5 mặc định BẬT suy nghĩ: nó tiêu hết max_tokens cho phần `reasoning`
        # rồi trả `content` rỗng. Gemini tuần 9 chạy không có ngân sách suy nghĩ, nên muốn giữ đúng
        # một biến thì phải tắt. `reasoning_effort: none` là khoá duy nhất Ollama nhận ở đường /v1
        # (`think` và `chat_template_kwargs` bị bỏ qua) — cũng là đường VigoTrip đi qua
        # OpenAiCompatibleProvider. Khoá này nằm trong body nên vào cả khoá cache.
        extra_body={"reasoning_effort": "none"} if p.local else None,
        # Local không có hạn mức; lời gọi đầu còn phải nạp model vào VRAM nên cho chờ lâu.
        min_interval_s=0.0 if p.local else DEFAULT_MIN_INTERVAL_S,
        timeout_s=600.0 if p.local else 120.0,
    )

    items: list[dict] = []
    latencies: list[float] = []
    speeds: list[float] = []
    tu_cache = 0
    ps_line: str | None = None
    for src_item in src:
        chunks = [by_id[doc_id] for doc_id in src_item["chunks"]]
        lang = cases[src_item["id"]]["lang"]
        try:
            reply = chat.complete(
                system_prompt(chunks, lang, variant=args.prompt), src_item["query"]
            )
        except LlmError as error:
            print(f"{src_item['id']}: {error}", file=sys.stderr)
            return 1
        if p.local and ps_line is None:
            ps_line = ollama_ps(p.model)

        # Độ trễ trong cache là con số đo được lúc gọi thật, nên vẫn tính vào p50/p95 — chỉ đếm
        # riêng xem bao nhiêu câu lấy từ cache để người đọc biết bảng không đo trong một lần chạy.
        latencies.append(reply.latency_ms)
        tu_cache += reply.cached
        speed = None
        if reply.completion_tokens and reply.latency_ms > 0:
            speed = reply.completion_tokens / (reply.latency_ms / 1000)
            speeds.append(speed)

        items.append(
            {
                "id": src_item["id"],
                "nguon": src_item["nguon"],
                "loai": src_item["loai"],
                "query": src_item["query"],
                "expected": src_item["expected"],
                "chunks": src_item["chunks"],
                "hang_chunk_dung": src_item["hang_chunk_dung"],
                "tra_loi": reply.text.strip(),
                "latency_ms": round(reply.latency_ms),
                "completion_tokens": reply.completion_tokens,
                "tokens_per_s": round(speed, 1) if speed else None,
                "nhan_tay": "",
                "ghi_chu": "",
            }
        )
        took = "cache" if reply.cached else f"{reply.latency_ms:6.0f}ms"
        print(f"{src_item['id']} {took}  {src_item['query'][:58]}")

    meta = {
        "model": p.model,
        "prompt": prompt_path.name,
        "temperature": args.temperature,
        "base_url": p.base_url,
        "suy_nghi": "tat" if p.local else None,
        "goi_that": chat.api_calls,
        "tu_cache": tu_cache,
        "ollama_ps": ps_line,
        "p50_ms": round(percentile(latencies, 0.5)) if latencies else None,
        "p95_ms": round(percentile(latencies, 0.95)) if latencies else None,
        "tokens_per_s_trung_vi": round(percentile(speeds, 0.5), 1) if speeds else None,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_items(
        out,
        [{"_meta": meta}, *items],
        HEADER.format(n=len(items), model=p.model, prompt=prompt_path.name),
    )
    print(f"\nĐã ghi {out.relative_to(ROOT)}: {len(items)} câu, {chat.api_calls} lời gọi thật.")
    for key, value in meta.items():
        if key not in ("model", "base_url"):
            print(f"  {key:<22} {value}")
    if not speeds:
        print("  (không có token/giây: đọc hết từ cache, hoặc endpoint không trả usage)")
    return 0


# ------------------------------------------------------------------ judge


def split_meta(rows: list[dict]) -> tuple[dict, list[dict]]:
    if rows and "_meta" in rows[0]:
        return dict(rows[0]["_meta"]), rows[1:]
    return {}, rows


def cmd_judge(args: argparse.Namespace) -> int:
    path = out_path(args.model, args.prompt, args.temperature)
    if not path.exists():
        print(f"Chưa có {path} — chạy gen --model {args.model} trước.", file=sys.stderr)
        return 2
    meta, items = split_meta(read_items(path))

    # Dòng gemini sinh lại từ cache tuần 9 nên câu trả lời trùng NGUYÊN VĂN. Trùng hết thì chép
    # thẳng nhãn judge v3 và nhãn tay của tuần 9 sang, không gọi Groq lần nữa: vừa đỡ 30 lượt,
    # vừa chắc chắn hai bảng dùng đúng một bộ nhãn thay vì hai lần chấm có thể lệch nhau.
    w9 = {i["id"]: i for i in read_items(BO["dev"])}
    if all(w9.get(i["id"], {}).get("tra_loi", "").strip() == i["tra_loi"].strip() for i in items):
        for item in items:
            src = w9[item["id"]]
            for key in ("nhan_judge", "ly_do_judge", "nhan_tay", "rubric"):
                item[key] = src.get(key, "")
        write_items(
            path,
            [{"_meta": meta}, *items],
            HEADER.format(n=len(items), model=args.model, prompt=meta.get("prompt", "?")),
        )
        print(f"{args.model}: trùng nguyên văn tuần 9 — chép nhãn sẵn có, 0 lời gọi Groq.")
        return 0

    by_id = {chunk.doc_id: chunk for chunk in load_kb()}
    # Judge mặc định vẫn là Groq. Tên khác được hiểu là tag Ollama, tức judge chạy trên máy
    # mình: 0 lượt API, đổi lại nó yếu hơn (16/09 (f): qwen cùng nhãn 65–70% so với Groq 80%,
    # báo bịa giả 5 so với 3). Judge nào cũng chỉ là BỘ LỌC, nhãn tay mới là thước.
    judge = judge_client(args.judge_model)
    for item in items:
        context = rag_context([by_id[doc_id] for doc_id in item["chunks"]])
        try:
            reply = judge.complete(RUBRIC, judge_prompt(item["query"], context, item["tra_loi"]))
            item["nhan_judge"], item["ly_do_judge"] = parse_label(reply.text)
            item["rubric"] = RUBRIC_VERSION
        except (LlmError, ValueError) as error:
            print(f"{item['id']}: {error}", file=sys.stderr)
            return 1
        # Judge không gắn bịa thì tin nó. Gắn bịa thì để trống cho người đọc lại.
        if item["nhan_judge"] != "bia":
            item["nhan_tay"] = item["nhan_judge"]
        elif item["nhan_tay"] not in LABELS:
            item["nhan_tay"] = ""

    write_items(
        path,
        [{"_meta": meta}, *items],
        HEADER.format(n=len(items), model=args.model, prompt=meta.get("prompt", "?")),
    )
    cho_cham = [i["id"] for i in items if not i["nhan_tay"]]
    print(f"\n{args.model}: judge {RUBRIC_VERSION} ({args.judge_model}) xong, "
          f"{judge.api_calls} lời gọi.")
    print(f"  judge gắn bịa    {sum(i['nhan_judge'] == 'bia' for i in items)} câu")
    print(f"  chờ bạn chấm     {len(cho_cham)} câu: {cho_cham}")
    for item in items:
        if item["nhan_judge"] == "bia":
            print(f"\n  {item['id']}  {item['query'][:60]}")
            print(f"     judge: {item['ly_do_judge']}")
    return 0


# ------------------------------------------------------------------ chấm tay


def cmd_cham(args: argparse.Namespace) -> int:
    """In các câu judge gắn bịa kèm đúng chunk nó đọc, để người chấm không phải mở file."""
    path = out_path(args.model, args.prompt, args.temperature)
    if not path.exists():
        print(f"Chưa có {path}.", file=sys.stderr)
        return 2
    _, items = split_meta(read_items(path))
    by_id = {chunk.doc_id: chunk for chunk in load_kb()}
    cho = [i for i in items if not i["nhan_tay"]]
    if not cho:
        print(f"{args.model}: không còn câu nào chờ chấm.")
        return 0

    print(f"{args.model}: {len(cho)} câu chờ bạn chấm. Điền `nhan_tay` trong {path}.")
    print("Nhãn: co_can_cu · bia · tu_choi_dung · tu_choi_thua")
    print("Mỗi ý trong câu trả lời: ý đó có nằm trong chunk bên dưới không?")
    print("Khách hỏi ngoài phạm vi mà bot từ chối là tu_choi_dung, KHÔNG phải bịa.")
    for item in cho:
        print("=" * 78)
        print(f"{item['id']}  {item['query']}")
        print()
        print(f"  judge nói: {item['ly_do_judge']}")
        print()
        print("  --- CÂU TRẢ LỜI ---")
        print(item["tra_loi"])
        print()
        print("  --- CHUNK BOT ĐƯỢC ĐỌC ---")
        for doc_id in item["chunks"]:
            print()
            chunk = by_id[doc_id]
            print(f"  [{doc_id}] {chunk.title} — {chunk.content.strip()}")
        print()
    return 0


# ------------------------------------------------------------------ bảng


def cmd_bang(args: argparse.Namespace) -> int:
    paths = sorted(OUT_DIR.glob("*.yml")) if OUT_DIR.exists() else []
    if not paths:
        print(f"Chưa có file nào trong {OUT_DIR}.", file=sys.stderr)
        return 2

    head = [
        "model",
        "prompt",
        "t",
        "bia(judge)",
        "bia(tay)",
        "tu_choi_thua",
        "co_can_cu",
        "tok/s",
        "p50",
        "p95",
        "VRAM",
    ]
    rows: list[list[str]] = []
    for path in paths:
        meta, items = split_meta(read_items(path))
        judged = [i for i in items if i.get("nhan_judge")]
        prompt_name = str(meta.get("prompt") or "vigotrip_chat.txt").removeprefix(
            "vigotrip_chat"
        ).removesuffix(".txt").lstrip("_") or "production"
        temp = f'{meta.get("temperature", DEFAULT_TEMPERATURE):g}'
        if not judged:
            rows.append([path.stem, prompt_name, temp, "chưa judge", "", "", "", "", "", "", ""])
            continue
        bia_judge = [i for i in judged if i["nhan_judge"] == "bia"]
        cho = sum(1 for i in bia_judge if not i["nhan_tay"])
        bia_tay = sum(1 for i in judged if i["nhan_tay"] == "bia")
        parts = (meta.get("ollama_ps") or "").split()
        rows.append(
            [
                str(meta.get("model") or path.stem),
                prompt_name,
                temp,
                f"{len(bia_judge)}/{len(judged)}",
                str(bia_tay) + (f" (+{cho} chưa chấm)" if cho else ""),
                str(sum(1 for i in judged if i["nhan_tay"] == "tu_choi_thua")),
                str(sum(1 for i in judged if i["nhan_tay"] == "co_can_cu")),
                str(meta.get("tokens_per_s_trung_vi") or "—"),
                str(meta.get("p50_ms") or "—"),
                str(meta.get("p95_ms") or "—"),
                " ".join(parts[2:5]) if len(parts) >= 5 else "—",
            ]
        )

    widths = [max(len(row[c]) for row in [head, *rows]) for c in range(len(head))]
    for row in [head, *rows]:
        print("  ".join(cell.ljust(widths[c]) for c, cell in enumerate(row)).rstrip())
    print("\nGemini tuần 9 làm mốc: bia 1/30, co_can_cu 15, tu_choi_dung 14.")
    print("bia(tay) chỉ đếm câu ĐÃ chấm lại; còn 'chưa chấm' thì chưa dùng để kết luận được.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="So model ở tầng sinh (tuần 10)")
    parser.add_argument("command", choices=("gen", "judge", "cham", "bang"))
    parser.add_argument("--model", help="gemini | groq | tag Ollama, ví dụ qwen3.5:9b")
    parser.add_argument("--env-file", help="file .env chứa GEMINI_API_KEY / GROQ_API_KEY")
    parser.add_argument(
        "--prompt",
        help="biến thể prompt trong data/prompts/vigotrip_chat_<tên>.txt; bỏ trống = bản production",
    )
    parser.add_argument(
        "--judge-model",
        default="groq",
        help="groq (mặc định) hoặc một tag Ollama để chấm trên máy mình, ví dụ qwen3.5:9b",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="nhiệt độ tầng sinh; mặc định 0.7 như production, dùng 0 khi so hai prompt",
    )
    parser.add_argument("--force", action="store_true", help="gen: ghi đè file đã có")
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    if args.command == "bang":
        return cmd_bang(args)
    if not args.model:
        parser.error(f"{args.command} cần --model")
    if args.command == "gen":
        return cmd_gen(args)
    return cmd_cham(args) if args.command == "cham" else cmd_judge(args)


if __name__ == "__main__":
    raise SystemExit(main())
