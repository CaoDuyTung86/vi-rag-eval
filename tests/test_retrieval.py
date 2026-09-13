"""Test cho synonyms, BM25 và RRF. Đỏ cho tới khi bạn cài đặt các module tương ứng."""

import pytest

from rag.bm25 import B, K1, BM25Index
from rag.fusion import rrf
from rag.synonyms import expand, load_synonyms
from rag.types import Chunk, Scored


def chunk(doc_id: str, content: str, title: str = "") -> Chunk:
    return Chunk(doc_id=doc_id, content=content, title=title)


class TestSynonyms:
    def test_bang_dong_nghia_nap_duoc(self):
        # Test này XANH ngay: loader là hạ tầng, đã viết sẵn.
        syn = load_synonyms()
        assert "hanh ly" in syn
        assert "kg" in syn["hanh ly"]

    def test_them_tu_khong_thay_the(self):
        tokens = expand("mang được mấy cân")
        assert "mang" in tokens, "token gốc phải còn nguyên"
        assert "hanh ly" not in tokens, "giá trị đồng nghĩa phải được tokenize, không nhét thô"
        assert "hanh" in tokens and "ly" in tokens

    def test_khong_lap_token(self):
        tokens = expand("hành lý vali ký gửi")
        assert len(tokens) == len(set(tokens)), "token lặp làm BM25 chấm điểm lệch"

    def test_khop_chuoi_con_nhieu_tu(self):
        # "mấy cân" là hai token nhưng một khoá.
        assert "kg" in expand("cho hỏi mấy cân")

    def test_tieng_long(self):
        assert "hoan" in expand("bùng vé thì sao")


class TestBM25:
    @pytest.fixture
    def index(self):
        idx = BM25Index()
        idx.load(
            [
                chunk("baggage-plane", "Vé máy bay gồm 7kg xách tay và 20kg ký gửi", "Hành lý máy bay"),
                chunk("baggage-bus", "Vé xe khách miễn phí 20kg hành lý", "Hành lý xe khách"),
                chunk("pets-plane", "Thú cưng đi máy bay phải có lồng", "Thú cưng máy bay"),
            ]
        )
        return idx

    def test_tham_so_chuan(self):
        assert (K1, B) == (1.2, 0.75)

    def test_tim_dung_chunk(self, index):
        hits = index.search("hành lý máy bay bao nhiêu kg", 3)
        assert hits[0].chunk.doc_id == "baggage-plane"

    def test_loai_diem_khong(self, index):
        hits = index.search("xxxyyyzzz không có trong corpus", 3)
        assert hits == [], "chunk điểm 0 phải bị loại, không trả về với score 0"

    def test_tieu_de_duoc_danh_chi_muc(self, index):
        # indexed_text gộp title + content; tiêu đề thường chứa đúng từ người dùng hỏi.
        assert index.search("thú cưng", 3)[0].chunk.doc_id == "pets-plane"

    def test_ton_trong_top_k(self, index):
        assert len(index.search("hành lý", 1)) == 1

    def test_idf_khong_am(self, index):
        # "hành lý" xuất hiện ở nhiều chunk. Nếu bỏ +1 trong log của IDF thì term phổ
        # biến sẽ TRỪ điểm và kết quả đảo lộn.
        for hit in index.search("hành lý", 3):
            assert hit.score > 0


class TestRRF:
    def test_chunk_o_ca_hai_nhanh_len_dau(self):
        a, b, c = chunk("a", "a"), chunk("b", "b"), chunk("c", "c")
        lexical = [Scored(b, 9.9), Scored(a, 1.0)]
        semantic = [Scored(c, 0.9), Scored(a, 0.8)]
        # a đứng hạng 2 ở cả hai nhánh -> tổng 2/(60+2) lớn hơn 1/(60+1) của b và c.
        assert rrf([lexical, semantic], 3)[0].doc_id == "a"

    def test_chiu_duoc_nhanh_rong(self):
        a = chunk("a", "a")
        assert [c.doc_id for c in rrf([[Scored(a, 1.0)], []], 3)] == ["a"]
        assert rrf([[], []], 3) == []

    def test_gop_theo_doc_id(self):
        # Cùng doc_id nhưng hai instance khác nhau — phải gộp làm một.
        lexical = [Scored(chunk("a", "a"), 1.0)]
        semantic = [Scored(chunk("a", "a"), 0.9)]
        assert len(rrf([lexical, semantic], 5)) == 1

    def test_ton_trong_top_k(self):
        hits = [Scored(chunk(str(i), str(i)), 1.0) for i in range(10)]
        assert len(rrf([hits, []], 3)) == 3
