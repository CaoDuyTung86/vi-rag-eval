"""Client embedding qua endpoint /embeddings tương thích OpenAI, kèm cache đĩa.

Tham chiếu: .../ai/embedding/OpenAiCompatibleEmbeddingClient.java + EmbeddingProperties.java

Mặc định khớp cấu hình bản Java (gemini-embedding-001, 768 chiều, lô 32) để số đo nhánh ngữ
nghĩa so được với RagRetrievalQualityTest ở chế độ live.

Cache đĩa KHÔNG phải tối ưu vặt: bộ đo nhúng vài trăm chunk và hơn trăm câu hỏi mỗi lần, và
khi thử nghiệm bạn sẽ chạy nó nhiều lần một ngày. Không cache thì mỗi lần chạy là một lượt ăn
vào hạn mức miễn phí và vài phút chờ — đủ để ngại chạy, mà bộ đo chỉ có giá trị khi được chạy
thường xuyên.

Biến môi trường:
  EMBEDDING_API_KEY (hoặc GEMINI_API_KEY), EMBEDDING_MODEL, EMBEDDING_DIMENSIONS,
  EMBEDDING_BASE_URL, EMBEDDING_MIN_INTERVAL_S
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx
import numpy as np

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "embeddings"

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODEL = "gemini-embedding-001"
DEFAULT_DIMENSIONS = 768
DEFAULT_BATCH_SIZE = 32

# Khoảng nghỉ tối thiểu giữa hai lời gọi, cùng con số MIN_INTERVAL_MS của bộ đo Java. Hạn mức
# miễn phí của Gemini tính theo phút; dồn lời gọi sát nhau là ăn 429 rồi phải chờ lâu hơn.
DEFAULT_MIN_INTERVAL_S = 1.5


class EmbeddingError(RuntimeError):
    """Lời gọi embedding hỏng. Nhánh ngữ nghĩa phải chịu được lỗi này và trả về rỗng."""


def _env_api_key() -> str:
    return (os.environ.get("EMBEDDING_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()


class EmbeddingClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str | None = None,
        dimensions: int | None = None,
        base_url: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        cache_dir: Path | str = CACHE_DIR,
        http_client: httpx.Client | None = None,
        min_interval_s: float | None = None,
        max_retries: int = 4,
        timeout_s: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = (_env_api_key() if api_key is None else api_key).strip()
        self.model = model or os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
        if dimensions is None:
            dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", DEFAULT_DIMENSIONS))
        self.dimensions = dimensions
        self.base_url = (base_url or os.environ.get("EMBEDDING_BASE_URL", DEFAULT_BASE_URL)).rstrip(
            "/"
        )
        self.batch_size = max(1, batch_size)
        self.cache_dir = Path(cache_dir)
        if min_interval_s is None:
            min_interval_s = float(
                os.environ.get("EMBEDDING_MIN_INTERVAL_S", DEFAULT_MIN_INTERVAL_S)
            )
        self.min_interval_s = min_interval_s
        self.max_retries = max(0, max_retries)
        self._http = http_client
        self._timeout_s = timeout_s
        self._sleep = sleep
        self._last_call_at: float | None = None

        # Số liệu vận hành, harness in ra sau mỗi lượt đo.
        self.api_calls = 0
        self.rate_limit_retries = 0

    @property
    def available(self) -> bool:
        """Thiếu key thì hệ thống phải chạy tiếp bằng BM25, không được sập."""
        return bool(self.api_key) and self.api_key != "YOUR_API_KEY_HERE" and bool(self.model)

    def embed(self, text: str) -> np.ndarray:
        return self.embed_all([text])[0]

    def embed_all(self, texts: Sequence[str]) -> np.ndarray:
        """Nhúng nhiều văn bản, trả ma trận float32 shape (len(texts), dim) cùng thứ tự.

        Văn bản đã có trong cache không tốn lời gọi nào; văn bản lặp lại chỉ gửi đi một lần.
        """
        if not texts:
            return np.empty((0, max(self.dimensions, 0)), dtype=np.float32)

        vectors: list[np.ndarray | None] = [self._read_cache(text) for text in texts]
        missing = [i for i, vector in enumerate(vectors) if vector is None]

        if missing:
            if not self.available:
                raise EmbeddingError("Chưa có API key embedding (EMBEDDING_API_KEY/GEMINI_API_KEY)")
            unique = list(dict.fromkeys(texts[i] for i in missing))
            fetched: dict[str, np.ndarray] = {}
            for start in range(0, len(unique), self.batch_size):
                batch = unique[start : start + self.batch_size]
                for text, vector in zip(batch, self._call_api(batch), strict=True):
                    self._write_cache(text, vector)
                    fetched[text] = vector
            for i in missing:
                vectors[i] = fetched[texts[i]]

        return np.vstack([v for v in vectors if v is not None]).astype(np.float32)

    # ------------------------------------------------------------------ gọi API

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=self._timeout_s)
        return self._http

    def _throttle(self) -> None:
        if self._last_call_at is not None and self.min_interval_s > 0:
            wait = self.min_interval_s - (time.monotonic() - self._last_call_at)
            if wait > 0:
                self._sleep(wait)
        self._last_call_at = time.monotonic()

    @staticmethod
    def _retry_after(response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("retry-after", "")
        try:
            return max(0.0, float(header))
        except ValueError:
            return float(min(60, 10 * 2 ** (attempt - 1)))

    def _call_api(self, batch: list[str]) -> list[np.ndarray]:
        body: dict[str, object] = {"model": self.model, "input": batch}
        if self.dimensions > 0:
            body["dimensions"] = self.dimensions
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/embeddings"

        attempt = 0
        while True:
            self._throttle()
            try:
                response = self._client().post(url, json=body, headers=headers)
            except httpx.HTTPError as error:
                raise EmbeddingError(f"Gọi API embedding thất bại: {error}") from error
            self.api_calls += 1

            if response.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                self.rate_limit_retries += 1
                wait = self._retry_after(response, attempt)
                print(
                    f"[embedding] Dính 429 (lần {attempt}/{self.max_retries}), chờ {wait:.0f}s...",
                    file=sys.stderr,
                )
                self._sleep(wait)
                continue
            if response.status_code >= 400:
                raise EmbeddingError(
                    f"API embedding trả HTTP {response.status_code}: {response.text[:300]}"
                )
            break

        try:
            payload = response.json()
        except ValueError as error:
            raise EmbeddingError("Phản hồi embedding không phải JSON") from error

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise EmbeddingError("Phản hồi embedding không có trường data")
        if len(data) != len(batch):
            raise EmbeddingError(
                f"Số vector trả về ({len(data)}) khác số văn bản gửi đi ({len(batch)})"
            )
        # Giao thức OpenAI đánh số từng phần tử. Bản Java tin vào thứ tự mảng; sắp theo index
        # khi có thì không tốn gì mà chặn được một kiểu lệch vector rất khó phát hiện.
        if all(isinstance(item, dict) and isinstance(item.get("index"), int) for item in data):
            data = sorted(data, key=lambda item: item["index"])

        vectors: list[np.ndarray] = []
        for item in data:
            raw = item.get("embedding") if isinstance(item, dict) else None
            if raw is None:
                raise EmbeddingError("Một phần tử data thiếu trường embedding")
            vectors.append(np.asarray(raw, dtype=np.float32))
        return vectors

    # ------------------------------------------------------------------ cache đĩa

    def _cache_path(self, text: str) -> Path:
        # Model và số chiều nằm trong khoá: đổi một trong hai là vector khác, phải trượt cache.
        raw = f"{self.model}\x00{self.dimensions}\x00{text}".encode()
        return self.cache_dir / f"{hashlib.sha256(raw).hexdigest()}.json"

    def _read_cache(self, text: str) -> np.ndarray | None:
        path = self._cache_path(text)
        if not path.exists():
            return None
        try:
            return np.asarray(json.loads(path.read_text(encoding="utf-8")), dtype=np.float32)
        except (json.JSONDecodeError, ValueError):
            path.unlink(missing_ok=True)
            return None

    def _write_cache(self, text: str, vector: np.ndarray) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path(text).write_text(json.dumps(vector.tolist()), encoding="utf-8")
