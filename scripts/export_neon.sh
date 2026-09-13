#!/usr/bin/env bash
# Xuất dữ liệu thật từ Neon ra CSV trước khi đóng băng đồ án.
#
# Chạy:
#   export NEON_URL='postgresql://user:pass@ep-xxx.neon.tech/dbname?sslmode=require'
#   bash scripts/export_neon.sh
#
# Lấy NEON_URL ở đâu: Neon Console > project > Connection string (chọn dạng psql/URI).
# KHÔNG dùng thẳng chuỗi SPRING_DATASOURCE_URL trong Render — đó là định dạng JDBC,
# psql không hiểu.
#
# Không cài được psql thì dùng Neon Console > SQL Editor: dán từng câu SELECT bên dưới
# rồi bấm nút tải CSV.

set -euo pipefail

: "${NEON_URL:?Chưa đặt NEON_URL}"

OUT="${1:-data/private}"
mkdir -p "$OUT"

dump() {
  local name="$1" sql="$2"
  echo "-> $OUT/$name.csv"
  psql "$NEON_URL" -c "\copy ($sql) TO '$OUT/$name.csv' WITH (FORMAT csv, HEADER true)"
}

# Lịch sử chat. CỐ TÌNH BỎ user_email: tuần 10 chỉ cần nội dung để gán nhãn ý định,
# và không mang dữ liệu định danh ra khỏi hệ thống là mặc định đúng.
# Đây là bảng gấp nhất — cron 3h sáng mỗi ngày xoá tin nhắn quá 30 ngày.
dump chat_messages "
  SELECT message_id, session_id, role, content, lang, message_ref, created_at
  FROM tin_nhan_chat
  ORDER BY created_at
"

# Số đo từng lượt chat: không nội dung, không danh tính. Giữ 90 ngày.
dump chat_turn_metrics "
  SELECT metric_id, created_at, lang, authenticated, streamed,
         latency_ms, question_chars, answer_chars, rag_chunks, outcome
  FROM chi_so_chat
  ORDER BY created_at
"

# Đánh giá 👍/👎. Nối được với chat_messages qua message_ref.
dump chat_feedback "
  SELECT feedback_id, message_ref, session_id, rating, reason,
         question_snippet, lang, created_at
  FROM phan_hoi_chat
  ORDER BY created_at
"

# Knowledge base như đang chạy thật (có thể đã lệch so với faq-vi.yml nếu từng sửa
# trực tiếp trong DB). Bỏ cột embedding_base64 — nặng và sinh lại được.
dump knowledge_chunks "
  SELECT chunk_id, doc_id, title, content, category, lang,
         embedding_model, dimensions, content_hash, active
  FROM tri_thuc
  ORDER BY doc_id
"

# Nhật ký thanh toán. Giữ 180 ngày. Không cần cho lộ trình học, nhưng là bằng chứng
# vận hành nếu sau này cần dẫn lại trong báo cáo.
dump payment_logs "
  SELECT * FROM nhat_ky_thanh_toan ORDER BY id
"

echo
echo "Xong. Kiểm tra số dòng:"
wc -l "$OUT"/*.csv
echo
echo "LƯU Ý: chat_messages.csv chứa nội dung người dùng gõ thật."
echo "Thư mục data/private/ đã nằm trong .gitignore — đừng đưa ra khỏi đó."
