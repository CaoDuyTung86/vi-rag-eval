"""Quy tắc lọc chunk theo ngôn ngữ, dùng chung cho nhánh từ khoá và nhánh ngữ nghĩa.

Tham chiếu: .../ai/rag/LangFilter.java

Gom vào một chỗ vì hai chỉ mục PHẢI hiểu mã ngôn ngữ giống hệt nhau. Nếu một bên coi
"EN " khác "en" thì cùng một truy vấn sẽ lọc ở nhánh này mà không lọc ở nhánh kia, và kết
quả hợp nhất bằng RRF lệch theo cách rất khó lần ra.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet

from rag.types import Chunk


def normalize_lang(lang: str | None) -> str | None:
    """Chuẩn hoá mã ngôn ngữ. Rỗng, None hay toàn khoảng trắng đều thành None = "không lọc"."""
    if lang is None:
        return None
    value = lang.strip().lower()
    return value or None


def resolve_filter(lang: str | None, available: AbstractSet[str]) -> str | None:
    """Mã ngôn ngữ thực sự đem đi lọc.

    Mã mà chỉ mục KHÔNG có chunk nào thì bị bỏ, tức là tìm trên toàn corpus. Trả về rỗng
    trong trường hợp đó tệ hơn hẳn: người hỏi vẫn nhận được câu trả lời đúng từ chunk ngôn
    ngữ khác, chỉ là LLM phải dịch lại.
    """
    value = normalize_lang(lang)
    return value if value is not None and value in available else None


def accepts(normalized_filter: str | None, chunk: Chunk) -> bool:
    """True khi chunk thuộc ngôn ngữ đang lọc, hoặc khi không lọc gì cả."""
    return normalized_filter is None or normalized_filter == normalize_lang(chunk.lang)
