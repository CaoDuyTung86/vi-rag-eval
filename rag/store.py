"""Nhánh ngữ nghĩa: kho vector trong bộ nhớ, quét cosine tuần tự, có lọc ngôn ngữ.

Tham chiếu: .../ai/rag/InMemoryVectorStore.java + VectorCodec.cosineSimilarity

Quét tuyến tính là lựa chọn ĐÚNG ở cỡ vài trăm chunk, không phải lựa chọn tạm — chỉ mục ANN
chỉ đáng từ cỡ chục nghìn vector trở lên. Thay bằng FAISS/Qdrant là một thí nghiệm phải đo,
không phải việc làm mặc định.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from rag.langfilter import accepts, normalize_lang, resolve_filter
from rag.types import Chunk, Scored


class VectorStore:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._matrix = np.empty((0, 0), dtype=np.float64)
        self._norms = np.empty(0, dtype=np.float64)
        self._languages: frozenset[str] = frozenset()

    def __len__(self) -> int:
        return len(self._chunks)

    @property
    def languages(self) -> frozenset[str]:
        """Ngôn ngữ thực sự có vector trong kho."""
        return self._languages

    def load(self, chunks: list[Chunk], vectors: ArrayLike) -> None:
        """Nạp corpus kèm ma trận vector shape (len(chunks), dim), cùng thứ tự với chunks.

        Vector giữ độ chính xác float32 như API trả về, nhưng cosine tính trên float64 — đúng
        như VectorCodec bên Java cộng dồn bằng double. Tính trên float32 thì điểm lệch từ chữ
        số thứ 7, đủ để đảo thứ hạng hai chunk sát điểm nhau.
        """
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != len(chunks):
            raise ValueError(f"Cần ma trận ({len(chunks)}, dim), nhận được shape {matrix.shape}")

        self._chunks = list(chunks)
        self._matrix = matrix.astype(np.float64)
        self._norms = np.sqrt(np.einsum("ij,ij->i", self._matrix, self._matrix))
        self._languages = frozenset(
            code for chunk in chunks if (code := normalize_lang(chunk.lang)) is not None
        )

    def search(
        self,
        query_vector: ArrayLike | None,
        top_k: int,
        min_similarity: float,
        lang: str | None = None,
    ) -> list[Scored]:
        """top_k chunk có cosine >= min_similarity, giảm dần.

        min_similarity (bản Java để 0.55) chặn "chunk gần nhất" khỏi bị trả về khi thật ra
        chẳng chunk nào liên quan. Không có ngưỡng thì câu hỏi nào cũng có kết quả, kể cả câu
        ngoài phạm vi.

        Mã ngôn ngữ mà kho không có vector nào thì bỏ lọc: model embedding đa ngôn ngữ, câu
        hỏi tiếng Nhật vẫn khớp được chunk tiếng Việt, lọc cho bằng được rồi trả rỗng là tự
        bắn vào chân.

        Bản Java trả cosine 0 khi lệch số chiều; ở đây ném ValueError, vì lệch số chiều luôn
        là lỗi cấu hình (đổi model mà quên xoá cache) chứ không phải dữ liệu hợp lệ.
        """
        if query_vector is None or not self._chunks or top_k <= 0:
            return []

        query = np.asarray(query_vector, dtype=np.float32).astype(np.float64)
        if query.shape != (self._matrix.shape[1],):
            raise ValueError(
                f"Vector truy vấn có shape {query.shape}, "
                f"kho đang giữ {self._matrix.shape[1]} chiều"
            )

        filter_lang = resolve_filter(lang, self._languages)
        query_norm = float(np.sqrt(query @ query))
        dots = self._matrix @ query
        with np.errstate(divide="ignore", invalid="ignore"):
            similarities = np.where(
                (self._norms == 0) | (query_norm == 0),
                0.0,
                dots / (self._norms * query_norm),
            )

        scored = [
            Scored(chunk, float(similarity))
            for chunk, similarity in zip(self._chunks, similarities, strict=True)
            if accepts(filter_lang, chunk) and similarity >= min_similarity
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]
