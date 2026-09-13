"""Kiểu dữ liệu dùng chung. Không có logic — sửa ở đây là đổi hợp đồng giữa các module."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Chunk:
    """Một đơn vị tri thức được đánh chỉ mục và nhúng riêng.

    Khớp 1-1 với một mục trong data/kb/*.yml và với bảng `tri_thuc` của bản Java.
    """

    doc_id: str
    content: str
    title: str = ""
    category: str = ""
    lang: str = "vi"

    @property
    def indexed_text(self) -> str:
        """Văn bản đem đi đánh chỉ mục BM25: tiêu đề, dấu cách, nội dung.

        Gộp tiêu đề vào là có chủ đích — tiêu đề thường chứa đúng từ người dùng hỏi. Dấu
        cách ở giữa không chỉ để đẹp: nó cắt dãy chữ CJK của tiêu đề khỏi dãy của nội dung,
        nếu không sẽ sinh một bigram giả nối ký tự cuối tiêu đề với ký tự đầu nội dung. Bản
        Java làm y hệt trong LexicalIndex.load().
        """
        return f"{self.title} {self.content}"

    @property
    def embedding_text(self) -> str:
        """Văn bản đem đi nhúng: "Tiêu đề. Nội dung", bỏ phần tiêu đề nếu trống.

        KHÁC indexed_text, và phải khác đúng như vậy: đây là chuỗi bộ đo Java gửi sang API
        embedding. Đổi dù chỉ một dấu chấm là ra vector khác, cache đĩa trượt hết, và số đo
        nhánh ngữ nghĩa không còn so được với bản Java.
        """
        return f"{self.title}. {self.content}" if self.title.strip() else self.content


@dataclass(frozen=True, slots=True)
class Scored:
    """Một chunk kèm điểm của MỘT nhánh truy hồi.

    Điểm của hai nhánh KHÔNG so sánh trực tiếp được với nhau: cosine nằm trong 0..1, BM25
    không chặn trên. Đó chính là lý do hợp nhất bằng RRF (chỉ dùng thứ hạng).
    """

    chunk: Chunk
    score: float


@dataclass(slots=True)
class GoldenCase:
    """Một câu hỏi vàng: truy vấn của khách, tập doc_id được coi là đúng, và ngôn ngữ câu hỏi.

    `expected` có thể có nhiều phần tử — nhiều câu hỏi có hơn một câu trả lời hợp lệ, và phạt
    hệ thống vì chọn chunk đúng "khác" là sai. `lang` là ngôn ngữ của CÂU HỎI, dùng để chấm
    riêng từng ngôn ngữ và để lọc chỉ mục ở cấu hình "+ lọc lang".
    """

    query: str
    expected: list[str] = field(default_factory=list)
    lang: str = "vi"
