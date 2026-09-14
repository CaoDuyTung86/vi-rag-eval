"""Test bảng đồng nghĩa, BM25, kho vector, RRF và truy hồi lai.

Phần bảng đồng nghĩa là bản port SynonymExpanderTest bên Java. Phần còn lại chốt những bất
biến bản Python phải giữ để số đo so được với bản Java.
"""

import numpy as np
import pytest

from rag.bm25 import K1, B, BM25Index
from rag.embed import EmbeddingError
from rag.fusion import rrf
from rag.retriever import HybridRetriever
from rag.store import VectorStore
from rag.synonyms import expand, load_synonyms
from rag.types import Chunk, Scored


def chunk(doc_id: str, content: str, title: str = "", lang: str = "vi") -> Chunk:
    return Chunk(doc_id=doc_id, content=content, title=title, lang=lang)


CORPUS = [
    chunk(
        "baggage-plane",
        "Vé máy bay gồm 7kg hành lý xách tay và 20kg hành lý ký gửi.",
        "Hành lý máy bay",
    ),
    chunk(
        "baggage-bus",
        "Vé xe khách được miễn phí 20kg hành lý cho mỗi hành khách.",
        "Hành lý xe khách",
    ),
    chunk(
        "pets-plane",
        "Thú cưng đi máy bay phải ở trong lồng vận chuyển.",
        "Thú cưng trên máy bay",
    ),
    chunk(
        "baggage-plane-en",
        "A plane ticket includes 7kg of carry-on and 20kg of checked baggage.",
        "Plane baggage",
        "en",
    ),
    chunk(
        "pets-plane-ja",
        "ペットは専用のキャリーに入れて機内に持ち込めます。",
        "飛行機のペット",
        "ja",
    ),
]
VI = [c for c in CORPUS if c.lang == "vi"]


