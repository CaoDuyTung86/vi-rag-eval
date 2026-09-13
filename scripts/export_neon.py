"""Xuất dữ liệu thật từ Neon ra CSV trước khi đóng băng đồ án.

Dùng psycopg thay cho psql: không cần cài PostgreSQL client, không cần Docker.

    python scripts/export_neon.py

Đọc NEON_URL từ biến môi trường, hoặc từ file .env.neon cạnh repo (đã gitignore).
Lấy chuỗi kết nối ở Neon Console > project > Connection string (dạng URI).

Chỉ ĐỌC — không có câu lệnh ghi nào trong file này.
"""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "private"
ENV_FILE = ROOT / ".env.neon"

# (tên file, mô tả, câu SELECT)
EXPORTS: list[tuple[str, str, str]] = [
    (
        "chat_messages",
        "Lịch sử chat — CỐ TÌNH bỏ user_email: tuần 10 chỉ cần nội dung để gán nhãn ý "
        "định. Bảng gấp nhất: cron 3h sáng xoá tin nhắn quá CHAT_HISTORY_RETENTION_DAYS.",
        """
        SELECT message_id, session_id, role, content, lang, message_ref, created_at
        FROM tin_nhan_chat
        ORDER BY created_at
        """,
    ),
    (
        "chat_turn_metrics",
        "Số đo từng lượt chat: không nội dung, không danh tính. Giữ 90 ngày.",
        """
        SELECT metric_id, created_at, lang, authenticated, streamed,
               latency_ms, question_chars, answer_chars, rag_chunks, outcome
        FROM chi_so_chat
        ORDER BY created_at
        """,
    ),
    (
        "chat_feedback",
        "Đánh giá 👍/👎. Nối được với chat_messages qua message_ref.",
        """
        SELECT feedback_id, message_ref, session_id, rating, reason,
               question_snippet, lang, created_at
        FROM phan_hoi_chat
        ORDER BY created_at
        """,
    ),
    (
        "knowledge_chunks",
        "Knowledge base như đang chạy thật (có thể đã lệch so với faq-vi.yml nếu từng "
        "sửa trực tiếp trong DB). Bỏ embedding_base64 — nặng và sinh lại được.",
        """
        SELECT chunk_id, doc_id, title, content, category, lang,
               embedding_model, dimensions, content_hash, active
        FROM tri_thuc
        ORDER BY doc_id
        """,
    ),
    (
        "payment_logs",
        "Nhật ký thanh toán, giữ 180 ngày. Không cần cho lộ trình học, nhưng là bằng "
        "chứng vận hành nếu sau này cần dẫn lại trong báo cáo.",
        "SELECT * FROM nhat_ky_thanh_toan ORDER BY 1",
    ),
]


def load_url() -> str:
    url = os.environ.get("NEON_URL", "").strip()
    if url:
        return url
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*NEON_URL\s*=\s*(.+)\s*$", line)
            if m:
                return m.group(1).strip().strip("'\"")
    sys.exit(f"Chưa có NEON_URL (đặt biến môi trường hoặc ghi vào {ENV_FILE.name})")


def redact(url: str) -> str:
    return re.sub(r"//([^:]+):[^@]+@", r"//\1:***@", url)


def main() -> int:
    # Console Windows mặc định cp1252, không in được tiếng Việt có dấu.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    url = load_url()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Kết nối: {redact(url)}\n")
    total_rows = 0

    with psycopg.connect(url) as conn:
        for name, note, sql in EXPORTS:
            path = OUT_DIR / f"{name}.csv"
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    headers = [d.name for d in cur.description]
                    rows = cur.fetchall()
            except psycopg.Error as e:
                conn.rollback()
                print(f"  [bỏ qua] {name}: {str(e).strip().splitlines()[0]}")
                continue

            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(headers)
                w.writerows(rows)

            total_rows += len(rows)
            print(f"  {name + '.csv':<26} {len(rows):>6} dòng   # {note.splitlines()[0][:60]}")

    print(f"\nTổng {total_rows} dòng, ghi vào {OUT_DIR}")
    print("chat_messages.csv chứa nội dung người dùng gõ thật — data/private/ đã gitignore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
