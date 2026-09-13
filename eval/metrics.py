"""Chỉ số đánh giá truy hồi.

TUẦN 3 — bạn viết phần này. Đây là tuần quan trọng nhất của ba tuần đầu: không có
baseline đóng băng thì mọi thí nghiệm từ tuần 6 trở đi đều vô nghĩa.

Tham chiếu: .../test/java/com/booking/api/ai/rag/RagRetrievalQualityTest.java

Lưu ý về ngữ nghĩa, khác với sách giáo khoa: phần lớn câu hỏi trong golden.yml chỉ có
MỘT chunk đúng. Nghĩa là precision@3 bị chặn trên bởi 1/3 ngay cả khi hệ thống hoàn
hảo. Nó vẫn được tính để đủ bộ, nhưng đừng đọc nó như một tỉ lệ phần trăm chất lượng —
recall@k và MRR mới là hai con số bạn thật sự nhìn.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Metrics:
    """Kết quả chấm điểm của MỘT nhánh truy hồi trên toàn bộ câu hỏi vàng."""

    name: str
    n: int
    precision_at_1: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_3: float
    f1_at_3: float
    mrr: float
    ndcg_at_5: float = 0.0


def recall_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    """1.0 nếu có ÍT NHẤT một docId đúng nằm trong top-k, ngược lại 0.0.

    Đây là recall theo kiểu "hit rate", không phải |đúng ∩ topk| / |đúng|. Chọn như vậy
    vì với chatbot, bốc được một chunk trả lời đúng là đủ để trả lời đúng — bốc đủ cả
    ba chunk hợp lệ không tốt hơn.
    """
    raise NotImplementedError("Tuần 3")


def precision_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    """|đúng ∩ top-k| / k. Xem lưu ý về trần 1/3 ở docstring đầu file."""
    raise NotImplementedError("Tuần 3")


def reciprocal_rank(retrieved: list[str], expected: list[str]) -> float:
    """1 / (thứ hạng của kết quả đúng ĐẦU TIÊN), hạng tính từ 1. Không có thì 0.0.

    MRR là chỉ số nhạy nhất với việc "đúng nhưng xếp sau". recall@3 không phân biệt
    được hạng 1 với hạng 3; MRR thì có (1.0 so với 0.33).
    """
    raise NotImplementedError("Tuần 3")


def ndcg_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain.

    TUẦN 8, không phải tuần 3 — để trống cho tới lúc đó cũng được.

    Khác MRR ở chỗ nó tính CẢ các kết quả đúng phía sau, có chiết khấu theo log vị trí.
    Chỉ đáng thêm khi bạn đã có nhiều câu hỏi có hơn một đáp án đúng.
    """
    raise NotImplementedError("Tuần 8")


def f1(precision: float, recall: float) -> float:
    """Trung bình điều hoà. Trả 0.0 khi cả hai bằng 0 (tránh chia cho 0)."""
    raise NotImplementedError("Tuần 3")


def evaluate(name: str, results: list[tuple[list[str], list[str]]]) -> Metrics:
    """Gộp kết quả từng câu thành một bản Metrics.

    results là danh sách (retrieved_doc_ids, expected_doc_ids) theo đúng thứ tự câu hỏi.
    Mọi chỉ số đều là trung bình cộng trên số câu hỏi.
    """
    raise NotImplementedError("Tuần 3")
