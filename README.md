# vi-rag-eval

Truy hồi lai đa ngôn ngữ (vi / en / ja / zh) — BM25 + vector + RRF — kèm bộ đo chất lượng
chạy từ dòng lệnh.

Port từ module RAG của đồ án VigoTrip (Spring Boot). Giữ nguyên bộ câu hỏi vàng, và **nhánh
BM25 tái lập đúng từng con số của bản Java** ở tag `baseline` — nên mọi thí nghiệm làm ở đây vẫn
so được với hệ thống đang chạy thật. Từ 14/09/2026 bản Python đi trước bản Java hai thay đổi đã
đo (xem [experiments.md](experiments.md)); chúng sẽ được port sang Java.

## Trạng thái

| Phần | Trạng thái |
|---|---|
| `rag/normalize.py` — tách token Latin + bigram CJK | xong, khớp Java |
| `rag/synonyms.py` + `data/synonyms.yml` — 4 bảng | xong, khớp Java (khoá `chó` có dấu đã port 14/09) |
| `rag/bm25.py` — BM25, thống kê theo ngôn ngữ | xong, khớp Java |
| `rag/store.py`, `rag/fusion.py`, `rag/retriever.py` | xong; RRF duyệt nhánh Vector trước — đã port sang Java 14/09 |
| `rag/embed.py` — client embedding + cache đĩa | xong, test bằng transport giả |
| `eval/` — chỉ số, harness, cổng ngưỡng | xong |
| Baseline nhánh Vector / Hybrid | xong, khớp Java — 20 dòng live trùng `RagRetrievalQualityTest` từng chữ số (14/09/2026) |
| `learn/` — mạng nơ-ron numpy trên MNIST | bài tập nền tảng, không thuộc pipeline |

113 test, không test nào gọi mạng.

## Kết quả nhánh BM25

132 câu, sau khi áp khoá `chó` chỉ khớp khi có dấu:

```
Cấu hình                 Câu      P@1      R@3      R@5      P@3     F1@3      MRR
-----------------------------------------------------------------
BM25 · en                 37    81.1%    94.6%   100.0%   0.351   0.512   0.887
BM25 · ja                 18    72.2%    88.9%    94.4%   0.315   0.465   0.819
BM25 · vi                 59    72.9%    94.9%   100.0%   0.350   0.512   0.842
BM25 · zh                 18    66.7%   100.0%   100.0%   0.370   0.541   0.815
BM25 · gộp               132    74.2%    94.7%    99.2%   0.348   0.509   0.848
BM25 + lọc lang · en      37    86.5%    94.6%   100.0%   0.351   0.512   0.914
BM25 + lọc lang · ja      18    72.2%    94.4%   100.0%   0.352   0.513   0.844
BM25 + lọc lang · vi      59    74.6%    94.9%    96.6%   0.350   0.512   0.843
BM25 + lọc lang · zh      18    66.7%   100.0%   100.0%   0.389   0.560   0.824
BM25 + lọc lang · gộp    132    76.5%    95.5%    98.5%   0.356   0.519   0.861
```

Bảng trùng từng chữ số với `./mvnw test -Dtest=RagRetrievalQualityTest` trên WebProject tại
`9f17f77` — 130 câu, kể cả danh sách câu trượt và thứ tự top-5 — nằm ở tag `baseline`.

`+ lọc lang` là đường mà lượt chat thật đi qua: chỉ chấm chunk cùng ngôn ngữ với câu hỏi.

## Kết quả nhánh Vector / Hybrid

`gemini-embedding-001`, 768 chiều, 10 ứng viên mỗi nhánh, ngưỡng cosine 0.55. Chỉ trích dòng
gộp; bảng đầy đủ theo ngôn ngữ ở [experiments.md](experiments.md).

```
Cấu hình                 Câu      P@1      R@3      R@5      P@3     F1@3      MRR
-----------------------------------------------------------------
Vector · gộp             132    84.8%    99.2%   100.0%   0.356   0.524   0.914
Vector + lọc lang · gộp  132    95.5%    99.2%   100.0%   0.376   0.546   0.975
Hybrid (RRF) · gộp       132    95.5%   100.0%   100.0%   0.376   0.547   0.977
Hybrid + lọc lang · gộp  132    95.5%   100.0%   100.0%   0.379   0.549   0.976
```

Hybrid + lọc lang trước và sau khi RRF duyệt nhánh Vector trước (14/09):

| | vi P@1 | gộp P@1 | gộp MRR |
|---|---|---|---|
| BM25 trước, như bản Java | 84.7% | 90.2% | 0.949 |
| Vector trước | 96.6% | 95.5% | 0.976 |

7 trên 9 câu tiếng Việt từng tụt P@1 là hoà điểm RRF tuyệt đối — hạng (1, 2) và (2, 1) cho cùng
một điểm — mà hoà thì nhánh duyệt trước thắng.

