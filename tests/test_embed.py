"""Test client embedding bằng transport giả của httpx — không có lời gọi mạng nào."""

import json

import httpx
import numpy as np
import pytest

from rag.embed import EmbeddingClient, EmbeddingError


def fake_vector(text: str, dim: int) -> list[float]:
    return [float(len(text) + i) for i in range(dim)]


class Recorder:
    """Handler giả: trả vector suy ra từ độ dài văn bản và ghi lại mọi request."""

    def __init__(self) -> None:
        self.bodies: list[dict] = []
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(request)
        self.bodies.append(body)
        dim = body.get("dimensions", 4)
        data = [
            {"index": i, "embedding": fake_vector(text, dim)}
            for i, text in enumerate(body["input"])
        ]
        return httpx.Response(200, json={"data": data})


def make_client(handler, tmp_path, **overrides) -> EmbeddingClient:
    params = {
        "model": "m",
        "dimensions": 4,
        "base_url": "https://example.test/v1/",
        "batch_size": 2,
        "cache_dir": tmp_path,
        "http_client": httpx.Client(transport=httpx.MockTransport(handler)),
        "min_interval_s": 0,
        "sleep": lambda seconds: None,
    }
    api_key = overrides.pop("api_key", "test-key")
    params.update(overrides)
    return EmbeddingClient(api_key, **params)


def test_dinh_dang_request_theo_giao_thuc_openai(tmp_path):
    rec = Recorder()
    make_client(rec, tmp_path).embed_all(["xin chào"])

    request = rec.requests[0]
    assert str(request.url) == "https://example.test/v1/embeddings"
    assert request.headers["authorization"] == "Bearer test-key"
    assert rec.bodies[0] == {"model": "m", "input": ["xin chào"], "dimensions": 4}


def test_chia_lo_va_giu_thu_tu(tmp_path):
    rec = Recorder()
    vectors = make_client(rec, tmp_path).embed_all(["a", "bb", "ccc"])

    assert [body["input"] for body in rec.bodies] == [["a", "bb"], ["ccc"]]
    assert vectors.shape == (3, 4)
    assert vectors.dtype == np.float32
    assert vectors[:, 0].tolist() == [1.0, 2.0, 3.0]


def test_cache_dia_dung_duoc_giua_cac_lan_chay(tmp_path):
    first = make_client(Recorder(), tmp_path).embed_all(["a", "bb"])
    rec = Recorder()
    second = make_client(rec, tmp_path).embed_all(["a", "bb"])

    assert rec.bodies == []
    np.testing.assert_array_equal(first, second)


def test_chi_goi_cho_phan_chua_co_trong_cache_va_khu_trung(tmp_path):
    rec = Recorder()
    client = make_client(rec, tmp_path)
    client.embed_all(["a"])
    vectors = client.embed_all(["a", "bb", "bb"])

    assert [body["input"] for body in rec.bodies] == [["a"], ["bb"]]
    assert vectors.shape == (3, 4)


def test_doi_so_chieu_thi_truot_cache(tmp_path):
    make_client(Recorder(), tmp_path, dimensions=4).embed_all(["a"])
    rec = Recorder()
    vectors = make_client(rec, tmp_path, dimensions=8).embed_all(["a"])

    assert len(rec.bodies) == 1
    assert vectors.shape == (1, 8)


def test_sap_theo_index_khi_api_tra_lon_thu_tu(tmp_path):
    def reversed_handler(request):
        body = json.loads(request.content)
        data = [{"index": i, "embedding": fake_vector(t, 4)} for i, t in enumerate(body["input"])]
        return httpx.Response(200, json={"data": list(reversed(data))})

    vectors = make_client(reversed_handler, tmp_path).embed_all(["a", "bb"])
    assert vectors[:, 0].tolist() == [1.0, 2.0]


def test_so_vector_lech_so_van_ban_bao_loi_va_khong_ghi_cache(tmp_path):
    def short_handler(request):
        return httpx.Response(200, json={"data": [{"embedding": [1.0, 2.0, 3.0, 4.0]}]})

    with pytest.raises(EmbeddingError):
        make_client(short_handler, tmp_path).embed_all(["a", "bb"])
    assert list(tmp_path.iterdir()) == []


def test_loi_http_va_loi_mang_deu_thanh_embedding_error(tmp_path):
    with pytest.raises(EmbeddingError):
        make_client(lambda r: httpx.Response(500, text="boom"), tmp_path).embed_all(["a"])

    def broken(request):
        raise httpx.ConnectError("mất mạng", request=request)

    with pytest.raises(EmbeddingError):
        make_client(broken, tmp_path).embed_all(["b"])


def test_429_thi_cho_roi_thu_lai(tmp_path):
    calls = {"n": 0}
    sleeps: list[float] = []
    ok = Recorder()

    def flaky(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "3"})
        return ok(request)

    client = make_client(flaky, tmp_path, sleep=sleeps.append)
    assert client.embed_all(["a"]).shape == (1, 4)
    assert sleeps == [3.0]
    assert client.rate_limit_retries == 1
    assert client.api_calls == 2


def test_429_mai_thi_bo_cuoc_sau_so_lan_thu(tmp_path):
    calls = {"n": 0}

    def always_limited(request):
        calls["n"] += 1
        return httpx.Response(429)

    with pytest.raises(EmbeddingError):
        make_client(always_limited, tmp_path, max_retries=2).embed_all(["a"])
    assert calls["n"] == 3


def test_thieu_key_van_doc_duoc_cache_nhung_khong_goi_api(tmp_path):
    make_client(Recorder(), tmp_path).embed_all(["a"])
    keyless = make_client(Recorder(), tmp_path, api_key="")

    assert not keyless.available
    assert keyless.embed_all(["a"]).shape == (1, 4)
    with pytest.raises(EmbeddingError):
        keyless.embed_all(["chưa có trong cache"])
