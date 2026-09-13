"""Mở rộng truy vấn bằng từ đồng nghĩa tiếng Việt.

TUẦN 1 — bạn viết hàm expand().

Tham chiếu: .../ai/rag/SynonymExpander.java

Bảng đồng nghĩa bắt được thứ embedding hay trượt: tiếng lóng ("bùng vé"), cách nói
đời thường ("mấy cân"), và biến thể không dấu. Nó CHỈ thêm từ vào truy vấn — không
quyết định trả về nội dung gì. Chấm điểm vẫn là việc của BM25 trên toàn corpus.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from rag.normalize import normalize, tokenize  # noqa: F401  (dùng khi cài đặt expand)

DEFAULT_SYNONYMS_PATH = Path(__file__).resolve().parent.parent / "data" / "synonyms.yml"


@lru_cache(maxsize=1)
def load_synonyms(path: str | None = None) -> dict[str, list[str]]:
    """Nạp bảng đồng nghĩa từ YAML. Kết quả được cache theo tiến trình."""
    p = Path(path) if path else DEFAULT_SYNONYMS_PATH
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {str(k): list(v) for k, v in data.items()}


def expand(query: str, synonyms: dict[str, list[str]] | None = None) -> list[str]:
    """Trả về token của truy vấn KÈM token đồng nghĩa.

    Hai điều dễ làm sai:

    - Thứ tự và trùng lặp: token gốc phải đứng trước, và không được lặp. Token lặp làm
      BM25 chấm điểm lệch. Bản Java dùng LinkedHashSet cho đúng việc này — Python thì
      dict.fromkeys() giữ thứ tự và khử trùng trong một bước.
    - So khớp khoá bằng CHUỖI CON trên truy vấn đã chuẩn hoá, không phải theo token.
      "mấy cân" là hai token nhưng là một khoá.
    """
    raise NotImplementedError("Tuần 1: xem SynonymExpander.expand")
