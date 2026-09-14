"""Test dữ liệu, chỉ số và harness."""

import json
import math

import pytest

from eval.corpus import ROOT, check_golden_against_kb, load_golden, load_kb
from eval.harness import MIN_MRR, MIN_RECALL_AT_3, check_thresholds, main
from eval.metrics import (
    ALL_LANGS,
    Metrics,
    evaluate,
    evaluate_by_lang,
    f1,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from rag.normalize import remove_accents
from rag.types import GoldenCase

HOLDOUT = ROOT / "data" / "holdout.yml"


@pytest.fixture(scope="module")
def kb():
    return load_kb()


@pytest.fixture(scope="module")
def golden():
    return load_golden()


class TestCorpus:
    """Chứng minh dữ liệu bê sang từ VigoTrip nhất quán — và giữ nó nhất quán khi đồng bộ lại."""

    def test_knowledge_base_nhieu_ngon_ngu(self, kb):
        assert {"vi", "en"} <= {c.lang for c in kb}
        assert all(c.doc_id and c.content for c in kb)

    def test_doc_id_khong_trung(self, kb):
        assert len({c.doc_id for c in kb}) == len(kb)

    def test_lang_mac_dinh_la_vi_va_duoc_chuan_hoa(self, tmp_path):
        (tmp_path / "kb.yml").write_text(
            "- docId: a\n  content: nội dung\n- docId: b\n  content: content\n  lang: ' EN '\n",
            encoding="utf-8",
        )
        assert [c.lang for c in load_kb(tmp_path)] == ["vi", "en"]

    def test_loc_theo_lang(self):
        chunks = load_kb(lang="en")
        assert chunks and {c.lang for c in chunks} == {"en"}

    def test_doc_id_trung_giua_hai_file_thi_bao_loi(self, tmp_path):
        for name in ("a.yml", "b.yml"):
            (tmp_path / name).write_text("- docId: x\n  content: y\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_kb(tmp_path)

    def test_bo_cau_hoi_vang(self, golden):
        assert len(golden) >= 100
        assert all(case.query and case.expected for case in golden)

    def test_moi_doc_id_ky_vong_deu_ton_tai(self, golden, kb):
        assert check_golden_against_kb(golden, kb) == []

    def test_chunk_ky_vong_cung_ngon_ngu_voi_cau_hoi(self, golden, kb):
        """Nếu câu hỏi tiếng Việt lại kỳ vọng chunk tiếng Anh, cấu hình "+ lọc lang" sẽ không
        bao giờ trúng được câu đó — điểm tụt vì lỗi dữ liệu chứ không vì truy hồi."""
        lang_of = {c.doc_id: c.lang for c in kb}
        wrong = [
            (case.query, doc_id)
            for case in golden
            for doc_id in case.expected
            if lang_of[doc_id] != case.lang
        ]
        assert wrong == []

    def test_cau_hoi_khong_phai_ban_chep_cua_chunk(self, golden, kb):
        """Bộ vàng chỉ có nghĩa khi câu hỏi viết theo cách khách HỎI, không phải cách tài liệu
        VIẾT. Câu hỏi chép nguyên văn content thì bộ đo chỉ còn đo khả năng khớp chuỗi."""
        contents = {c.content.lower() for c in kb}
        assert [case.query for case in golden if case.query.lower() in contents] == []

    def test_moi_ngon_ngu_trong_bo_vang_deu_co_nguong(self, golden):
        langs = {case.lang for case in golden}
        assert langs <= set(MIN_RECALL_AT_3)
        assert langs <= set(MIN_MRR)


@pytest.fixture(scope="module")
def holdout():
    return load_golden(HOLDOUT)


class TestHoldout:
    """holdout.yml chỉ có giá trị khi nó thật sự tách khỏi golden.yml."""

    def test_doc_id_ton_tai_va_cung_ngon_ngu(self, holdout, kb):
        assert check_golden_against_kb(holdout, kb) == []
        lang_of = {c.doc_id: c.lang for c in kb}
        assert all(lang_of[d] == case.lang for case in holdout for d in case.expected)

    def test_khong_trung_golden_ke_ca_khi_bo_dau(self, holdout, golden):
        seen = {remove_accents(case.query.lower()) for case in golden}
        assert [c.query for c in holdout if remove_accents(c.query.lower()) in seen] == []

    def test_khong_chep_nguyen_van_chunk(self, holdout, kb):
        contents = " ".join(c.content.lower() for c in kb)
        assert [c.query for c in holdout if c.query.lower() in contents] == []

    def test_bo_cau_co_ma_hop_le(self, kb, golden, holdout):
        codes = load_golden(ROOT / "data" / "holdout_codes.yml")
        assert check_golden_against_kb(codes, kb) == []
        lang_of = {c.doc_id: c.lang for c in kb}
        assert all(lang_of[d] == case.lang for case in codes for d in case.expected)
        seen = {remove_accents(c.query.lower()) for c in [*golden, *holdout]}
        assert [c.query for c in codes if remove_accents(c.query.lower()) in seen] == []

    def test_harness_nhan_co_golden(self, capsys):
        assert main(["--golden", str(HOLDOUT), "--json", "--no-gate"]) == 0
        rows = json.loads(capsys.readouterr().out)
        assert {r["n"] for r in rows if r["name"].endswith("· vi")} == {len(load_golden(HOLDOUT))}


class TestMetrics:
    def test_recall_at_k(self):
        assert recall_at_k(["a", "b", "c"], ["c"], 3) == 1.0
        assert recall_at_k(["a", "b", "c"], ["c"], 2) == 0.0
        assert recall_at_k(["a"], ["x", "a"], 1) == 1.0, "nhiều đáp án đúng: trúng 1 là đủ"
        assert recall_at_k([], ["a"], 3) == 0.0

    def test_precision_at_k(self):
        assert precision_at_k(["a", "b", "c"], ["a"], 3) == 1 / 3
        assert precision_at_k(["a", "b", "c"], ["a", "b"], 3) == 2 / 3
        assert precision_at_k(["a"], ["a"], 3) == 1 / 3, "chia cho k kể cả khi trả về ít hơn k"

    def test_reciprocal_rank(self):
        assert reciprocal_rank(["a", "b"], ["a"]) == 1.0
        assert reciprocal_rank(["a", "b"], ["b"]) == 0.5
        assert reciprocal_rank(["a"], ["z"]) == 0.0

    def test_ndcg(self):
        assert ndcg_at_k(["a", "b"], ["a"], 5) == 1.0
        assert ndcg_at_k(["x", "a"], ["a"], 5) == pytest.approx(1 / math.log2(3))
        assert ndcg_at_k([], ["a"], 5) == 0.0
        assert ndcg_at_k(["a"], [], 5) == 0.0

    def test_f1(self):
        assert f1(0.0, 0.0) == 0.0
        assert f1(1.0, 1.0) == 1.0
        assert f1(1 / 3, 1.0) == pytest.approx(0.5)

    def test_evaluate_cham_nhu_ban_java(self):
        cases = [GoldenCase("q1", ["a"]), GoldenCase("q2", ["b"]), GoldenCase("q3", ["z"])]
        ranked = {
            "q1": ["a", "x", "y", "w", "v"],
            "q2": ["x", "y", "b", "w", "v"],
            "q3": ["x", "y", "w", "v", "u"],
        }
        m = evaluate("thử", cases, lambda case, k: ranked[case.query][:k])

        assert m.n == 3
        assert m.precision_at_1 == pytest.approx(1 / 3)
        assert m.recall_at_3 == pytest.approx(2 / 3)
        assert m.recall_at_5 == pytest.approx(2 / 3)
        assert m.precision_at_3 == pytest.approx((1 / 3 + 1 / 3) / 3)
        assert m.mrr == pytest.approx((1 + 1 / 3) / 3)
        assert len(m.misses) == 1 and '"q3"' in m.misses[0]

    def test_evaluate_khong_co_cau_hoi_thi_bao_loi(self):
        with pytest.raises(ValueError):
            evaluate("rỗng", [], lambda case, k: [])

    def test_evaluate_by_lang(self):
        cases = [GoldenCase("q1", ["a"], "vi"), GoldenCase("q2", ["b"], "en")]
        result = evaluate_by_lang("BM25", cases, lambda case, k: ["a", "b"])

        assert list(result) == ["en", "vi", ALL_LANGS]
        assert result["en"].name == "BM25 · en" and result["en"].n == 1
        assert result[ALL_LANGS].n == 2

        single = evaluate_by_lang("BM25", cases[:1], lambda case, k: ["a"])
        assert list(single) == ["vi"]


def metrics(name: str, recall_at_3: float, mrr: float) -> Metrics:
    return Metrics(name, 1, 0, 0, recall_at_3, 0, 0, 0, mrr, 0)


class TestThresholds:
    def test_ngon_ngu_thieu_nguong_thi_hong_dong_gop_khong_bi_cham(self):
        failures = check_thresholds(
            {
                "vi": metrics("BM25 · vi", 0.9, 0.8),
                "fr": metrics("BM25 · fr", 0.9, 0.9),
                ALL_LANGS: metrics("BM25 · gộp", 0.1, 0.1),
            }
        )
        assert len(failures) == 1 and "'fr'" in failures[0]

    def test_duoi_nguong_thi_hong(self):
        failures = check_thresholds({"vi": metrics("BM25 · vi", 0.5, 0.8)})
        assert len(failures) == 1 and "recall@3" in failures[0]

    def test_ghi_de_nguong(self):
        assert check_thresholds({"fr": metrics("x", 0.6, 0.6)}, min_recall3=0.5, min_mrr=0.5) == []


class TestHarness:
    def test_chay_offline_dat_nguong_va_in_json(self, capsys):
        code = main(["--json"])
        rows = json.loads(capsys.readouterr().out)

        assert code == 0
        langs = ["en", "ja", "vi", "zh", ALL_LANGS]
        assert [row["name"] for row in rows] == [
            *(f"BM25 · {lang}" for lang in langs),
            *(f"BM25 + lọc lang · {lang}" for lang in langs),
        ]
        assert all(0.0 <= row["recall_at_3"] <= 1.0 for row in rows)
