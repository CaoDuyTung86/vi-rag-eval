"""Các test này ĐỊNH NGHĨA hành vi đúng, chốt theo bản Java đang chạy thật.

Chúng đỏ cho tới khi bạn cài đặt rag/normalize.py — đó là chủ ý. Đọc test trước khi
viết code: chúng nói rõ hơn docstring.
"""

import pytest

from rag.normalize import normalize, remove_accents, tokenize


class TestRemoveAccents:
    def test_bo_dau_tieng_viet(self):
        assert remove_accents("đặt vé máy bay") == "dat ve may bay"

    def test_chu_d_gach_ngang(self):
        # đ/Đ không tách được bằng NFD — phải thay tay. Đây là chỗ hay quên nhất.
        assert remove_accents("đường") == "duong"
        assert remove_accents("Đà Nẵng") == "Da Nang"

    def test_giu_nguyen_hoa_thuong(self):
        assert remove_accents("Hành Lý") == "Hanh Ly"

    def test_none_va_rong(self):
        assert remove_accents(None) == ""
        assert remove_accents("") == ""


class TestNormalize:
    def test_thuong_hoa_va_bo_dau(self):
        assert normalize("Hành Lý Ký Gửi") == "hanh ly ky gui"

    def test_cau_khong_dau_giu_nguyen(self):
        # Người dùng gõ không dấu phải cho ra cùng kết quả với người gõ có dấu.
        assert normalize("hanh ly ky gui") == normalize("hành lý ký gửi")


class TestTokenize:
    def test_tach_ranh_gioi_chu_so(self):
        # Lỗi này do bộ đo golden.yml phát hiện: tài liệu ghi "20kg" phải khớp được
        # câu hỏi "mang được bao nhiêu kg".
        assert tokenize("20kg") == ["20", "kg"]
        assert tokenize("hành lý 7kg") == ["hanh", "ly", "7", "kg"]

    def test_bo_token_mot_ky_tu(self):
        assert "a" not in tokenize("a b hanh ly")
        assert tokenize("a b hanh ly") == ["hanh", "ly"]

    def test_bo_dau_cau(self):
        assert tokenize("hành lý, vali!") == ["hanh", "ly", "vali"]

    def test_rong(self):
        assert tokenize(None) == []
        assert tokenize("   ") == []

    @pytest.mark.parametrize(
        "cau_hoi",
        [
            "cho tôi hỏi được mang bao nhiêu kg lên máy bay",
            "di xe khach mang duoc may can hanh ly",
        ],
    )
    def test_khong_sinh_token_rong(self, cau_hoi):
        assert all(t for t in tokenize(cau_hoi))
