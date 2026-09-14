"""Hợp nhất nhiều bảng xếp hạng bằng Reciprocal Rank Fusion.

Tham chiếu: .../ai/rag/HybridRetriever.java (fuse / accumulate)

Vì sao RRF chứ không phải cộng điểm có trọng số: hai nhánh cho điểm trên hai thang hoàn toàn
khác nhau (cosine 0..1 so với BM25 không chặn trên). RRF chỉ dùng THỨ HẠNG nên không cần
chuẩn hoá, cũng không cần tự tay chỉnh trọng số — thứ mà với corpus cỡ này thì có chỉnh cũng
chỉ là đoán mò.
"""

from __future__ import annotations

from collections.abc import Sequence

from rag.types import Chunk, Scored

# Hằng số k trong bài báo gốc của RRF (Cormack, Clarke, Buettcher 2009). Nó làm phẳng chênh
# lệch giữa các hạng đầu nên không phải tự gán trọng số cho từng nhánh.
DEFAULT_RRF_K = 60


def rrf(
    branches: list[list[Scored]],
    top_k: int,
    k: int = DEFAULT_RRF_K,
    weights: Sequence[float] | None = None,
) -> list[Chunk]:
    """Mỗi chunk cộng trọng_số/(k + hạng) từ mỗi nhánh có mặt nó, hạng tính từ 1.

    Chunk xuất hiện ở CẢ hai nhánh được đẩy lên trên một cách tự nhiên, không cần quy tắc
    riêng. Một nhánh rỗng (embedding hỏng, thiếu API key) thì kết quả rơi về đúng nhánh còn
    lại, giữ nguyên thứ tự của nó.

    weights mặc định là 1 cho mọi nhánh — đúng công thức gốc và bản Java. Trọng số 0 bỏ hẳn
    nhánh đó, kể cả những chunk chỉ nhánh đó tìm ra.

    Gộp theo doc_id chứ không theo object — cùng một chunk đến từ hai nhánh có thể là hai
    instance khác nhau. Điểm bằng nhau giữ thứ tự xuất hiện đầu tiên, như LinkedHashMap bên
    Java.
    """
    if top_k <= 0:
        return []
    if weights is None:
        weights = [1.0] * len(branches)
    if len(weights) != len(branches):
        raise ValueError(f"{len(weights)} trọng số cho {len(branches)} nhánh")

    fused: dict[str, float] = {}
    by_id: dict[str, Chunk] = {}
    for hits, weight in zip(branches, weights, strict=True):
        if weight == 0:
            continue
        for rank, hit in enumerate(hits, start=1):
            doc_id = hit.chunk.doc_id
            by_id.setdefault(doc_id, hit.chunk)
            fused[doc_id] = fused.get(doc_id, 0.0) + weight / (k + rank)

    ranked = sorted(fused, key=fused.__getitem__, reverse=True)
    return [by_id[doc_id] for doc_id in ranked[:top_k]]
