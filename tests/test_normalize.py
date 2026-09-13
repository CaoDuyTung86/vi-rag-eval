"""Cách cắt token quyết định nhánh BM25 nhìn thấy gì.

Port TextNormalizerTest bên Java, cộng các test tiếng Việt. Chốt hai thứ: nhánh Latin không
được đổi hành vi, và chữ CJK phải sinh ra token thay vì biến mất.
"""

from rag.normalize import contains_cjk, is_cjk, normalize, remove_accents, tokenize


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
        assert normalize("Hủy vé Đặt chỗ") == "huy ve dat cho"

    def test_cau_khong_dau_cho_cung_ket_qua(self):
        assert normalize("hanh ly ky gui") == normalize("hành lý ký gửi")


class TestTokenizeLatin:
    def test_tach_ranh_gioi_chu_so(self):
        assert tokenize("20kg") == ["20", "kg"]
        assert tokenize("mang 20kg hành lý") == ["mang", "20", "kg", "hanh", "ly"]

    def test_bo_token_mot_ky_tu(self):
        assert tokenize("a b hanh ly") == ["hanh", "ly"]
        # Số một chữ số cũng là token một ký tự nên bị bỏ — đúng như bản Java.
        assert tokenize("hành lý 7kg") == ["hanh", "ly", "kg"]

    def test_bo_dau_cau(self):
        assert tokenize("hành lý, vali!") == ["hanh", "ly", "vali"]

    def test_rong(self):
        assert tokenize(None) == []
        assert tokenize("   ") == []


class TestTokenizeCjk:
    def test_cat_thanh_bigram(self):
        # Không có bước này thì cả câu cho ra không token nào và chunk vô hình với BM25.
        assert tokenize("手荷物") == ["手荷", "荷物"]
        assert tokenize("行李规定") == ["行李", "李规", "规定"]

    def test_cau_hoi_va_tai_lieu_khop_qua_bigram_chung(self):
        # Người hỏi viết "荷物", tài liệu viết "手荷物" — chung bigram 荷物 là đủ để khớp.
        assert set(tokenize("荷物は何キロ")) & set(tokenize("手荷物の規定"))

    def test_day_mot_ky_tu_van_thanh_token(self):
        # Luật "bỏ token 1 ký tự" của nhánh Latin không áp cho chữ Hán.
        assert tokenize("犬") == ["犬"]

    def test_giu_dau_duc_tieng_nhat(self):
        # normalize() bỏ dấu phụ để phục vụ tiếng Việt; với tiếng Nhật thì が sẽ thành か.
        assert tokenize("がか") == ["がか"]
        assert "物が" in tokenize("荷物が")

    def test_dau_truong_am_va_dau_lap_nam_trong_day(self):
        assert tokenize("カード") == ["カー", "ード"]
        assert tokenize("各々") == ["各々"]

    def test_katakana_nua_do_rong_quy_ve_dang_chuan(self):
        assert tokenize("ﾍﾟｯﾄ") == tokenize("ペット")

    def test_cau_tron_hai_he_chu(self):
        tokens = tokenize("VNPAYで支払う")
        assert "vnpay" in tokens
        assert "支払" in tokens


class TestCjkDetection:
    def test_nhan_dien_han_kana_va_ngoai_le(self):
        for ch in ["犬", "ペ", "が", "ー", "々", "〆"]:
            assert is_cjk(ch), ch

    def test_khong_nham_dau_cau_va_chu_latin(self):
        for ch in ["A", "đ", " ", "・", "゛"]:
            assert not is_cjk(ch), ch

    def test_contains_cjk(self):
        assert contains_cjk("VNPAYで")
        assert not contains_cjk("hành lý")
        assert not contains_cjk(None)
