"""Chuẩn hoá văn bản tiếng Việt cho nhánh tìm kiếm từ khoá.

TUẦN 1 — bạn viết phần này.

Tham chiếu bản Java:
  WebProject/backend/ticket-booking/src/main/java/com/booking/api/ai/rag/TextNormalizer.java

Điều bắt buộc phải giữ: index và truy vấn phải chuẩn hoá GIỐNG HỆT nhau. Lệch một
chút là không bao giờ khớp, và lỗi đó không có triệu chứng nào ngoài điểm số thấp.
"""

from __future__ import annotations

import re
import unicodedata  # noqa: F401  (dùng khi bạn cài đặt remove_accents)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_DIGIT_THEN_LETTER = re.compile(r"(\d)([a-z])")
_LETTER_THEN_DIGIT = re.compile(r"([a-z])(\d)")


def remove_accents(text: str | None) -> str:
    """Bỏ dấu tiếng Việt, quy đổi đ/Đ về d/D. Giữ nguyên hoa/thường.

    Người Việt gõ không dấu rất phổ biến ("thu cung", "huy ve") nên đây là bắt buộc,
    không phải tối ưu thêm.

    Gợi ý: unicodedata.normalize("NFD", ...) tách dấu thành ký tự tổ hợp riêng, lọc bỏ
    ký tự có category "Mn". Riêng đ/Đ KHÔNG tách được bằng NFD — phải thay tay.
    """
    raise NotImplementedError("Tuần 1: xem TextNormalizer.removeAccents")


def normalize(text: str | None) -> str:
    """Chuẩn hoá đầy đủ: thường hoá rồi bỏ dấu. Dùng để so khớp chuỗi con."""
    raise NotImplementedError("Tuần 1: xem TextNormalizer.normalize")


def tokenize(text: str | None) -> list[str]:
    """Tách token đã chuẩn hoá cho BM25.

    Hai luật không hiển nhiên, cả hai đều do bộ đo golden.yml phát hiện:

    1. Tách ranh giới chữ-số: "20kg" -> ["20", "kg"]. Không tách thì tài liệu ghi
       "20kg" sẽ không bao giờ khớp câu hỏi "mang được bao nhiêu kg".
    2. Bỏ token 1 ký tự. Tiếng Việt có từ đơn một âm tiết, nhưng sau khi bỏ dấu thì
       token 1 ký tự hầu như chỉ là nhiễu.
    """
    raise NotImplementedError("Tuần 1: xem TextNormalizer.tokenize")
