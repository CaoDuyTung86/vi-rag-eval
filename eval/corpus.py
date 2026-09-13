"""Nạp knowledge base và bộ câu hỏi vàng. Hạ tầng — đã viết sẵn, không phải bài tập."""

from __future__ import annotations

from pathlib import Path

import yaml

from rag.types import Chunk, GoldenCase

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KB_DIR = ROOT / "data" / "kb"
DEFAULT_GOLDEN = ROOT / "data" / "golden.yml"


def load_kb(kb_dir: Path | str = DEFAULT_KB_DIR, lang: str | None = None) -> list[Chunk]:
    """Nạp mọi *.yml trong thư mục knowledge base.

    lang lọc theo trường lang của chunk. Tuần 8 (đo đa ngôn ngữ) sẽ cần nó để dựng
    được phép đo chéo: hỏi tiếng Anh trên kho tiếng Việt và ngược lại.
    """
    chunks: list[Chunk] = []
    seen: set[str] = set()

    for path in sorted(Path(kb_dir).glob("*.yml")):
        with path.open(encoding="utf-8") as f:
            entries = yaml.safe_load(f) or []
        for entry in entries:
            doc_id = str(entry.get("docId") or entry.get("doc_id") or "").strip()
            content = str(entry.get("content") or "").strip()
            if not doc_id or not content:
                continue
            if doc_id in seen:
                raise ValueError(f"docId trùng giữa các file knowledge base: {doc_id}")
            seen.add(doc_id)
            chunk = Chunk(
                doc_id=doc_id,
                content=content,
                title=str(entry.get("title") or ""),
                category=str(entry.get("category") or ""),
                lang=str(entry.get("lang") or "vi"),
            )
            if lang is None or chunk.lang == lang:
                chunks.append(chunk)

    if not chunks:
        raise ValueError(f"Không nạp được chunk nào từ {kb_dir}")
    return chunks


def load_golden(path: Path | str = DEFAULT_GOLDEN) -> list[GoldenCase]:
    """Nạp bộ câu hỏi vàng."""
    with Path(path).open(encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []

    cases = [
        GoldenCase(query=str(e["query"]).strip(), expected=[str(x) for x in e.get("expected", [])])
        for e in entries
        if e.get("query")
    ]
    if not cases:
        raise ValueError(f"Bộ câu hỏi vàng rỗng: {path}")
    return cases


def check_golden_against_kb(cases: list[GoldenCase], chunks: list[Chunk]) -> list[str]:
    """Trả về danh sách docId được kỳ vọng nhưng không tồn tại trong knowledge base.

    Kiểm tra này quan trọng hơn vẻ ngoài của nó: một docId gõ sai trong golden.yml làm
    câu hỏi đó KHÔNG BAO GIỜ đúng được, và điểm số tụt mà không có nguyên nhân nào
    nhìn thấy được. Bản Java cũng chặn đúng chỗ này trước khi chấm.
    """
    known = {c.doc_id for c in chunks}
    missing = {doc_id for case in cases for doc_id in case.expected if doc_id not in known}
    return sorted(missing)
