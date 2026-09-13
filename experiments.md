# Nhật ký thí nghiệm

Mỗi thay đổi có thể ảnh hưởng điểm số đều phải có một mục ở đây. Không ghi thì ba tuần
sau bạn sẽ không nhớ vì sao chunk size lại là 400 chứ không phải 600, và sẽ thử lại từ đầu.

Luật: **viết giả thuyết TRƯỚC khi chạy.** Viết sau khi thấy kết quả thì bạn chỉ đang kể
lại số liệu, không phải kiểm chứng điều gì.

---

## Mẫu

### YYYY-MM-DD — tên ngắn gọn

**Giả thuyết.** Điều bạn tin là đúng, và vì sao.

**Thay đổi.** Chính xác cái gì đổi. Một biến một lần.

**Kết quả.**

| Cấu hình | R@3 | MRR | p50 (ms) |
|---|---|---|---|
| baseline | | | |
| thử nghiệm | | | |

**Kết luận.** Giữ hay bỏ, và vì sao. Nếu bỏ thì ghi rõ điều kiện nào sẽ khiến bạn đổi ý.

---

## Đã lên lịch

| Tuần | Thí nghiệm | Câu hỏi cần trả lời |
|---|---|---|
| 6 | Chunk size, overlap, có/không nhét title vào phần đem nhúng | Cấu hình nào cho R@3 cao nhất, và trả giá bao nhiêu độ trễ |
| 7 | Cross-encoder rerank trên top-20 | Delta R@3 có đáng với delta độ trễ không (đặt ngân sách TRƯỚC khi đo) |
| 7 | FAISS/Qdrant thay quét tuyến tính | Ở 56 chunk thì gần như chắc chắn KHÔNG đáng — đo để chứng minh, rồi ghi lại ngưỡng corpus mà nó bắt đầu đáng |
| 8 | Bộ vàng tiếng Anh + đo chéo ngôn ngữ | Hỏi tiếng Anh trên kho tiếng Việt tụt bao nhiêu điểm |
| 8 | nDCG@5 | Có xếp hạng lại thứ tự ưu tiên sửa lỗi so với recall@3 không |
| 8 | Tách điểm theo 13 category | Category nào yếu nhất, và vì sao |
| 9 | LLM-judge cho groundedness | Judge đồng ý với bản chấm tay bao nhiêu phần trăm |
