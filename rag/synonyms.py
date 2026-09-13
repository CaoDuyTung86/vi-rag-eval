"""Mở rộng truy vấn bằng từ đồng nghĩa, mỗi ngôn ngữ một bảng.

Tham chiếu: .../ai/rag/SynonymExpander.java — bảng từ nằm ở data/synonyms.yml thay vì
hard-code: nó đổi mỗi lần error analysis phát hiện một khoảng trống từ vựng, và đổi dữ liệu
thì không nên phải sửa code.

Bảng đồng nghĩa bắt được thứ embedding hay trượt: tiếng lóng ("bùng vé"), cách nói đời
thường ("mấy cân"), biến thể không dấu, và biến thể hình thái tiếng Anh mà BM25 — vốn so
khớp mặt chữ — không tự nối được (cancel/cancellation). Nó CHỈ thêm từ vào truy vấn; chấm
điểm vẫn là việc của BM25.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import yaml

from rag.langfilter import normalize_lang
from rag.normalize import contains_cjk, tokenize

DEFAULT_SYNONYMS_PATH = Path(__file__).resolve().parent.parent / "data" / "synonyms.yml"

SynonymTables = dict[str, dict[str, list[str]]]


@lru_cache(maxsize=4)
def load_synonyms(path: str | None = None) -> SynonymTables:
    """Nạp bảng đồng nghĩa: {mã ngôn ngữ: {khoá: [từ bổ sung]}}. Cache theo tiến trình."""
    p = Path(path) if path else DEFAULT_SYNONYMS_PATH
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    tables: SynonymTables = {}
    for lang, table in data.items():
        code = normalize_lang(str(lang))
        if code is None or not isinstance(table, dict):
            raise ValueError(f"{p}: mục cấp một phải là bảng theo mã ngôn ngữ, gặp {lang!r}")
        entries: dict[str, list[str]] = {}
        for key, values in table.items():
            # YAML 1.1 đọc no/yes/on/off để trần thành bool. Chặn ở đây, thay vì để một khoá
            # "no" âm thầm thành False và không bao giờ khớp được gì.
            valid = (
                isinstance(key, str)
                and isinstance(values, list)
                and all(isinstance(v, str) for v in values)
            )
            if not valid:
                raise ValueError(f"{p}: bảng {code} có khoá/giá trị không phải chuỗi: {key!r}")
            entries[key] = list(values)
        tables[code] = entries
    return tables


def tables_for(lang: str | None, tables: SynonymTables) -> list[dict[str, list[str]]]:
    """Bảng của đúng ngôn ngữ; ngôn ngữ None hoặc chưa có bảng riêng thì áp mọi bảng.

    Áp mọi bảng ăn khớp với truy hồi: ngôn ngữ lạ cũng không bị lọc chỉ mục, nên truy vấn
    được phép với sang mọi kho từ.
    """
    code = normalize_lang(lang)
    table = tables.get(code) if code is not None else None
    return [table] if table is not None else list(tables.values())


def expand(
    query: str | None,
    lang: str | None = None,
    tables: SynonymTables | None = None,
) -> list[str]:
    """Token của truy vấn KÈM token đồng nghĩa của đúng ngôn ngữ đang tra.

    Token gốc đứng trước và không lặp — lặp làm BM25 chấm điểm lệch. dict.fromkeys giữ
    thứ tự chèn và khử trùng trong một bước, đúng việc LinkedHashSet làm bên Java.
    """
    tables = load_synonyms() if tables is None else tables
    query_tokens = tokenize(query)
    tokens = dict.fromkeys(query_tokens)

    # Khoá Latin khớp theo RANH GIỚI TỪ, ghép lại từ chính token của truy vấn để hai vế so
    # khớp đi qua đúng một bộ chuẩn hoá. Khớp chuỗi con thì "chọn ghế" (chon) dính khoá
    # "cho" và bị nhét thêm cả đống từ về thú cưng.
    haystack = " " + " ".join(query_tokens) + " "

    # Khoá CJK thì ngược lại, PHẢI khớp chuỗi con: tiếng Nhật và tiếng Trung viết liền không
    # dấu cách nên không có ranh giới từ để dựa vào, và token của chúng là bigram.
    cjk_haystack = unicodedata.normalize("NFKC", query or "")

    for table in tables_for(lang, tables):
        for key, synonyms in table.items():
            matched = key in cjk_haystack if contains_cjk(key) else f" {key} " in haystack
            if matched:
                for synonym in synonyms:
                    tokens.update(dict.fromkeys(tokenize(synonym)))
    return list(tokens)
