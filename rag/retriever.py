"""Truy hồi lai: BM25 + vector, hợp nhất bằng RRF.

Tham chiếu: .../ai/rag/HybridRetriever.java

Lọc ngôn ngữ áp cho CẢ hai nhánh TRƯỚC khi hợp nhất, chứ không cắt bớt sau khi đã xếp hạng.
Lọc sau sẽ làm rỗng dần danh sách ứng viên: lấy 10 ứng viên mỗi nhánh rồi bỏ những cái khác
ngôn ngữ thì có khi chỉ còn 2-3 cái để hợp nhất, trong khi corpus vẫn còn thừa chunk đúng
ngôn ngữ xếp ngay bên dưới.

Suy giảm êm: embedding không dùng được (thiếu key, lời gọi hỏng) thì nhánh ngữ nghĩa trả
rỗng và kết quả rơi về đúng BM25 thuần. Đó là hành vi ĐÚNG khi chạy thật — nhưng khi ĐO thì
nó biến nhánh Vector thành BM25 trá hình, nên mỗi lần suy giảm đều được đếm lại.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import numpy as np

from rag.bm25 import BM25Index
from rag.embed import EmbeddingError
from rag.fusion import DEFAULT_RRF_K, rrf
from rag.store import VectorStore
from rag.types import Chunk, Scored


class Embedder(Protocol):
    @property
    def available(self) -> bool: ...

    def embed(self, text: str) -> np.ndarray: ...


class HybridRetriever:
    def __init__(
        self,
        bm25: BM25Index,
        store: VectorStore,
        embedder: Embedder | None,
        *,
        candidates_per_branch: int = 10,
        min_similarity: float = 0.55,
        rrf_k: int = DEFAULT_RRF_K,
        rrf_weights: tuple[float, float] = (1.0, 1.0),
        on_embedding_error: Callable[[str, EmbeddingError], None] | None = None,
    ) -> None:
        self.bm25 = bm25
        self.store = store
        self.embedder = embedder
        self.candidates_per_branch = candidates_per_branch
        self.min_similarity = min_similarity
        self.rrf_k = rrf_k
        # (BM25, Vector). Mặc định bằng nhau như bản Java; thí nghiệm P@1 ngày 14/09 thử nghiêng
        # về Vector.
        self.rrf_weights = rrf_weights
        self._on_embedding_error = on_embedding_error
        self.embedding_failures = 0

    def retrieve(self, query: str | None, top_k: int, lang: str | None = None) -> list[Chunk]:
        """Truy hồi lai. Mỗi nhánh lấy max(top_k, candidates_per_branch) ứng viên rồi hợp nhất."""
        if query is None or not query.strip() or top_k <= 0:
            return []
        candidates = max(top_k, self.candidates_per_branch)
        lexical = self.bm25.search(query, candidates, lang)
        semantic = self._semantic_search(query, candidates, lang)
        # Nhánh Vector duyệt TRƯỚC: hoà điểm RRF thì chunk xuất hiện trước thắng, và hoà xảy ra
        # thường hơn tưởng — hạng (1, 2) và (2, 1) cho đúng cùng một điểm. Đứng riêng, Vector
        # đúng hạng 1 nhiều hơn BM25 hẳn (95.5% so với 76.5% trên bộ vàng), nên hoà thì nghe
        # Vector. Bản Java (HybridRetriever.fuse) làm y như vậy; xem experiments.md 14/09.
        lexical_weight, semantic_weight = self.rrf_weights
        return rrf([semantic, lexical], top_k, self.rrf_k, [semantic_weight, lexical_weight])

    def retrieve_lexical_only(
        self, query: str | None, top_k: int, lang: str | None = None
    ) -> list[Chunk]:
        """Chỉ nhánh từ khoá — dùng cho bộ đo."""
        return [hit.chunk for hit in self.bm25.search(query, top_k, lang)]

    def retrieve_semantic_only(
        self, query: str | None, top_k: int, lang: str | None = None
    ) -> list[Chunk]:
        """Chỉ nhánh ngữ nghĩa — dùng cho bộ đo."""
        if query is None or not query.strip():
            return []
        return [hit.chunk for hit in self._semantic_search(query, top_k, lang)]

    def _semantic_search(self, query: str, candidates: int, lang: str | None) -> list[Scored]:
        if self.embedder is None or not self.embedder.available or len(self.store) == 0:
            return []
        try:
            query_vector = self.embedder.embed(query)
        except EmbeddingError as error:
            # Không để lỗi embedding làm hỏng cả lượt truy hồi — lùi về BM25, nhưng ghi sổ.
            self.embedding_failures += 1
            if self._on_embedding_error is not None:
                self._on_embedding_error(query, error)
            return []
        return self.store.search(query_vector, candidates, self.min_similarity, lang)
