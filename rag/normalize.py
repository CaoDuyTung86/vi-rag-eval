"""Chuẩn hoá và tách token cho nhánh tìm kiếm từ khoá.

Tham chiếu: .../ai/rag/TextNormalizer.java

Điều bắt buộc phải giữ: index và truy vấn phải chuẩn hoá GIỐNG HỆT nhau. Lệch một chút là
không bao giờ khớp, và lỗi đó không có triệu chứng nào ngoài điểm số thấp.

Hai đường tách token chạy song song trên cùng một văn bản:
  - Latin (tiếng Việt, tiếng Anh): thường hoá, bỏ dấu, cắt theo [^a-z0-9]+.
  - CJK (tiếng Nhật, tiếng Trung): bigram ký tự, xem _cjk_bigrams.
"""

from __future__ import annotations

import re
import unicodedata

import regex

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_DIGIT_THEN_LETTER = re.compile(r"(\d)([a-z])")
_LETTER_THEN_DIGIT = re.compile(r"([a-z])(\d)")

# đ/Đ là chữ cái riêng trong bảng mã, không phải d cộng dấu, nên NFD không đụng tới nó.
_D_STROKE = str.maketrans({"đ": "d", "Đ": "D"})

# Thư viện chuẩn của Python không có thuộc tính Unicode Script; module regex thì có. Đó cũng
# là lý do bản Java dùng Character.UnicodeScript thay vì tự liệt khoảng mã: khoảng mã CJK nằm
# rải rác ở nhiều chỗ và còn được bổ sung qua từng phiên bản Unicode.
_CJK_SCRIPT = regex.compile(r"[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]")

# Dấu trường âm ー, dấu lặp 々 và 〆 thuộc (hoặc từng thuộc) script COMMON nhưng luôn đi liền
# trong từ. Cắt chúng ra khỏi dãy sẽ băm nhỏ từ một cách vô lý.
_CJK_EXTRA = frozenset("ー々〆")


def remove_accents(text: str | None) -> str:
    """Bỏ dấu tiếng Việt, quy đổi đ/Đ về d/D. Giữ nguyên hoa/thường.

    Người Việt gõ không dấu rất phổ biến ("thu cung", "huy ve") nên đây là bắt buộc,
    không phải tối ưu thêm.

    NFD tách "ặ" thành "a" cộng hai ký tự tổ hợp, cả hai đều mang category "Mn" nên
    lọc theo category là bỏ được mọi dấu tiếng Việt, kể cả dấu móc của ơ và ư.
    Riêng đ/Đ KHÔNG tách được bằng NFD — phải thay tay.
    """
    if text is None:
        return ""
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return without_marks.translate(_D_STROKE)


def normalize(text: str | None) -> str:
    """Chuẩn hoá đầy đủ: thường hoá rồi bỏ dấu. Dùng để so khớp chuỗi con."""
    return remove_accents("" if text is None else text.lower())


def tokenize(text: str | None) -> list[str]:
    """Tách token cho BM25: token Latin đã chuẩn hoá trước, bigram CJK sau.

    Hai luật không hiển nhiên của nhánh Latin, cả hai đều do bộ đo phát hiện:

    1. Tách ranh giới chữ-số: "20kg" -> ["20", "kg"]. Không tách thì tài liệu ghi "20kg"
       sẽ không bao giờ khớp câu hỏi "mang được bao nhiêu kg".
    2. Bỏ token 1 ký tự. Tiếng Việt có từ đơn một âm tiết, nhưng sau khi bỏ dấu thì token 1
       ký tự hầu như chỉ là nhiễu. Luật này KHÔNG áp cho chữ Hán: một chữ đứng riêng vẫn là
       một từ đủ nghĩa.
    """
    if text is None or not text.strip():
        return []

    normalized = normalize(text)
    normalized = _DIGIT_THEN_LETTER.sub(r"\1 \2", normalized)
    normalized = _LETTER_THEN_DIGIT.sub(r"\1 \2", normalized)

    tokens = [token for token in _NON_ALNUM.split(normalized) if len(token) > 1]
    tokens.extend(_cjk_bigrams(text))
    return tokens


def is_cjk(ch: str) -> bool:
    """Ký tự có thuộc phần chữ Hán, Hiragana hoặc Katakana không."""
    return ch in _CJK_EXTRA or _CJK_SCRIPT.match(ch) is not None


def contains_cjk(text: str | None) -> bool:
    """True khi chuỗi có ít nhất một ký tự CJK. Dùng để chọn cách so khớp từ đồng nghĩa."""
    return text is not None and any(is_cjk(ch) for ch in text)


def _cjk_bigrams(text: str) -> list[str]:
    """Cắt chữ Nhật và chữ Trung thành cặp ký tự liền nhau (bigram).

    VÌ SAO CẦN ĐƯỜNG RIÊNG: nhánh Latin cắt theo [^a-z0-9]+, nên một câu tiếng Nhật đi qua đó
    ra ĐÚNG KHÔNG TOKEN NÀO — chunk tiếng Nhật vô hình với BM25.

    VÌ SAO LÀ BIGRAM CHỨ KHÔNG PHẢI TỪ: tiếng Nhật và tiếng Trung không có dấu cách giữa các
    từ. Tách từ cho đúng cần từ điển hình thái (MeCab, Jieba) — thêm vài chục MB phụ thuộc
    cho một corpus vài trăm chunk. Bigram là cách làm chuẩn mực cho đúng tình huống này:
    "手荷物" cho ra "手荷" và "荷物", câu hỏi chứa "荷物" vẫn khớp mà không cần biết ranh giới
    từ nằm đâu. Cặp cắt ngang ranh giới từ thật là nhiễu, nhưng chúng rải rác khắp corpus nên
    tự mất trọng số qua IDF.

    Dùng NFKC để katakana nửa độ rộng và chữ Latin toàn độ rộng quy về dạng chuẩn. KHÔNG dùng
    normalize() ở đây: nó bỏ dấu phụ, mà với tiếng Nhật dấu đục là dấu phụ — "が" sẽ thành
    "か", tức là đổi hẳn âm.
    """
    bigrams: list[str] = []
    run: list[str] = []
    for ch in unicodedata.normalize("NFKC", text):
        if is_cjk(ch):
            run.append(ch)
        else:
            _flush_run(run, bigrams)
    _flush_run(run, bigrams)
    return bigrams


def _flush_run(run: list[str], bigrams: list[str]) -> None:
    """Một dãy CJK liền nhau thành các cặp; dãy chỉ một ký tự thì giữ nguyên ký tự đó."""
    if not run:
        return
    if len(run) == 1:
        bigrams.append(run[0])
    else:
        bigrams.extend(run[i] + run[i + 1] for i in range(len(run) - 1))
    run.clear()
