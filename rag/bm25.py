"""Nhánh tìm kiếm từ khoá, chấm điểm BM25 trên token đã bỏ dấu.

TUẦN 1 — bạn viết phần này. Tự cài đặt trước khi nghĩ tới pip install rank_bm25:
công thức này là bài học, không phải dependency.

Tham chiếu: .../ai/rag/LexicalIndex.java

Nhánh này KHÔNG phải phần thừa để hệ thống được gọi là "hybrid". Nó gánh hai việc:
  1. Đường lui khi không có embedding (thiếu API key, API hỏng) — hệ thống vẫn truy
     hồi được thay vì câm.
  2. Bắt được thứ embedding hay trượt: mã voucher, số hiệu, tiếng lóng, gõ không dấu.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag.types import Chunk, Scored

# Tham số BM25 tiêu chuẩn. Đừng tinh chỉnh: corpus 56 chunk không đủ lớn để việc tinh
# chỉnh có ý nghĩa thống kê — chỉnh chỉ là overfit lên 57 câu hỏi vàng.
K1 = 1.2
B = 0.75


@dataclass(slots=True)
class _Document:
    chunk: Chunk
    term_frequencies: dict[str, int]
    length: int


class BM25Index:
    """Chỉ mục nghịch đảo tối giản + chấm điểm BM25."""

    def __init__(self) -> None:
        self._documents: list[_Document] = []
        self._document_frequencies: dict[str, int] = {}
        self._average_length: float = 0.0

    def __len__(self) -> int:
        return len(self._documents)

    def load(self, chunks: list[Chunk]) -> None:
        """Đánh chỉ mục toàn bộ corpus.

        Với mỗi chunk: tokenize chunk.indexed_text, đếm tf, cộng df, ghi độ dài.
        Cuối cùng tính độ dài trung bình (dùng cho phần chuẩn hoá độ dài của BM25).
        """
        raise NotImplementedError("Tuần 1: xem LexicalIndex.load")

    def search(self, query: str, top_k: int) -> list[Scored]:
        """top_k chunk có điểm BM25 DƯƠNG, sắp xếp giảm dần.

        Truy vấn phải đi qua synonyms.expand() chứ không phải normalize.tokenize()
        trực tiếp — nếu không thì toàn bộ bảng đồng nghĩa vô tác dụng.

        Chunk điểm 0 phải bị LOẠI, không được trả về với điểm 0: chúng làm nhiễu thứ
        hạng khi hợp nhất RRF.
        """
        raise NotImplementedError("Tuần 1: xem LexicalIndex.search")

    def _score(self, doc: _Document, query_tokens: list[str]) -> float:
        """Điểm BM25 của một tài liệu với một truy vấn.

        IDF dùng công thức Robertson có cộng 1 bên trong log:

            idf = ln(1 + (N - df + 0.5) / (df + 0.5))

        Cộng 1 để idf không bao giờ ÂM với term xuất hiện ở mọi tài liệu. Bỏ chỗ +1 đó
        là bug kinh điển: một term phổ biến sẽ TRỪ điểm tài liệu chứa nó.
        """
        raise NotImplementedError("Tuần 1: xem LexicalIndex.score")
