# vi-rag-eval

Truy hồi lai tiếng Việt (BM25 + vector + RRF) kèm bộ đo chất lượng chạy được từ dòng lệnh.

Rút lõi từ module RAG của đồ án VigoTrip (Spring Boot, 1054 dòng Java) và viết lại bằng
Python, giữ nguyên bộ 57 câu hỏi vàng để so được điểm số trước/sau.

## Trạng thái

Khung repo. Phần hạ tầng đã chạy; phần thuật toán để trống có chủ ý — xem
[lộ trình 12 tuần](https://claude.ai/code/artifact/7db29778-1d1e-4728-8bdb-6a942b3db3c2).

| Đã viết sẵn (hạ tầng) | Bạn viết |
|---|---|
| `eval/corpus.py` — nạp KB và bộ vàng | `rag/normalize.py` — tuần 1 |
| `eval/harness.py` — CLI, bảng, cổng ngưỡng | `rag/synonyms.py` — tuần 1 |
| `rag/embed.py` — cache đĩa | `rag/bm25.py` — tuần 1 |
| `rag/types.py` — kiểu dùng chung | `rag/store.py`, `rag/fusion.py` — tuần 2 |
| Tests, CI | `eval/metrics.py` — tuần 3 |

Mọi hàm chưa cài đặt đều `raise NotImplementedError` kèm tên file Java tương ứng để
đối chiếu.

## Bắt đầu

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Lúc này `tests/test_corpus_and_metrics.py::TestCorpus` phải XANH — nó chứng minh dữ liệu
đã bê sang đúng. Các test còn lại đỏ cho tới khi bạn viết code; **đọc test trước khi
viết**, chúng định nghĩa hành vi rõ hơn docstring.

Chạy bộ đo:

```bash
python -m eval.harness
```

Nhánh từ khoá không cần API key. Muốn đo nhánh ngữ nghĩa thì đặt biến môi trường:

```bash
export EMBEDDING_API_KEY=...
```

## Đối chiếu với bản Java

Mở song song để tham chiếu — **đọc, không copy**:

```
D:\clone repo\WebProject\backend\ticket-booking\src\main\java\com\booking\api\ai\rag\
```

| File này | Bản Java |
|---|---|
| `rag/normalize.py` | `TextNormalizer.java` (67 dòng) |
| `rag/synonyms.py` + `data/synonyms.yml` | `SynonymExpander.java` (100 dòng) |
| `rag/bm25.py` | `LexicalIndex.java` (114 dòng) |
| `rag/store.py` | `InMemoryVectorStore.java` + `VectorCodec.java` |
| `rag/fusion.py` | `HybridRetriever.java` (150 dòng) |
| `eval/metrics.py` + `eval/harness.py` | `RagRetrievalQualityTest.java` |

## Dữ liệu

| File | Nguồn | Ghi chú |
|---|---|---|
| `data/golden.yml` | `src/test/resources/rag-eval.yml` | 57 câu, copy nguyên |
| `data/kb/faq-vi.yml` | `src/main/resources/knowledge/faq-vi.yml` | 56 chunk, 13 category |
| `data/synonyms.yml` | tách từ `SynonymExpander.java` | hard-code → dữ liệu |

Bộ câu hỏi vàng viết theo cách khách **hỏi** chứ không phải cách knowledge base **viết**:
không dấu, sai chính tả, tiếng lóng. Có một test canh giữ tính chất đó
(`test_cau_hoi_khong_phai_ban_chep_cua_chunk`) — nếu bạn thêm câu hỏi bằng cách chép lại
nội dung chunk thì bộ đo mất ý nghĩa và test sẽ báo.

## Baseline

Điền sau khi hoàn thành tuần 3. Ngưỡng của bản Java: `recall@3 ≥ 0.85`, `MRR ≥ 0.70`.

| Nhánh | P@1 | R@3 | R@5 | F1@3 | MRR |
|---|---|---|---|---|---|
| lexical | | | | | |
| semantic | | | | | |
| hybrid | | | | | |

Xong tuần 3 thì `git tag baseline` để mọi thí nghiệm từ tuần 6 có mốc so sánh.
Nhật ký thí nghiệm: [experiments.md](experiments.md).
