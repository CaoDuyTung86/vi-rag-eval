"""Nhánh tìm kiếm từ khoá: BM25 trên token đã chuẩn hoá, có lọc và thống kê theo ngôn ngữ.

Tham chiếu: .../ai/rag/LexicalIndex.java

Nhánh này KHÔNG phải phần thừa để hệ thống được gọi là "hybrid". Nó gánh hai việc:
  1. Đường lui khi không có embedding (thiếu API key, API hỏng) — vẫn truy hồi được.
  2. Bắt được thứ embedding hay trượt: mã voucher, số hiệu, tiếng lóng, gõ không dấu.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from rag.langfilter import accepts, normalize_lang, resolve_filter
from rag.normalize import tokenize
from rag.synonyms import SynonymTables, expand
from rag.types import Chunk, Scored

# Tham số BM25 tiêu chuẩn. Đừng tinh chỉnh: vài trăm chunk không đủ để việc tinh chỉnh có ý
# nghĩa thống kê — chỉnh chỉ là overfit lên bộ câu hỏi vàng.
K1 = 1.2
B = 0.75


@dataclass(slots=True)
class _Document:
    chunk: Chunk
    term_frequencies: dict[str, int]
    length: int


@dataclass(frozen=True, slots=True)
class _Stats:
    """Thống kê BM25 của MỘT tập tài liệu: số tài liệu, độ dài trung bình, df từng term.

    Có một bộ cho toàn corpus và một bộ cho mỗi ngôn ngữ. Bản Java ban đầu chỉ có bộ chung,
    với lập luận rằng IDF áp đều cho mọi tài liệu đang so nên đổi mẫu số không đổi thứ hạng.
    Lập luận đó đúng với IDF nhưng SAI với chuẩn hoá độ dài: hệ số B chấm tài liệu theo độ
    dài SO VỚI trung bình, mà trung bình lại phụ thuộc corpus có gì. Thêm chunk tiếng Nhật,
    tiếng Trung — dài hơn hẳn vì bigram sinh nhiều token — kéo trung bình lên, và thứ hạng
    giữa các chunk tiếng Việt đổi theo dù không chunk tiếng Việt nào thay đổi. Bộ đo bắt được
    đúng lỗi này: R@3 tiếng Việt tụt từ 93.0% xuống 91.2%.
    """

    document_count: int = 0
    average_length: float = 0.0
    document_frequencies: dict[str, int] = field(default_factory=dict)


def _compute_stats(documents: list[_Document]) -> _Stats:
    df: Counter[str] = Counter()
    total_length = 0
    for doc in documents:
        df.update(doc.term_frequencies.keys())
        total_length += doc.length
    average = total_length / len(documents) if documents else 0.0
    return _Stats(len(documents), average, dict(df))


class BM25Index:
    """Chỉ mục nghịch đảo tối giản + chấm điểm BM25."""

    def __init__(self, synonyms: SynonymTables | None = None) -> None:
        self._synonyms = synonyms
        self._documents: list[_Document] = []
        self._corpus_stats = _Stats()
        self._stats_by_lang: dict[str, _Stats] = {}
        self._languages: frozenset[str] = frozenset()

    def __len__(self) -> int:
        return len(self._documents)

    @property
    def languages(self) -> frozenset[str]:
        """Ngôn ngữ thực sự có mặt trong chỉ mục."""
        return self._languages

    def load(self, chunks: list[Chunk]) -> None:
        """Đánh chỉ mục toàn bộ corpus, thay thế chỉ mục cũ."""
        documents: list[_Document] = []
        by_lang: dict[str, list[_Document]] = {}

        for chunk in chunks:
            tokens = tokenize(chunk.indexed_text)
            document = _Document(chunk, dict(Counter(tokens)), len(tokens))
            documents.append(document)
            lang = normalize_lang(chunk.lang)
            if lang is not None:
                by_lang.setdefault(lang, []).append(document)

        self._documents = documents
        self._corpus_stats = _compute_stats(documents)
        self._stats_by_lang = {lang: _compute_stats(docs) for lang, docs in by_lang.items()}
        self._languages = frozenset(by_lang)

    def search(self, query: str | None, top_k: int, lang: str | None = None) -> list[Scored]:
        """top_k chunk có điểm DƯƠNG, giảm dần. lang lọc theo ngôn ngữ của chunk.

        Chunk điểm 0 bị LOẠI chứ không trả về với điểm 0: chúng làm nhiễu thứ hạng khi hợp
        nhất RRF. Mã ngôn ngữ mà chỉ mục không có thì bỏ lọc — xem langfilter.resolve_filter.
        """
        if not self._documents or top_k <= 0:
            return []

        filter_lang = resolve_filter(lang, self._languages)

        # Mở rộng bằng bảng từ của ĐÚNG ngôn ngữ sắp lọc, không phải ngôn ngữ người gọi yêu
        # cầu: khi lọc bị bỏ, truy vấn chấm trên toàn corpus nên cũng phải với sang mọi bảng.
        query_tokens = expand(query, filter_lang, self._synonyms)
        if not query_tokens:
            return []

        # Lọc ngôn ngữ nào thì chấm bằng thống kê của ngôn ngữ đó.
        if filter_lang is None:
            stats = self._corpus_stats
        else:
            stats = self._stats_by_lang[filter_lang]

        scored: list[Scored] = []
        for doc in self._documents:
            if not accepts(filter_lang, doc.chunk):
                continue
            score = self._score(doc, query_tokens, stats)
            if score > 0:
                scored.append(Scored(doc.chunk, score))

        # sort của Python ổn định như List.sort của Java: điểm bằng nhau giữ thứ tự nạp.
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _score(doc: _Document, query_tokens: list[str], stats: _Stats) -> float:
        """Điểm BM25 của một tài liệu với một truy vấn.

        IDF Robertson có cộng 1 trong log: idf = ln(1 + (N - df + 0.5) / (df + 0.5)). Cộng 1
        để idf không bao giờ ÂM với term xuất hiện ở mọi tài liệu. Bỏ chỗ +1 đó là bug kinh
        điển: một term phổ biến sẽ TRỪ điểm tài liệu chứa nó.
        """
        score = 0.0
        for term in query_tokens:
            tf = doc.term_frequencies.get(term)
            if tf is None:
                continue
            df = stats.document_frequencies.get(term, 0)
            idf = math.log(1 + (stats.document_count - df + 0.5) / (df + 0.5))
            average = stats.average_length
            normalized_length = doc.length / average if average > 0 else 1.0
            denominator = tf + K1 * (1 - B + B * normalized_length)
            score += idf * (tf * (K1 + 1)) / denominator
        return score
