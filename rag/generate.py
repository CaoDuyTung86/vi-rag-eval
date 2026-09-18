"""Tầng sinh câu trả lời tối thiểu: system prompt của VigoTrip + ngữ cảnh RAG.

Tham chiếu: ChatService.buildSystemInstruction (WebProject).

data/prompts/vigotrip_chat.txt chép NGUYÊN VĂN các khối quyết định chuyện bịa hay không: nguyên
tắc chỉ nói điều có căn cứ, phong cách, khối KIẾN THỨC, bảo mật, dòng ngôn ngữ. Bỏ ba khối cần hệ
thống thật mà bộ đo không có: hướng dẫn công cụ, danh sách mã giảm giá (đọc DB theo tài khoản),
link điều hướng. Hệ quả khi chấm: câu nào production sẽ gọi tool (tra chuyến, tra đơn) thì ở đây
model chỉ còn cách trả lời bằng FAQ hoặc từ chối.

Sửa prompt bên Java thì phải chép lại file này. tests/test_generate_judge.py đối chiếu từng dòng với
ChatService.java khi có repo WebProject nằm cạnh; CI không có repo đó nên test tự bỏ qua.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from rag.types import Chunk

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "prompts"
PROMPT_PATH = PROMPTS_DIR / "vigotrip_chat.txt"

# Production chèn giờ thật. Cố định ở đây để prompt không đổi mỗi phút — đổi là trượt cache.
FIXED_NOW = "09:00 ngày 14/09/2026"

# rag.top-k trong application.yml của VigoTrip: số chunk nhét vào prompt.
TOP_K = 4


def rag_context(chunks: Sequence[Chunk]) -> str:
    """Khối KIẾN THỨC đúng như ChatService dựng: mỗi chunk "- Tiêu đề: Nội dung" và xuống dòng."""
    lines = []
    for chunk in chunks:
        title = f"{chunk.title}: " if chunk.title.strip() else ""
        lines.append(f"- {title}{chunk.content}\n")
    return "".join(lines)


def prompt_file(variant: str | None) -> Path:
    """Biến thể prompt -> file. None là bản production, tức bản phải trùng ChatService.java.

    Có để thử prompt mà không đụng vào bản production: đổi thẳng vigotrip_chat.txt là bộ đo
    hết so được với mọi bảng đã chạy, và test đối chiếu từng dòng với ChatService.java sẽ đỏ
    trong suốt thời gian còn đang thử. Biến thể nào thắng thì mới chép vào cả hai chỗ.
    """
    if variant is None:
        return PROMPT_PATH
    path = PROMPTS_DIR / f"vigotrip_chat_{variant}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Không có biến thể prompt {variant}: {path}")
    return path


def system_prompt(
    chunks: Sequence[Chunk],
    lang: str | None = "vi",
    now: str = FIXED_NOW,
    variant: str | None = None,
) -> str:
    template = prompt_file(variant).read_text(encoding="utf-8").rstrip("\n")
    return (
        template.replace("{{now}}", now)
        .replace("{{lang}}", lang or "vi")
        .replace("{{context}}", rag_context(chunks) or "- Không có FAQ bổ sung.\n")
    )
