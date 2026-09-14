"""Thống kê nhanh dữ liệu đã export. Chỉ in SỐ ĐẾM, không in nội dung tin nhắn."""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "private"


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")

    path = OUT / "chat_messages.csv"
    if not path.exists():
        sys.exit(f"Chưa có {path} — chạy scripts/export_neon.py trước.")

    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    roles = Counter(r["role"].lower() for r in rows)
    langs = Counter(r["lang"] for r in rows)
    days = sorted(r["created_at"][:10] for r in rows if r["created_at"])
    user_rows = [r for r in rows if r["role"].lower() in ("user", "human")]
    lengths = sorted(len(r["content"]) for r in user_rows)

    print(f"tổng dòng          : {len(rows)}")
    print(f"theo role          : {dict(roles)}")
    print(f"theo ngôn ngữ      : {dict(langs)}")
    print(f"số phiên (session) : {len({r['session_id'] for r in rows})}")
    if days:
        print(f"khoảng ngày        : {days[0]} -> {days[-1]}")
    print(f"câu hỏi người dùng : {len(user_rows)}")
    if lengths:
        print(
            f"độ dài câu hỏi     : min {lengths[0]}, trung vị {lengths[len(lengths) // 2]}, "
            f"max {lengths[-1]} ký tự"
        )

    print()
    print(f"Tuần 10 cần 300-500 câu gán nhãn. Hiện có {len(user_rows)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