class TestSynonyms:
    def test_nap_du_bon_bang(self):
        tables = load_synonyms()
        assert set(tables) == {"vi", "en", "ja", "zh"}
        assert "kg" in tables["vi"]["hanh ly"]
        assert "cancellation" in tables["en"]["cancel"]

    def test_bang_tieng_viet_khong_con_khoa_tieng_anh(self):
        # luggage/baggage/baby đã chuyển sang bảng tiếng Anh cùng lúc với bộ lọc ngôn ngữ.
        assert "baggage" not in load_synonyms()["vi"]

    def test_khoa_bi_yaml_doc_thanh_bool_thi_bao_loi(self, tmp_path):
        path = tmp_path / "syn.yml"
        path.write_text("vi:\n  no: [khong]\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_synonyms(str(path))

    def test_cau_hoi_tieng_viet_mo_rong_bang_bang_tieng_viet(self):
        tokens = expand("cho tôi hỏi mang được mấy cân hành lý", "vi")
        assert {"hanh", "ly", "vali", "kg"} <= set(tokens)

    def test_cau_hoi_tieng_anh_chi_nhan_tu_tieng_anh(self):
        tokens = expand("how heavy can my suitcase be", "en")
        assert {"baggage", "luggage"} <= set(tokens)
        assert "hanh" not in tokens and "ly" not in tokens

    def test_bang_tieng_anh_noi_bien_the_hinh_thai(self):
        assert {"cancellation", "refund"} <= set(expand("i want to cancel", "en"))
        assert "payment" in expand("i already paid", "en")

    def test_khop_theo_ranh_gioi_tu(self):
        # "chọn" bỏ dấu thành "chon", chứa "cho" — khoá thú cưng.
        assert "meo" not in expand("chọn ghế xong bao lâu phải trả tiền", "vi")
        # "cùng" bỏ dấu thành "cung", chứa khoá "cun".
        assert "meo" not in expand("lưu thông tin người đi cùng", "vi")
        # Còn khi đúng là một từ thì vẫn phải khớp.
        assert {"thu", "cung"} <= set(expand("tôi mang theo con chó", "vi"))

    def test_khoa_co_dau_chi_khop_khi_cau_hoi_viet_dung_dau(self):
        # "cho" không dấu hầu như luôn là từ chức năng, và "chỗ" bỏ dấu cũng thành "cho". Khoá
        # "chó" chỉ khớp khi câu hỏi viết đúng dấu — experiments.md, mục khoá `chó` 14/09.
        assert "thu" not in expand("cho tôi hỏi mang được mấy cân hành lý", "vi")
        assert "thu" not in expand("trả tiền rồi có đổi chỗ ngồi được không", "vi")
        assert {"thu", "cung"} <= set(expand("chó nhà tôi đi xe khách được không", "vi"))
        # Cái giá đã biết: gõ không dấu thì mất phần mở rộng.
        assert "thu" not in expand("mang cho len xe khach duoc khong", "vi")

    def test_khoa_co_dau_khop_ca_cau_hoi_dang_to_hop(self):
        # "o" + dấu sắc rời (NFD) — một số bàn phím và trình duyệt gửi dạng này.
        assert "thu" in expand("con chó nhà tôi", "vi")

    def test_ngon_ngu_chua_co_bang_thi_ap_moi_bang(self):
        assert {"vali", "luggage"} <= set(expand("hành lý baggage", "fr"))
        assert {"vali", "luggage"} <= set(expand("hành lý baggage", None))

    def test_khoa_cjk_khop_chuoi_con(self):
        assert {"ペッ", "ット", "動物"} <= set(expand("犬を連れて行けますか", "ja"))
        assert {"宠物", "动物"} <= set(expand("可以带狗上车吗", "zh"))

    def test_cau_hoi_tieng_nhat_khong_nhan_tu_ngon_ngu_khac(self):
        tokens = expand("ペットを連れて行けますか", "ja")
        assert not {"thu", "cung", "pets"} & set(tokens)

    def test_giu_token_goc_khong_lap(self):
        tokens = expand("hủy vé hoàn tiền", "vi")
        assert tokens[:4] == ["huy", "ve", "hoan", "tien"]
        assert len(tokens) == len(set(tokens))

    def test_truy_van_rong(self):
        assert expand("", "vi") == []
        assert expand(None, "en") == []


class TestBM25:
    @pytest.fixture
    def index(self):
        idx = BM25Index()
        idx.load(CORPUS)
        return idx

    def test_tham_so_chuan(self):
        assert (K1, B) == (1.2, 0.75)

    def test_tim_dung_chunk(self, index):
        assert index.search("hành lý máy bay bao nhiêu kg", 3)[0].chunk.doc_id == "baggage-plane"

    def test_khong_dau_khop_nhu_co_dau(self, index):
        assert index.search("hanh ly may bay", 3)[0].chunk.doc_id == "baggage-plane"

    def test_tieng_long_khop_nho_dong_nghia(self, index):
        assert index.search("mang được mấy cân", 3, "vi")[0].chunk.doc_id.startswith("baggage")

    def test_loai_diem_khong(self, index):
        assert index.search("xxxyyyzzz", 3) == []

    def test_tieu_de_duoc_danh_chi_muc(self, index):
        assert index.search("thú cưng", 3)[0].chunk.doc_id == "pets-plane"

    def test_ton_trong_top_k(self, index):
        assert len(index.search("hành lý", 1)) == 1

    def test_idf_khong_am(self, index):
        # "hành lý" có ở nhiều chunk. Bỏ +1 trong log của IDF thì term phổ biến TRỪ điểm.
        assert all(hit.score > 0 for hit in index.search("hành lý", 5))

    def test_loc_theo_ngon_ngu(self, index):
        hits = index.search("hành lý baggage kg", 5, "en")
        assert hits and {hit.chunk.lang for hit in hits} == {"en"}

    def test_ma_ngon_ngu_khong_co_trong_chi_muc_thi_bo_loc(self, index):
        ids = [hit.chunk.doc_id for hit in index.search("hành lý", 5, "fr")]
        assert ids == [hit.chunk.doc_id for hit in index.search("hành lý", 5)]

    def test_ngon_ngu_co_trong_chi_muc(self, index):
        assert index.languages == {"vi", "en", "ja"}

    def test_chu_cjk_khong_vo_hinh(self, index):
        assert index.search("ペットを連れて行けますか", 3, "ja")[0].chunk.doc_id == "pets-plane-ja"

    def test_thong_ke_theo_ngon_ngu_khong_bi_corpus_khac_keo_lech(self):
        """Lỗi mà bộ đo Java từng bắt: thêm chunk CJK dài làm đổi thứ hạng tiếng Việt.

        Có lọc lang thì điểm tiếng Việt phải GIỐNG HỆT dù corpus có thêm gì. Không lọc thì
        điểm đổi — đó là lý do cấu hình "+ lọc lang" tồn tại.
        """
        long_cjk = [chunk(f"long-ja-{i}", "長い説明文" * 40, "説明", "ja") for i in range(5)]
        only_vi, mixed = BM25Index(), BM25Index()
        only_vi.load(VI)
        mixed.load(VI + long_cjk)
        query = "hành lý máy bay"

        def scored(idx, lang):
            return [(hit.chunk.doc_id, hit.score) for hit in idx.search(query, 5, lang)]

        assert scored(mixed, "vi") == scored(only_vi, "vi")
        assert scored(mixed, None) != scored(only_vi, None)

    def test_chi_muc_rong_va_truy_van_rong(self, index):
        assert BM25Index().search("hành lý", 3) == []
        assert index.search("", 3) == []
        assert index.search(None, 3) == []


class TestVectorStore:
    @staticmethod
    def store(chunks, rows):
        s = VectorStore()
        s.load(chunks, np.array(rows, dtype=np.float32))
        return s

    A = chunk("a", "a")
    B_EN = chunk("b", "b", lang="en")
    C = chunk("c", "c")

    def test_cosine_giam_dan_va_nguong(self):
        s = self.store([self.A, self.B_EN, self.C], [[1, 0], [0.8, 0.6], [0, 1]])
        hits = s.search([1, 0], 5, 0.5)
        assert [h.chunk.doc_id for h in hits] == ["a", "b"]
        assert [h.score for h in hits] == pytest.approx([1.0, 0.8], abs=1e-6)

    def test_vector_chua_chuan_hoa_van_ra_cosine(self):
        assert self.store([self.A], [[2, 0]]).search([5, 0], 1, 0.0)[0].score == pytest.approx(1.0)

    def test_loc_ngon_ngu_va_bo_loc_khi_ma_la(self):
        s = self.store([self.A, self.B_EN, self.C], [[1, 0], [0.8, 0.6], [0, 1]])
        assert [h.chunk.doc_id for h in s.search([1, 0], 5, 0.0, "en")] == ["b"]
        assert [h.chunk.doc_id for h in s.search([1, 0], 5, 0.0, "fr")] == ["a", "b", "c"]

    def test_vector_khong_thi_cosine_bang_khong(self):
        assert self.store([self.A], [[0, 0]]).search([1, 0], 5, 0.0)[0].score == 0.0
        assert self.store([self.A], [[1, 0]]).search([0, 0], 5, 0.1) == []

    def test_lech_so_chieu_bao_loi(self):
        with pytest.raises(ValueError):
            self.store([self.A, self.C], [[1, 0]])
        with pytest.raises(ValueError):
            self.store([self.A], [[1, 0]]).search([1, 0, 0], 5, 0.0)

    def test_kho_rong(self):
        assert VectorStore().search([1, 0], 5, 0.0) == []


class TestRRF:
    def test_chunk_o_ca_hai_nhanh_len_dau(self):
        a, b, c = chunk("a", "a"), chunk("b", "b"), chunk("c", "c")
        lexical = [Scored(b, 9.9), Scored(a, 1.0)]
        semantic = [Scored(c, 0.9), Scored(a, 0.8)]
        # a hạng 2 ở cả hai nhánh: 2/(60+2) lớn hơn 1/(60+1) của b hay c.
        assert rrf([lexical, semantic], 3)[0].doc_id == "a"

    def test_chiu_duoc_nhanh_rong(self):
        a = chunk("a", "a")
        assert [c.doc_id for c in rrf([[Scored(a, 1.0)], []], 3)] == ["a"]
        assert rrf([[], []], 3) == []

    def test_gop_theo_doc_id(self):
        lexical = [Scored(chunk("a", "a"), 1.0)]
        semantic = [Scored(chunk("a", "a"), 0.9)]
        assert len(rrf([lexical, semantic], 5)) == 1

    def test_ton_trong_top_k(self):
        hits = [Scored(chunk(str(i), str(i)), 1.0) for i in range(10)]
        assert len(rrf([hits, []], 3)) == 3
        assert rrf([hits, []], 0) == []

    def test_hoa_diem_thi_nhanh_duyet_truoc_thang(self):
        # Hạng (1, 2) và (2, 1) cho cùng 1/61 + 1/62 — thí nghiệm P@1 ngày 14/09: 7/9 câu tiếng
        # Việt tụt P@1 vì đúng luật này.
        a, b = chunk("a", "a"), chunk("b", "b")
        lexical = [Scored(a, 9.0), Scored(b, 8.0)]
        semantic = [Scored(b, 0.9), Scored(a, 0.8)]
        assert rrf([lexical, semantic], 2)[0].doc_id == "a"
        assert rrf([semantic, lexical], 2)[0].doc_id == "b"

    def test_trong_so_mac_dinh_giu_nguyen_ket_qua_cu(self):
        a, b, c = chunk("a", "a"), chunk("b", "b"), chunk("c", "c")
        lexical = [Scored(a, 3.0), Scored(b, 2.0)]
        semantic = [Scored(c, 0.9), Scored(b, 0.8)]
        assert rrf([lexical, semantic], 3) == rrf([lexical, semantic], 3, weights=[1.0, 1.0])

    def test_trong_so_nho_hon_pha_hoa_nghieng_ve_nhanh_kia(self):
        a, b = chunk("a", "a"), chunk("b", "b")
        lexical = [Scored(a, 9.0), Scored(b, 8.0)]
        semantic = [Scored(b, 0.9), Scored(a, 0.8)]
        assert rrf([lexical, semantic], 2, weights=[0.5, 1.0])[0].doc_id == "b"

    def test_trong_so_0_bo_han_nhanh(self):
        a, b = chunk("a", "a"), chunk("b", "b")
        fused = rrf([[Scored(a, 9.0)], [Scored(b, 0.9)]], 5, weights=[0.0, 1.0])
        assert [c.doc_id for c in fused] == ["b"]

    def test_so_trong_so_phai_bang_so_nhanh(self):
        with pytest.raises(ValueError):
            rrf([[], []], 3, weights=[1.0])


class FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]], available: bool = True) -> None:
        self.vectors = vectors
        self.available = available

    def embed(self, text: str) -> np.ndarray:
        if text not in self.vectors:
            raise EmbeddingError(f"không có vector cho {text!r}")
        return np.asarray(self.vectors[text], dtype=np.float32)


