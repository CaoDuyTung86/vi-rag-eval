PYTHON ?= python

.PHONY: install test lint eval eval-live baseline export stats

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

# Nhánh từ khoá, không cần API key, có cổng ngưỡng theo ngôn ngữ.
eval:
	$(PYTHON) -m eval.harness

# Thêm nhánh Vector và Hybrid. Cần GEMINI_API_KEY hoặc EMBEDDING_API_KEY.
eval-live:
	$(PYTHON) -m eval.harness --live

baseline:
	$(PYTHON) -m eval.harness --json > baseline.json

# Xuất dữ liệu thật từ Neon vào data/private/ (đã gitignore). Cần extra [export].
export:
	$(PYTHON) scripts/export_neon.py

stats:
	$(PYTHON) scripts/stats_private.py
