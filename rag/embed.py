"""Client embedding + cache đĩa.

TUẦN 2 — phần cache đã viết sẵn (nó là hạ tầng, không phải bài học). Bạn chỉ cần
cài đặt _call_api().

Cache đĩa KHÔNG phải tối ưu vặt: bộ đo chạy 57 truy vấn mỗi lần, và tuần 6-8 bạn sẽ
chạy nó vài chục lần một ngày. Không cache thì mỗi lần chạy là một lần trả tiền và
một lần chờ, đủ để bạn ngại chạy — mà bộ đo chỉ có giá trị khi bạn chạy nó thường xuyên.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "embeddings"

DEFAULT_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-004")
DEFAULT_BASE_URL = os.environ.get(
    "EMBEDDING_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
)


class EmbeddingError(RuntimeError):
    """Lỗi gọi API embedding. Nhánh ngữ nghĩa phải chịu được lỗi này và trả về rỗng."""


class EmbeddingClient:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("EMBEDDING_API_KEY", "")
        self.model = model
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        """Thiếu key thì hệ thống phải chạy tiếp bằng BM25, không được sập."""
        return bool(self.api_key)

    def embed(self, text: str) -> np.ndarray:
        cached = self._read_cache(text)
        if cached is not None:
            return cached
        if not self.available:
            raise EmbeddingError("Chưa đặt EMBEDDING_API_KEY")
        vector = self._call_api(text)
        self._write_cache(text, vector)
        return vector

    def embed_all(self, texts: list[str]) -> np.ndarray:
        """Nhúng nhiều văn bản. Trả về ma trận (len(texts), dim)."""
        return np.vstack([self.embed(t) for t in texts])

    # --- cache: đã viết sẵn ---

    def _key(self, text: str) -> str:
        raw = f"{self.model}\x00{text}".encode()
        return hashlib.sha256(raw).hexdigest()

    def _path(self, text: str) -> Path:
        return CACHE_DIR / f"{self._key(text)}.json"

    def _read_cache(self, text: str) -> np.ndarray | None:
        p = self._path(text)
        if not p.exists():
            return None
        try:
            return np.asarray(json.loads(p.read_text(encoding="utf-8")), dtype=np.float32)
        except (json.JSONDecodeError, ValueError):
            p.unlink(missing_ok=True)
            return None

    def _write_cache(self, text: str, vector: np.ndarray) -> None:
        self._path(text).write_text(json.dumps(vector.tolist()), encoding="utf-8")

    # --- phần bạn viết ---

    def _call_api(self, text: str) -> np.ndarray:
        """Gọi endpoint /embeddings tương thích OpenAI, trả về vector float32.

        Ném EmbeddingError khi hỏng — đừng để exception thô của httpx lọt lên trên,
        vì tầng gọi cần phân biệt "embedding hỏng, lùi về BM25" với lỗi lập trình.
        """
        raise NotImplementedError("Tuần 2: xem OpenAiCompatibleEmbeddingClient.java")
