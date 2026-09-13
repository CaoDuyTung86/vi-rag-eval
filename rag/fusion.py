"""Hợp nhất hai bảng xếp hạng bằng Reciprocal Rank Fusion.

TUẦN 2 — bạn viết hàm rrf(). Khoảng 20 dòng.

Tham chiếu: .../ai/rag/HybridRetriever.java (phương thức fuse/accumulate)

Vì sao RRF chứ không phải cộng điểm có trọng số: hai nhánh cho điểm trên hai thang
hoàn toàn khác nhau (cosine 0..1 so với BM25 không chặn trên). RRF chỉ dùng THỨ HẠNG
nên không cần chuẩn hoá, cũng không cần tự tay chỉnh trọng số — thứ mà với corpus cỡ
này thì có chỉnh cũng chỉ là đoán mò.
"""

from __future__ import annotations

from rag.types import Chunk, Scored

# Hằng số k trong tài liệu gốc của RRF (Cormack, Clarke, Buettcher 2009).
DEFAULT_RRF_K = 60


def rrf(branches: list[list[Scored]], top_k: int, k: int = DEFAULT_RRF_K) -> list[Chunk]:
    """Mỗi chunk cộng 1/(k + hạng) từ mỗi nhánh có mặt nó.

    Hạng tính từ 1, không phải 0. Chunk xuất hiện ở CẢ hai nhánh được đẩy lên trên một
    cách tự nhiên, không cần quy tắc riêng nào cho trường hợp đó.

    Suy giảm êm: một nhánh trả về rỗng (embedding hỏng, thiếu API key) thì kết quả rơi
    về đúng nhánh còn lại. Hàm này phải chịu được branches có nhánh rỗng.

    Gộp theo doc_id chứ không theo object — cùng một chunk đến từ hai nhánh là hai
    instance khác nhau trong Python.
    """
    raise NotImplementedError("Tuần 2: xem HybridRetriever.fuse")
