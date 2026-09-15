"""Tầng sinh và judge tuần 9 — transport giả của httpx, không có lời gọi mạng nào."""

import json
import os
import re
from pathlib import Path

import httpx
import pytest

from eval.judge import agreement, parse_label
from rag.generate import PROMPT_PATH, system_prompt
from rag.llm import ChatClient, LlmError, load_env_file
from rag.types import Chunk


def ok(text):
    return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}


def make_chat(handler, tmp_path, **overrides):
    params = {
        "model": "m",
        "base_url": "https://example.test/v1/",
        "cache_dir": tmp_path,
        "http_client": httpx.Client(transport=httpx.MockTransport(handler)),
        "min_interval_s": 0,
        "sleep": lambda seconds: None,
    }
    params.update(overrides)
    return ChatClient("test-key", **params)


def test_request_theo_giao_thuc_openai_va_cache(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=ok("chào bạn"))

    chat = make_chat(handler, tmp_path, extra_body={"reasoning_effort": "low"})
    first = chat.complete("sys", "hỏi")
    second = chat.complete("sys", "hỏi")

    assert len(requests) == 1 and chat.api_calls == 1
    assert str(requests[0].url) == "https://example.test/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer test-key"
    assert json.loads(requests[0].content) == {
        "model": "m",
        "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "hỏi"}],
        "max_tokens": 800,
        "temperature": 0.7,
        "reasoning_effort": "low",
    }
    assert first.text == second.text == "chào bạn"
    assert not first.cached and second.cached


def test_doi_mot_chu_trong_prompt_la_truot_cache(tmp_path):
    chat = make_chat(lambda r: httpx.Response(200, json=ok("x")), tmp_path)
    chat.complete("sys", "hỏi")
    chat.complete("sys.", "hỏi")
    assert chat.api_calls == 2


def test_429_cho_roi_thu_lai(tmp_path):
    responses = iter(
        [httpx.Response(429, headers={"retry-after": "3"}), httpx.Response(200, json=ok("x"))]
    )
    waits = []
    chat = make_chat(lambda r: next(responses), tmp_path, sleep=waits.append)
    assert chat.complete("s", "u").text == "x"
    assert waits == [3.0] and chat.rate_limit_retries == 1


def test_noi_dung_rong_la_loi_khong_phai_cau_tra_loi(tmp_path):
    body = {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}
    chat = make_chat(lambda r: httpx.Response(200, json=body), tmp_path)
    with pytest.raises(LlmError, match="length"):
        chat.complete("s", "u")
    assert not list(tmp_path.iterdir())


def test_load_env_file_khong_ghi_de(tmp_path, monkeypatch):
    monkeypatch.setenv("VRE_TEST_CO_SAN", "giu")
    monkeypatch.delenv("VRE_TEST_MOI", raising=False)
    monkeypatch.delenv("VRE_TEST_NHAY", raising=False)
    path = tmp_path / ".env"
    content = '# chú thích\n\nVRE_TEST_MOI=a=b\nVRE_TEST_NHAY="c d"\nVRE_TEST_CO_SAN=de\n'
    path.write_text(content, encoding="utf-8")
    try:
        assert load_env_file(path) == ["VRE_TEST_MOI", "VRE_TEST_NHAY"]
        assert os.environ["VRE_TEST_MOI"] == "a=b"
        assert os.environ["VRE_TEST_NHAY"] == "c d"
        assert os.environ["VRE_TEST_CO_SAN"] == "giu"
    finally:
        os.environ.pop("VRE_TEST_MOI", None)
        os.environ.pop("VRE_TEST_NHAY", None)


def test_prompt_dung_khoi_kien_thuc_nhu_chatservice():
    chunks = [Chunk("a", "Nội dung A", title="Tiêu đề A"), Chunk("b", "Nội dung B")]
    prompt = system_prompt(chunks, "vi")
    assert "(RAG Context):\n- Tiêu đề A: Nội dung A\n- Nội dung B\n\nBẢO MẬT" in prompt
    assert prompt.endswith("DÙ NGƯỜI DÙNG CÓ CHAT NGÔN NGỮ KHÁC.")
    assert "NGÔN NGỮ GIAO TIẾP HIỆN TẠI LÀ: vi." in prompt
    assert "{{" not in prompt


CHAT_SERVICE = (
    Path(__file__).resolve().parents[2]
    / "WebProject/backend/ticket-booking/src/main/java/com/booking/api/service/ChatService.java"
)


@pytest.mark.skipif(not CHAT_SERVICE.exists(), reason="không có repo WebProject nằm cạnh")
def test_prompt_trung_nguyen_van_chatservice():
    """Mỗi dòng của file prompt phải có nguyên văn trong các chuỗi literal của ChatService."""
    literals = re.findall(r'"((?:[^"\\]|\\.)*)"', CHAT_SERVICE.read_text(encoding="utf-8"))
    text = "".join(s.replace("\\n", "\n").replace('\\"', '"') for s in literals)
    java_lines = set(text.split("\n"))
    # Dòng này bên Java ghép từ biến userContextStr + ".\n", không phải một literal.
    dynamic = {"Khách hàng chưa đăng nhập."}
    lines = PROMPT_PATH.read_text(encoding="utf-8").splitlines()
    missing = [s for s in lines if s and "{{" not in s and s not in java_lines | dynamic]
    assert missing == []


def test_prompt_khong_co_chunk():
    assert "(RAG Context):\n- Không có FAQ bổ sung.\n\nBẢO MẬT" in system_prompt([], "en")


def test_parse_label_chiu_duoc_code_fence():
    text = '```json\n{"ly_do": "nói phí 50.000đ", "nhan": "bia"}\n```'
    assert parse_label(text) == ("bia", "nói phí 50.000đ")
    with pytest.raises(ValueError):
        parse_label('{"nhan": "dung"}')
    with pytest.raises(ValueError):
        parse_label("không có json")


def test_agreement():
    result = agreement(
        [
            ("bia", "bia"),
            ("co_can_cu", "bia"),
            ("tu_choi_dung", "tu_choi_thua"),
            ("co_can_cu", "co_can_cu"),
        ]
    )
    assert (result.n, result.exact, result.bia_match) == (4, 2, 3)
    assert (result.bia_human, result.bia_caught, result.bia_false) == (1, 1, 1)
    assert result.confusion[("co_can_cu", "bia")] == 1
