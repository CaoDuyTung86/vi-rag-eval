"""Test dữ liệu (xanh ngay) và test chỉ số (đỏ cho tới tuần 3)."""

from eval.corpus import check_golden_against_kb, load_golden, load_kb
from eval.metrics import f1, precision_at_k, recall_at_k, reciprocal_rank


class TestCorpus:
    """Nhóm này XANH ngay từ đầu — nó chứng minh dữ liệu đã bê sang đúng."""

    def test_nap_duoc_knowledge_base(self):
        chunks = load_kb()
        assert len(chunks) >= 50
        assert all(c.doc_id and c.content for c in chunks)

    def test_doc_id_khong_trung(self):
        chunks = load_kb()
        assert len({c.doc_id for c in chunks}) == len(chunks)

    def test_nap_duoc_bo_cau_hoi_vang(self):
        cases = load_golden()
        assert len(cases) >= 50
        assert all(c.query and c.expected for c in cases)

    def test_moi_docId_ky_vong_deu_ton_tai(self):
        # Một docId gõ sai làm câu hỏi đó không bao giờ đúng được, mà điểm số thì tụt
        # không có nguyên nhân nhìn thấy được.
        assert check_golden_against_kb(load_golden(), load_kb()) == []

    def test_cau_hoi_khong_phai_ban_chep_cua_chunk(self):
        """Bộ vàng chỉ có nghĩa khi câu hỏi viết theo cách khách HỎI, không phải cách
        knowledge base VIẾT. Nếu câu hỏi là bản sao nguyên văn của content thì bộ đo
        chỉ đo được khả năng khớp chuỗi."""
        contents = {c.content.lower() for c in load_kb()}
        for case in load_golden():
            assert case.query.lower() not in contents


class TestMetrics:
    def test_recall_at_k(self):
        assert recall_at_k(["a", "b", "c"], ["c"], 3) == 1.0
        assert recall_at_k(["a", "b", "c"], ["c"], 2) == 0.0
        assert recall_at_k(["a"], ["x", "a"], 1) == 1.0, "nhiều đáp án đúng: trúng 1 là đủ"
        assert recall_at_k([], ["a"], 3) == 0.0

    def test_precision_at_k(self):
        assert precision_at_k(["a", "b", "c"], ["a"], 3) == 1 / 3
        assert precision_at_k(["a", "b", "c"], ["a", "b"], 3) == 2 / 3
        assert precision_at_k(["x", "y", "z"], ["a"], 3) == 0.0

    def test_reciprocal_rank(self):
        assert reciprocal_rank(["a", "b"], ["a"]) == 1.0
        assert reciprocal_rank(["a", "b"], ["b"]) == 0.5
        assert reciprocal_rank(["a", "b", "c"], ["c"]) == 1 / 3
        assert reciprocal_rank(["a"], ["z"]) == 0.0

    def test_f1(self):
        assert f1(0.0, 0.0) == 0.0, "không được chia cho 0"
        assert f1(1.0, 1.0) == 1.0
        assert abs(f1(1 / 3, 1.0) - 0.5) < 1e-9
