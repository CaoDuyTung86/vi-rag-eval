"""Nạp knowledge base và bộ câu hỏi vàng."""

from __future__ import annotations

from pathlib import Path

import yaml

from rag.types import Chunk, GoldenCase

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KB_DIR = ROOT / "data" / "kb"
DEFAULT_GOLDEN = ROOT / "data" / "golden.yml"


def normalize_case_lang(raw: object) -> str:
    """Mã ngôn ngữ đã chuẩn hoá; bỏ trống trong YAML thì hiểu là tiếng Việt, như bản Java."""
    value = "" if raw is None else str(raw).strip().lower()
    return value or "vi"


def load_kb(kb_dir: Path | str = DEFAULT_KB_DIR, lang: str | None = None) -> list[Chunk]:
    """Nạp mọi *.yml trong thư mục knowledge base, theo thứ tự tên file.

    lang lọc theo ngôn ngữ của chunk, dùng khi muốn dựng một corpus một ngôn ngữ để so.
    """
    wanted = normalize_case_lang(lang) if lang is not None else None
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
            title = entry.get("title")
            chunk = Chunk(
                doc_id=doc_id,
                content=content,
                title="" if title is None else str(title),
                category=str(entry.get("category") or ""),
                lang=normalize_case_lang(entry.get("lang")),
            )
            if wanted is None or chunk.lang == wanted:
                chunks.append(chunk)

    if not chunks:
        raise ValueError(f"Không nạp được chunk nào từ {kb_dir}")
    return chunks


def load_golden(path: Path | str = DEFAULT_GOLDEN) -> list[GoldenCase]:
    """Nạp bộ câu hỏi vàng. `lang` là ngôn ngữ của CÂU HỎI, bỏ trống thì là "vi"."""
    with Path(path).open(encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []

    cases = [
        GoldenCase(
            query=str(entry["query"]),
            expected=[str(doc_id) for doc_id in entry.get("expected", [])],
            lang=normalize_case_lang(entry.get("lang")),
        )
        for entry in entries
        if entry.get("query")
    ]
    if not cases:
        raise ValueError(f"Bộ câu hỏi vàng rỗng: {path}")
    return cases


def check_golden_against_kb(cases: list[GoldenCase], chunks: list[Chunk]) -> list[str]:
    """docId được kỳ vọng nhưng không tồn tại trong knowledge base.

    Kiểm tra này quan trọng hơn vẻ ngoài của nó: một docId gõ sai làm câu hỏi đó KHÔNG BAO
    GIỜ đúng được, và điểm tụt mà không có nguyên nhân nào nhìn thấy được. Bản Java chặn
    đúng chỗ này trước khi chấm.
    """
    known = {chunk.doc_id for chunk in chunks}
    missing = {doc_id for case in cases for doc_id in case.expected if doc_id not in known}
    return sorted(missing)
