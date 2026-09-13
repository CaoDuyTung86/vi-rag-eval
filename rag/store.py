"""Nhánh ngữ nghĩa: kho vector trong bộ nhớ + cosine similarity.

TUẦN 2 — bạn viết phần này.

Tham chiếu: .../ai/rag/InMemoryVectorStore.java

Bản thô có chủ đích: quét tuyến tính toàn bộ corpus. Với 56 chunk thì đây là lựa chọn
ĐÚNG, không phải lựa chọn tạm — một chỉ mục ANN chỉ có ý nghĩa từ cỡ chục nghìn vector
trở lên. Tuần 7 mới thay bằng FAISS/Qdrant, và khi đó phải đo lại để chứng minh nó
thật sự đáng.
"""

from __future__ import annotations

import numpy as np

from rag.types import Chunk, Scored


class VectorStore:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._matrix: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self._chunks)

    def load(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        """Nạp corpus kèm ma trận vector shape (n_chunks, dim).

        Chuẩn hoá L2 từng hàng NGAY LÚC NẠP. Làm vậy thì cosine similarity trở thành
        một phép nhân ma trận đơn thuần, và bạn không phải chuẩn hoá lại ở mỗi truy vấn.
        """
        raise NotImplementedError("Tuần 2: xem InMemoryVectorStore.load")

    def search(self, query_vector: np.ndarray, top_k: int, min_similarity: float) -> list[Scored]:
        """top_k chunk có cosine >= min_similarity, sắp xếp giảm dần.

        min_similarity (bản Java để 0.55) là cái chặn "chunk gần nhất" khỏi bị trả về
        khi thực ra chẳng có chunk nào liên quan. Không có ngưỡng này thì mọi câu hỏi
        đều có kết quả, kể cả câu ngoài phạm vi.
        """
        raise NotImplementedError("Tuần 2: xem InMemoryVectorStore.search")
