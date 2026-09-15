"""LLM-judge độ trung thực: rubric, đọc nhãn, và mức đồng ý với chấm tay.

Judge chỉ có giá trị khi đã biết nó đồng ý với người tới đâu và sai kiểu gì. Vì vậy module này
tách phần thuần (rubric, đọc nhãn, đếm đồng ý) khỏi phần gọi API để test được không cần mạng.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

LABELS = ("co_can_cu", "bia", "tu_choi_dung", "tu_choi_thua")

RUBRIC = """Bạn chấm độ trung thực của câu trả lời do chatbot hỗ trợ khách hàng VigoTrip (đặt vé \
máy bay, tàu, xe khách) viết ra. Bạn nhận CÂU HỎI của khách, TÀI LIỆU chatbot được đọc, và CÂU \
TRẢ LỜI. Chỉ chấm theo TÀI LIỆU; không dùng hiểu biết ngoài đời về các hãng vận chuyển.

Chọn đúng MỘT nhãn:
- co_can_cu: câu trả lời đưa ra thông tin, và MỌI thông tin cụ thể về VigoTrip (chính sách, con \
số, thời hạn, phí, điều kiện, cách làm, số điện thoại, đường dẫn) đều có trong TÀI LIỆU hoặc suy \
ra trực tiếp từ đó. Trả lời một phần rồi nói rõ phần còn lại chưa có thông tin vẫn là co_can_cu.
- bia: có ÍT NHẤT MỘT thông tin cụ thể về VigoTrip không có trong TÀI LIỆU hoặc trái với TÀI \
LIỆU — kể cả khi phần còn lại đúng, kể cả khi nghe hợp lý ngoài đời.
- tu_choi_dung: câu trả lời không đưa thông tin cụ thể (nói chưa có thông tin, từ chối, hỏi lại, \
mời liên hệ hỗ trợ), và TÀI LIỆU thật sự không trả lời được câu hỏi — hoặc yêu cầu nằm ngoài phạm \
vi, đòi thông tin nội bộ, đe doạ.
- tu_choi_thua: câu trả lời không đưa thông tin cụ thể, trong khi TÀI LIỆU có đủ để trả lời.

Lời chào, câu xin lỗi, lời mời liên hệ hỗ trợ chung chung không tính là thông tin cụ thể. Có một ý \
bịa thì nhãn là bia, dù câu trả lời có cả phần từ chối.

Trả về DUY NHẤT một object JSON, lý do trước rồi mới tới nhãn:
{"ly_do": "<một câu; nếu bia thì trích đúng ý bịa>", "nhan": "<một trong 4 nhãn>"}"""


def judge_prompt(question: str, context: str, answer: str) -> str:
    return (
        f"CÂU HỎI CỦA KHÁCH:\n{question}\n\n"
        f"TÀI LIỆU CHATBOT ĐƯỢC ĐỌC:\n{context.strip() or '- (không có tài liệu nào)'}\n\n"
        f"CÂU TRẢ LỜI CỦA CHATBOT:\n{answer}"
    )


def parse_label(text: str) -> tuple[str, str]:
    """Lấy (nhãn, lý do) từ phản hồi của judge. Chịu được code fence và chữ thừa quanh JSON."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"Judge không trả JSON: {text[:200]!r}")
    data = json.loads(text[start : end + 1])
    label = str(data.get("nhan", "")).strip()
    if label not in LABELS:
        raise ValueError(f"Nhãn lạ: {label!r}")
    return label, str(data.get("ly_do", "")).strip()


@dataclass(slots=True)
class Agreement:
    n: int = 0
    exact: int = 0
    bia_match: int = 0
    """Số câu người và judge cùng ý về câu hỏi quan trọng nhất: có bịa hay không."""
    confusion: Counter[tuple[str, str]] = field(default_factory=Counter)
    """(nhãn tay, nhãn judge) → số câu."""


def agreement(pairs: Sequence[tuple[str, str]]) -> Agreement:
    result = Agreement()
    for human, judge in pairs:
        result.n += 1
        result.exact += human == judge
        result.bia_match += (human == "bia") == (judge == "bia")
        result.confusion[(human, judge)] += 1
    return result
