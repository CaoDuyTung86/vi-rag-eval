"""Client chat qua endpoint /chat/completions tương thích OpenAI, kèm cache đĩa.

Tham chiếu: .../ai/llm/OpenAiCompatibleProvider.java

Dùng cho tuần 9: sinh câu trả lời (Gemini, cấu hình tầng CHAT của VigoTrip) và chấm câu trả lời
(LLM-judge). Cache đĩa vì lý do của rag/embed.py, cộng một lý do riêng: temperature 0.7 như
production nghĩa là gọi lại sẽ ra câu khác — mà judge phải chấm ĐÚNG câu bạn đã chấm tay. Có cache
thì câu trả lời đã sinh cố định cho tới khi đổi prompt, model hoặc tham số.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "llm"

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_MIN_INTERVAL_S = 1.5
RETRYABLE = (429, 503)


class LlmError(RuntimeError):
    """Lời gọi chat hỏng. Khi ĐO không có đường lui: báo lỗi, không ghi một câu trả lời rỗng."""


def load_env_file(path: Path | str) -> list[str]:
    """Nạp KEY=VALUE từ file .env vào os.environ, không ghi đè biến đã có. Trả tên biến đã nạp.

    Không in giá trị ra đâu. Chỉ hiểu cú pháp tối thiểu: dòng trống, dòng #, `export`, dấu nháy
    bao ngoài.
    """
    loaded: list[str] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and not os.environ.get(key):
            os.environ[key] = value
            loaded.append(key)
    return loaded


@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    latency_ms: float
    """Độ trễ của lời gọi thật đã sinh ra câu này; đọc từ cache thì vẫn là con số lúc đó."""
    cached: bool


class ChatClient:
    def __init__(
        self,
        api_key: str | None,
        *,
        model: str,
        base_url: str,
        max_tokens: int = 800,
        temperature: float = 0.7,
        extra_body: Mapping[str, object] | None = None,
        cache_dir: Path | str = CACHE_DIR,
        http_client: httpx.Client | None = None,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        max_retries: int = 4,
        timeout_s: float = 120.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.extra_body = dict(extra_body or {})
        self.cache_dir = Path(cache_dir)
        self.min_interval_s = min_interval_s
        self.max_retries = max(0, max_retries)
        self._http = http_client
        self._timeout_s = timeout_s
        self._sleep = sleep
        self._last_call_at: float | None = None

        self.api_calls = 0
        self.rate_limit_retries = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key) and bool(self.model)

    def complete(self, system: str, user: str) -> Reply:
        body = self._body(system, user)
        path = self._cache_path(body)
        if (hit := self._read_cache(path)) is not None:
            return hit
        if not self.available:
            raise LlmError(f"Chưa có API key cho {self.model}")
        text, latency_ms = self._call_api(body)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"text": text, "latency_ms": latency_ms}, ensure_ascii=False),
            encoding="utf-8",
        )
        return Reply(text, latency_ms, cached=False)

    # ------------------------------------------------------------------ gọi API

    def _body(self, system: str, user: str) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            **self.extra_body,
        }

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
        try:
            return max(0.0, float(response.headers.get("retry-after", "")))
        except ValueError:
            return float(min(60, 10 * 2 ** (attempt - 1)))

    def _call_api(self, body: dict[str, object]) -> tuple[str, float]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/chat/completions"
        attempt = 0
        while True:
            self._throttle()
            started = time.perf_counter()
            try:
                response = self._client().post(url, json=body, headers=headers)
            except httpx.HTTPError as error:
                raise LlmError(f"Gọi {self.model} thất bại: {error}") from error
            latency_ms = (time.perf_counter() - started) * 1000
            self.api_calls += 1

            if response.status_code in RETRYABLE and attempt < self.max_retries:
                attempt += 1
                self.rate_limit_retries += 1
                wait = self._retry_after(response, attempt)
                print(
                    f"[llm] {self.model} trả {response.status_code} "
                    f"(lần {attempt}/{self.max_retries}), chờ {wait:.0f}s...",
                    file=sys.stderr,
                )
                self._sleep(wait)
                continue
            if response.status_code >= 400:
                raise LlmError(
                    f"{self.model} trả HTTP {response.status_code}: {response.text[:300]}"
                )
            break

        try:
            choice = response.json()["choices"][0]
            content = choice["message"].get("content")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            raise LlmError(f"Phản hồi của {self.model} sai định dạng") from error
        if not isinstance(content, str) or not content.strip():
            # Model suy luận (gpt-oss) hết max_tokens khi còn đang nghĩ thì content rỗng.
            raise LlmError(
                f"{self.model} trả nội dung rỗng (finish_reason={choice.get('finish_reason')})"
            )
        return content, latency_ms

    # ------------------------------------------------------------------ cache đĩa

    def _cache_path(self, body: dict[str, object]) -> Path:
        # Cả body nằm trong khoá: đổi một chữ trong prompt hay một tham số là trượt cache.
        key = {"url": self.base_url, "body": body}
        raw = json.dumps(key, sort_keys=True, ensure_ascii=False)
        return self.cache_dir / f"{hashlib.sha256(raw.encode()).hexdigest()}.json"

    @staticmethod
    def _read_cache(path: Path) -> Reply | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Reply(str(data["text"]), float(data["latency_ms"]), cached=True)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            path.unlink(missing_ok=True)
            return None