## Chạy

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/python

python -m pytest
python -m eval.harness                    # BM25, không cần key, áp ngưỡng theo từng ngôn ngữ
python -m eval.harness --live             # thêm Vector + Hybrid, cần GEMINI_API_KEY
python -m eval.harness --json             # JSON, kèm nDCG@5 và câu trượt
python -m eval.harness --live --bm25-weight 0.5   # thử trọng số BM25 trong RRF
python scripts/p1_diff.py                 # câu nào Vector đúng hạng 1 mà Hybrid sai, và vì sao
```

Mã thoát: `0` đạt · `1` tụt dưới ngưỡng (recall@3 < 0.85 hoặc MRR < 0.70 ở bất kỳ ngôn ngữ
nào) · `2` dữ liệu hỏng (docId kỳ vọng không tồn tại) · `3` chế độ live có lời gọi embedding
hỏng — số đo Vector/Hybrid khi đó không dùng được.

## Đối chiếu với bản Java

Tham chiếu: `WebProject/backend/ticket-booking/src/main/java/com/booking/api/ai/`

| File này | Bản Java |
|---|---|
| `rag/normalize.py` | `rag/TextNormalizer.java` |
| `rag/synonyms.py` + `data/synonyms.yml` | `rag/SynonymExpander.java` |
| `rag/langfilter.py` | `rag/LangFilter.java` |
| `rag/bm25.py` | `rag/LexicalIndex.java` |
| `rag/store.py` | `rag/InMemoryVectorStore.java` + `VectorCodec.java` |
| `rag/fusion.py`, `rag/retriever.py` | `rag/HybridRetriever.java` |
| `rag/embed.py` | `embedding/OpenAiCompatibleEmbeddingClient.java` |
| `eval/metrics.py`, `eval/harness.py` | `test/.../RagRetrievalQualityTest.java` |

Khác biệt có chủ ý:

- Bảng đồng nghĩa là dữ liệu YAML thay vì hard-code.
- `VectorStore` ném `ValueError` khi lệch số chiều; Java âm thầm trả cosine 0.
- Client embedding sắp vector theo trường `index`, cache ra đĩa, nhúng câu hỏi theo lô trước
  khi đo, và tôn trọng `Retry-After` khi dính 429.
- `remove_accents` lọc mọi ký tự category `Mn`; Java chỉ lọc khối U+0300–U+036F. Không đổi
  token nào trên corpus hiện tại — bảng số trùng khớp ở tag `baseline` là bằng chứng.
- JSON có thêm nDCG@5; bảng giữ đúng các cột của Java để đặt cạnh nhau.

Chưa port sang Java (đã đo, đang chờ):

- Khoá đồng nghĩa viết có dấu (`"chó"`) khớp trên câu hỏi còn dấu.
- RRF duyệt nhánh Vector trước nhánh BM25.
- Hai câu hỏi vàng mới về chó.

## Dữ liệu

| File | Nguồn trong WebProject | Nội dung |
|---|---|---|
| `data/golden.yml` | `src/test/resources/rag-eval.yml` | 132 câu: vi 59 · en 37 · ja 18 · zh 18 |
| `data/kb/faq-{vi,en,ja,zh}.yml` | `src/main/resources/knowledge/` | 56 chunk mỗi ngôn ngữ |
| `data/synonyms.yml` | tách từ `SynonymExpander.java` | 4 bảng |
| `data/private/` | xuất từ Neon | gitignore — dữ liệu người dùng thật |

Khi VigoTrip đổi knowledge base hoặc bộ vàng, đồng bộ lại rồi chạy test:

```bash
W="../WebProject/backend/ticket-booking/src"
cp "$W/test/resources/rag-eval.yml" data/golden.yml
cp "$W/main/resources/knowledge/"faq-*.yml data/kb/
python -m pytest tests/test_corpus_and_metrics.py
```

Nhóm `TestCorpus` canh các bất biến của dữ liệu: docId kỳ vọng phải tồn tại, chunk kỳ vọng
phải cùng ngôn ngữ với câu hỏi, câu hỏi không được là bản chép của chunk, và mỗi ngôn ngữ
trong bộ vàng phải có ngưỡng.

Bộ câu hỏi vàng viết theo cách khách **hỏi** chứ không phải cách tài liệu **viết**: không dấu,
sai chính tả, tiếng lóng.

## Dữ liệu hội thoại thật

```bash
.venv/Scripts/python -m pip install -e ".[export]"
python scripts/export_neon.py     # đọc NEON_URL từ biến môi trường hoặc .env.neon
python scripts/stats_private.py   # chỉ in số đếm, không in nội dung
```

Nhật ký thí nghiệm: [experiments.md](experiments.md). Bài tập nền tảng: [learn/](learn/README.md).