class TestHybridRetriever:
    QUERY = "hành lý máy bay"

    @staticmethod
    def build(chunks, embedder, **kwargs):
        bm25 = BM25Index()
        bm25.load(chunks)
        store = VectorStore()
        store.load(chunks, np.eye(len(chunks), dtype=np.float32))
        return HybridRetriever(bm25, store, embedder, **kwargs)

    def test_khong_co_embedder_thi_ket_qua_la_bm25(self):
        r = self.build(VI, None)
        lexical = [h.chunk.doc_id for h in r.bm25.search(self.QUERY, 3)]
        assert [c.doc_id for c in r.retrieve(self.QUERY, 3)] == lexical

    def test_embedding_hong_thi_lui_ve_bm25_va_ghi_so(self):
        errors = []
        r = self.build(VI, FakeEmbedder({}), on_embedding_error=lambda q, e: errors.append(q))
        lexical = [h.chunk.doc_id for h in r.bm25.search(self.QUERY, 3)]
        assert [c.doc_id for c in r.retrieve(self.QUERY, 3)] == lexical
        assert r.embedding_failures == 1
        assert errors == [self.QUERY]

    def test_chunk_co_mat_o_ca_hai_nhanh_duoc_day_len(self):
        # BM25 xếp baggage-plane đầu; nhánh vector chỉ trả baggage-bus (vector [0,1,0]).
        r = self.build(VI, FakeEmbedder({self.QUERY: [0, 1, 0]}))
        assert r.bm25.search(self.QUERY, 1)[0].chunk.doc_id == "baggage-plane"
        assert r.retrieve(self.QUERY, 3)[0].doc_id == "baggage-bus"
        assert [c.doc_id for c in r.retrieve_semantic_only(self.QUERY, 3)] == ["baggage-bus"]

    def test_loc_ngon_ngu_ap_cho_ca_hai_nhanh(self):
        vector_of_vi_chunk = [1, 0, 0, 0, 0]
        r = self.build(CORPUS, FakeEmbedder({"baggage kg": vector_of_vi_chunk}))
        hits = r.retrieve("baggage kg", 5, "en")
        assert hits and {c.lang for c in hits} == {"en"}

    def test_truy_van_rong(self):
        r = self.build(VI, FakeEmbedder({}))
        assert r.retrieve("   ", 3) == []
        assert r.retrieve_semantic_only(None, 3) == []
        assert r.embedding_failures == 0

    def test_vector_fill_giu_thu_tu_vector_roi_bu_bm25(self):
        # Vector chỉ trả baggage-bus; BM25 xếp baggage-plane đầu. Bù: bus trước, BM25 lấp sau.
        r = self.build(VI, FakeEmbedder({self.QUERY: [0, 1, 0]}), fusion="vector_fill")
        lexical = [h.chunk.doc_id for h in r.bm25.search(self.QUERY, 3)]
        got = [c.doc_id for c in r.retrieve(self.QUERY, 3)]
        assert got[0] == "baggage-bus"
        assert got[1:] == [d for d in lexical if d != "baggage-bus"][:2]

    def test_vector_rerank_khong_cho_bm25_them_chunk_moi(self):
        r = self.build(VI, FakeEmbedder({self.QUERY: [0, 1, 0]}), fusion="vector_rerank")
        assert [c.doc_id for c in r.retrieve(self.QUERY, 3)] == ["baggage-bus"]

    @pytest.mark.parametrize("fusion", ["vector_fill", "vector_rerank"])
    def test_cach_ghep_moi_van_lui_ve_bm25_khi_khong_co_vector(self, fusion):
        r = self.build(VI, FakeEmbedder({}), fusion=fusion)
        lexical = [h.chunk.doc_id for h in r.bm25.search(self.QUERY, 3)]
        assert [c.doc_id for c in r.retrieve(self.QUERY, 3)] == lexical

    def test_cach_ghep_la_thi_bao_loi(self):
        with pytest.raises(ValueError):
            self.build(VI, None, fusion="cong_diem")
