"""Chỉ số đánh giá truy hồi, chấm y hệt RagRetrievalQualityTest bên Java.

Mỗi câu lấy top-5; recall@k là tỉ lệ câu có ÍT NHẤT một chunk đúng trong top-k (hit rate),
không phải |đúng ∩ top-k| / |đúng|. Chọn vậy vì với chatbot, bốc được một chunk trả lời đúng
là đủ để trả lời đúng.

Lưu ý khi đọc P@3: phần lớn câu hỏi chỉ có MỘT chunk đúng, nên P@3 bị chặn trên ở 0.333
ngay cả khi hệ thống hoàn hảo. Thấp KHÔNG có nghĩa là tệ — recall@k và MRR mới là hai con số
đáng nhìn.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from rag.types import GoldenCase

EVAL_K = 5

# Khoá của dòng chấm gộp mọi ngôn ngữ, cùng nhãn với bảng bên Java.
ALL_LANGS = "gộp"

Retrieve = Callable[[GoldenCase, int], Sequence[str]]


@dataclass(frozen=True, slots=True)
class Metrics:
    """Kết quả chấm của MỘT cấu hình truy hồi trên một tập câu hỏi."""

    name: str
    n: int
    precision_at_1: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_3: float
    f1_at_3: float
    mrr: float
    ndcg_at_5: float
    misses: tuple[str, ...] = ()


def recall_at_k(retrieved: Sequence[str], expected: Sequence[str], k: int) -> float:
    """1.0 nếu có ít nhất một docId đúng trong top-k, ngược lại 0.0."""
    wanted = set(expected)
    return 1.0 if any(doc_id in wanted for doc_id in retrieved[:k]) else 0.0


def precision_at_k(retrieved: Sequence[str], expected: Sequence[str], k: int) -> float:
    """|đúng ∩ top-k| / k — chia cho k kể cả khi trả về ít hơn k kết quả, như bản Java."""
    if k <= 0:
        return 0.0
    wanted = set(expected)
    return sum(1 for doc_id in retrieved[:k] if doc_id in wanted) / k


def reciprocal_rank(retrieved: Sequence[str], expected: Sequence[str]) -> float:
    """1 / hạng của kết quả đúng ĐẦU TIÊN (tính từ 1); không có thì 0.0.

    MRR phân biệt được "đúng ở hạng 1" với "đúng ở hạng 3" (1.0 so với 0.33), thứ recall@3
    không thấy.
    """
    wanted = set(expected)
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in wanted:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], expected: Sequence[str], k: int) -> float:
    """nDCG với độ liên quan nhị phân. Không có trong bảng Java — chỉ xuất ra ở JSON.

    Khác MRR ở chỗ tính CẢ các kết quả đúng phía sau, có chiết khấu theo log vị trí. Chỉ nói
    thêm được điều gì khi bộ vàng có nhiều câu mang hơn một đáp án đúng.
    """
    wanted = set(expected)
    if not wanted or k <= 0:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, doc_id in enumerate(retrieved[:k], start=1)
        if doc_id in wanted
    )
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(wanted), k) + 1))
    return dcg / ideal


def f1(precision: float, recall: float) -> float:
    """Trung bình điều hoà; 0.0 khi cả hai bằng 0."""
    total = precision + recall
    return 0.0 if total == 0 else 2 * precision * recall / total


def _java_list(items: Sequence[str]) -> str:
    return "[" + ", ".join(items) + "]"


def evaluate(name: str, cases: Sequence[GoldenCase], retrieve: Retrieve) -> Metrics:
    """Chấm một cấu hình trên một tập câu hỏi. retrieve nhận (câu hỏi, k) và trả docId đã xếp.

    Nhận cả GoldenCase chứ không chỉ chuỗi câu hỏi, vì cấu hình có lọc ngôn ngữ cần biết câu
    hỏi thuộc ngôn ngữ nào.
    """
    if not cases:
        raise ValueError(f"{name}: không có câu hỏi nào để chấm")

    hits_at_1 = hits_at_3 = hits_at_5 = 0
    rr_sum = precision_at_3_sum = ndcg_sum = 0.0
    misses: list[str] = []

    for case in cases:
        top5 = list(retrieve(case, EVAL_K))[:EVAL_K]

        hits_at_1 += bool(top5) and top5[0] in case.expected
        hits_at_3 += int(recall_at_k(top5, case.expected, 3))
        hits_at_5 += int(recall_at_k(top5, case.expected, 5))
        precision_at_3_sum += precision_at_k(top5, case.expected, 3)
        ndcg_sum += ndcg_at_k(top5, case.expected, EVAL_K)

        rr = reciprocal_rank(top5, case.expected)
        if rr > 0:
            rr_sum += rr
        else:
            misses.append(
                f'  "{case.query}" -> mong đợi {_java_list(sorted(case.expected))}, '
                f"nhận được {_java_list(top5)}"
            )

    n = len(cases)
    recall_at_3 = hits_at_3 / n
    precision_at_3 = precision_at_3_sum / n
    return Metrics(
        name=name,
        n=n,
        precision_at_1=hits_at_1 / n,
        recall_at_1=hits_at_1 / n,
        recall_at_3=recall_at_3,
        recall_at_5=hits_at_5 / n,
        precision_at_3=precision_at_3,
        f1_at_3=f1(precision_at_3, recall_at_3),
        mrr=rr_sum / n,
        ndcg_at_5=ndcg_sum / n,
        misses=tuple(misses),
    )


def evaluate_by_lang(
    base_name: str, cases: Sequence[GoldenCase], retrieve: Retrieve
) -> dict[str, Metrics]:
    """Chấm riêng từng ngôn ngữ CÂU HỎI, rồi thêm một dòng gộp khi có từ hai ngôn ngữ trở lên.

    Chấm riêng vì một con số trung bình sẽ để ngôn ngữ nhiều câu hỏi che cho ngôn ngữ ít câu
    hỏi tụt hẳn mà bảng vẫn xanh.
    """
    langs = sorted({case.lang for case in cases})
    by_lang = {
        lang: evaluate(
            f"{base_name} · {lang}", [case for case in cases if case.lang == lang], retrieve
        )
        for lang in langs
    }
    if len(langs) > 1:
        by_lang[ALL_LANGS] = evaluate(f"{base_name} · {ALL_LANGS}", cases, retrieve)
    return by_lang
