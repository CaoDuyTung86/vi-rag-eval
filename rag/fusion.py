"""Hợp nhất nhiều bảng xếp hạng bằng Reciprocal Rank Fusion.

Tham chiếu: .../ai/rag/HybridRetriever.java (fuse / accumulate)

Vì sao RRF chứ không phải cộng điểm có trọng số: hai nhánh cho điểm trên hai thang hoàn toàn
khác nhau (cosine 0..1 so với BM25 không chặn trên). RRF chỉ dùng THỨ HẠNG nên không cần
chuẩn hoá, cũng không cần tự tay chỉnh trọng số — thứ mà với corpus cỡ này thì có chỉnh cũng
chỉ là đoán mò.
"""

from __future__ import annotations

from rag.types import Chunk, Scored

# Hằng số k trong bài báo gốc của RRF (Cormack, Clarke, Buettcher 2009). Nó làm phẳng chênh
# lệch giữa các hạng đầu nên không phải tự gán trọng số cho từng nhánh.
DEFAULT_RRF_K = 60


def rrf(branches: list[list[Scored]], top_k: int, k: int = DEFAULT_RRF_K) -> list[Chunk]:
    """Mỗi chunk cộng 1/(k + hạng) từ mỗi nhánh có mặt nó, hạng tính từ 1.

    Chunk xuất hiện ở CẢ hai nhánh được đẩy lên trên một cách tự nhiên, không cần quy tắc
    riêng. Một nhánh rỗng (embedding hỏng, thiếu API key) thì kết quả rơi về đúng nhánh còn
    lại, giữ nguyên thứ tự của nó.

    Gộp theo doc_id chứ không theo object — cùng một chunk đến từ hai nhánh có thể là hai
    instance khác nhau. Điểm bằng nhau giữ thứ tự xuất hiện đầu tiên, như LinkedHashMap bên
    Java.
    """
    if top_k <= 0:
        return []

    fused: dict[str, float] = {}
    by_id: dict[str, Chunk] = {}
    for hits in branches:
        for rank, hit in enumerate(hits, start=1):
            doc_id = hit.chunk.doc_id
            by_id.setdefault(doc_id, hit.chunk)
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)

    ranked = sorted(fused, key=fused.__getitem__, reverse=True)
    return [by_id[doc_id] for doc_id in ranked[:top_k]]
