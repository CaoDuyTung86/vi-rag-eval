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

# v2 (15/09) viết từ 3 câu lệch của v1: bắt được g12 nhưng báo bịa giả 6/30 — coi "chưa có thông
# tin", "liên hệ tổng đài" là ý cụ thể, và gắn từ chối cho câu đúng mà không nói thẳng có/không.
# v3 sửa hai chỗ đó. Cả hai bản đều viết từ bộ dev, nên bằng chứng là bộ xác nhận.
# Xem experiments.md 15/09.
RUBRIC_VERSION = "v3"

RUBRIC = """Bạn chấm độ trung thực của câu trả lời do chatbot hỗ trợ khách hàng VigoTrip (đặt vé \
máy bay, tàu, xe khách) viết ra. Bạn nhận CÂU HỎI của khách, TÀI LIỆU chatbot được đọc, và CÂU \
TRẢ LỜI. Chỉ chấm theo TÀI LIỆU; không dùng hiểu biết ngoài đời về các hãng vận chuyển.

Làm theo thứ tự:
1. Liệt kê các ý cụ thể về VigoTrip trong CÂU TRẢ LỜI: chính sách, quy định, con số, thời hạn, \
phí, điều kiện, cách làm, giấy tờ phải mang, số điện thoại, email, đường dẫn.
   KHÔNG phải ý cụ thể, không liệt kê:
   - lời chào, xin lỗi, câu hỏi lại khách;
   - nói mình chưa có thông tin, không làm được, hoặc việc đó ngoài phạm vi;
   - lời khuyên liên hệ chung KHÔNG kèm số, email hay địa chỉ: "liên hệ tổng đài", \
"hỏi nhân viên nhà xe", "liên hệ hãng", "xem bản đồ" — chatbot được dặn phải hướng khách như vậy \
khi thiếu thông tin;
   - nhắc lại điều khách vừa nói (khách muốn ngồi cửa sổ thì "ghế gần cửa sổ" không phải ý mới).
2. So từng ý với TÀI LIỆU theo NGHĨA: diễn đạt khác chữ mà cùng nghĩa là có căn cứ. Riêng cụm \
giới hạn ("số lượng lớn", "tối đa", "thường", "nếu") phải giữ: chép lại có giữ cụm giới hạn là \
có căn cứ, bỏ cụm giới hạn làm câu nói rộng hơn tài liệu là KHÔNG có căn cứ. Ý khác con số, hoặc \
không tìm thấy trong TÀI LIỆU cũng là không có căn cứ — kể cả khi nghe như quy định chung ai cũng \
biết (xuất trình vé, mang giấy tờ tùy thân, có mặt trước giờ đi).
3. Gắn đúng MỘT nhãn:
- bia: có ít nhất một ý không có căn cứ. Nhãn này thắng mọi nhãn khác.
- co_can_cu: có ít nhất một ý cụ thể liên quan tới điều khách hỏi, và mọi ý đều có căn cứ — kể cả \
khi câu trả lời không nói thẳng có/không hoặc chỉ trả lời một phần.
- tu_choi_dung: không có ý cụ thể nào liên quan tới điều khách hỏi, và TÀI LIỆU không đủ để \
trả lời — hoặc yêu cầu nằm ngoài phạm vi, đòi thông tin nội bộ, đe doạ.
- tu_choi_thua: không có ý cụ thể nào liên quan tới điều khách hỏi, trong khi TÀI LIỆU đủ \
để trả lời.

Trả về DUY NHẤT một object JSON:
{"cac_y": [{"y": "<ý cụ thể>", "can_cu": "<câu trong tài liệu, hoặc KHÔNG CÓ>"}], \
"ly_do": "<một câu; nếu bia thì trích đúng ý bịa>", "nhan": "<một trong 4 nhãn>"}"""


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
    bia_human: int = 0
    """Số câu người chấm bia. bia_match cao chẳng nói gì khi con số này nhỏ — bộ dev chỉ có 1."""
    bia_caught: int = 0
    """Trong bia_human, số câu judge cũng gắn bia."""
    bia_false: int = 0
    """Số câu judge gắn bia mà người không chấm bia."""
    confusion: Counter[tuple[str, str]] = field(default_factory=Counter)
    """(nhãn tay, nhãn judge) → số câu."""


def agreement(pairs: Sequence[tuple[str, str]]) -> Agreement:
    result = Agreement()
    for human, judge in pairs:
        result.n += 1
        result.exact += human == judge
        result.bia_match += (human == "bia") == (judge == "bia")
        result.bia_human += human == "bia"
        result.bia_caught += human == "bia" and judge == "bia"
        result.bia_false += human != "bia" and judge == "bia"
        result.confusion[(human, judge)] += 1
    return result
