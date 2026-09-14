# Nhật ký thí nghiệm

Mỗi thay đổi có thể ảnh hưởng điểm số đều phải có một mục ở đây. Không ghi thì ba tuần sau
sẽ không ai nhớ vì sao cấu hình lại là thế này chứ không phải thế kia, và lại thử từ đầu.

Luật: **viết giả thuyết TRƯỚC khi chạy.** Viết sau khi thấy kết quả thì chỉ là kể lại số
liệu, không phải kiểm chứng điều gì.

---

## 2026-09-13 — Port nhánh BM25 sang Python

**Giả thuyết.** Port trung thành TextNormalizer, SynonymExpander, LangFilter và LexicalIndex
sẽ cho ra đúng bảng số của RagRetrievalQualityTest bên Java. Nếu lệch, lệch sẽ nằm ở hai chỗ
dễ khác nhau nhất giữa hai ngôn ngữ: nhận diện chữ CJK (Java có `Character.UnicodeScript`,
Python phải dùng module `regex`) và thứ tự cộng dồn điểm khi các token đồng nghĩa đổi thứ tự.

**Thay đổi.** Viết lại toàn bộ lõi truy hồi bằng Python; dữ liệu đồng bộ từ WebProject tại
`9f17f77`: 4 knowledge base × 56 chunk, 130 câu hỏi vàng.

**Kết quả.** Chạy `./mvnw test -Dtest=RagRetrievalQualityTest` (offline) làm đáp án chuẩn,
rồi `python -m eval.harness`:

| Cấu hình | Java R@3 | Python R@3 | Java MRR | Python MRR |
|---|---|---|---|---|
| BM25 · vi | 91.2% | 91.2% | 0.818 | 0.818 |
| BM25 · gộp | 93.1% | 93.1% | 0.837 | 0.837 |
| BM25 + lọc lang · vi | 94.7% | 94.7% | 0.829 | 0.829 |
| BM25 + lọc lang · gộp | 95.4% | 95.4% | 0.855 | 0.855 |

Cả 10 dòng trùng ở mọi cột. Danh sách câu trượt trùng, kể cả thứ tự top-5 của từng câu.

**Kết luận.** Baseline Python = baseline Java. Mọi thí nghiệm từ đây làm trên Python mà số vẫn
so được với production. Hai chỗ nghi ngờ lệch đều không lệch: điểm BM25 không phụ thuộc thứ
tự token (tập token đã khử trùng), còn độ lệch làm tròn khi cộng dồn nhỏ hơn khoảng cách giữa
mọi cặp điểm liền kề trên corpus này.

Chưa kiểm chứng: nhánh Vector và Hybrid. Cần `--live` với API key; mục tiêu là trùng bảng
live của Java với cùng `gemini-embedding-001` 768 chiều.

---

## 2026-09-13 — Baseline `--live` nhánh Vector / Hybrid

**Giả thuyết.** (Viết trước, ở bảng "Đã lên lịch") Nhánh Vector/Hybrid bản Python trùng bảng
live của Java với cùng `gemini-embedding-001` 768 chiều.

**Thay đổi.** Không đổi gì; chạy `python -m eval.harness --live --no-gate` với key Gemini của
WebProject. Dữ liệu trùng từng byte với WebProject tại `2ded8bf`. Tham số mặc định:
10 ứng viên mỗi nhánh, cosine ≥ 0.55.

Vận hành: 20 lời gọi API, 8 lần thử lại vì 429 (giới hạn theo phút, lần chờ dài nhất 40s),
0 lời gọi hỏng hẳn. 354 vector đã nằm trong cache, nên các lượt chạy sau không tốn lời gọi nào.

**Kết quả.**

| Cấu hình | P@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| Vector · vi | 89.5% | 98.2% | 100.0% | 0.936 |
| Vector · gộp | 84.6% | 99.2% | 100.0% | 0.913 |
| Vector + lọc lang · vi | 94.7% | 98.2% | 100.0% | 0.968 |
| Vector + lọc lang · gộp | 95.4% | 99.2% | 100.0% | 0.975 |
| Hybrid (RRF) · vi | 91.2% | 100.0% | 100.0% | 0.956 |
| Hybrid (RRF) · gộp | 93.1% | 100.0% | 100.0% | 0.964 |
| Hybrid + lọc lang · en | 94.6% | 100.0% | 100.0% | 0.973 |
| Hybrid + lọc lang · ja | 88.9% | 100.0% | 100.0% | 0.944 |
| Hybrid + lọc lang · vi | 82.5% | 100.0% | 100.0% | 0.909 |
| Hybrid + lọc lang · zh | 100.0% | 100.0% | 100.0% | 1.000 |
| Hybrid + lọc lang · gộp | 89.2% | 100.0% | 100.0% | 0.945 |

Vector và Hybrid không có câu nào trượt top-5.

**Kết luận.** Chưa kiểm được giả thuyết: không có bảng live nào của Java được lưu lại để so.
Muốn so thì chạy `RAG_EVAL_LIVE` bên WebProject rồi dán bảng vào đây.

Phát hiện đáng chú ý nhất: trên đường production (có lọc lang), RRF làm **tụt** hạng đầu so với
Vector đơn thuần. P@1 tiếng Việt giảm từ 94.7% xuống 82.5%, MRR từ 0.968 xuống 0.909, còn R@3 chỉ
tăng từ 98.2% lên 100%. Nghĩa là BM25 đang kéo chunk sai lên hạng 1 ở khoảng 7 câu tiếng Việt.
Tiếng Việt là ngôn ngữ BM25 yếu nhất và có bảng đồng nghĩa lớn nhất, nên đây là chỗ đáng nghi
đầu tiên.

---

## 2026-09-13 — Khoá đồng nghĩa `cho`

**Giả thuyết.** Khoá `cho` (chó) khớp với từ chức năng "cho" ("**cho** tôi hỏi", "vé **cho** cả
nhà") vì so khớp chạy trên token đã bỏ dấu, nên nhét "thu cung" vào những câu không liên quan
đến thú cưng. Trong bộ vàng, mọi chữ "cho" không dấu đều là từ chức năng; câu duy nhất nói về
chó ("có chó dẫn đường") viết có dấu. Trong seed_questions.yml, 34 câu có "cho" thì 1 câu nghĩa
là chó, và cũng có dấu. Dự đoán:

- Bỏ khoá: câu "cho tôi hỏi được mang bao nhiêu kg lên máy bay" vào lại top-5 ở cấu hình không
  lọc; không câu thú cưng nào tụt (poodle, cún, mèo có khoá riêng; "chó dẫn đường" khớp thẳng
  token `cho` trong chunk).
- Chỉ bật khoá khi câu hỏi gốc có "chó" có dấu: cùng kết quả với bỏ khoá trên bộ vàng, nhưng
  giữ được phần mở rộng cho câu hỏi có dấu.

Rủi ro bộ vàng không nhìn thấy: câu gõ không dấu nghĩa là chó ("mang cho len xe") mất phần mở
rộng ở cả hai biến thể.

**Thay đổi.** Chỉ đổi khoá `cho` trong bảng `vi`. Đo trên BM25 và BM25 + lọc lang; không đụng
nhánh Vector.

**Kết quả.** Hai biến thể cho số giống hệt nhau trên bộ vàng:

| Cấu hình | R@3 | R@5 | MRR |
|---|---|---|---|
| baseline · BM25 · vi | 91.2% | 98.2% | 0.818 |
| bỏ khoá / chỉ khi có dấu · BM25 · vi | 94.7% | 100.0% | 0.837 |
| baseline · BM25 · gộp | 93.1% | 98.5% | 0.837 |
| bỏ khoá / chỉ khi có dấu · BM25 · gộp | 94.6% | 99.2% | 0.846 |
| baseline · BM25 + lọc lang · vi | 94.7% | 96.5% | 0.829 |
| bỏ khoá / chỉ khi có dấu · BM25 + lọc lang · vi | 94.7% | 96.5% | 0.838 |

Ba câu đổi hạng (hạng của đáp án đúng đầu tiên, 0 = trượt top-5), không câu nào tụt:

- không lọc · "cho tôi hỏi được mang bao nhiêu kg lên máy bay": 0 → 3
- không lọc · "cho con đi một mình được không": 4 → 1
- lọc lang · "trả tiền rồi có đổi chỗ ngồi được không": 2 → 1 — va chạm thứ hai không lường
  trước: "**chỗ**" bỏ dấu cũng thành `cho`.

Tin nhắn thật (data/private, chỉ đếm): 39 tin của người dùng, 3 tin có token `cho`, không tin
nào có "chó" có dấu.

**Kết luận.** Giả thuyết đúng. Chưa áp vào synonyms.yml: nhánh Hybrid của lượt `--live` đầu tiên
cần BM25 còn khớp với Java thì mới đối chiếu được. Hai biến thể không phân biệt được trên bộ vàng.
Nếu bỏ hẳn khoá thì test `test_khop_theo_ranh_gioi_tu` hỏng ("con chó" không còn mở rộng), tức là
bỏ luôn một hành vi đang có chủ đích. Vì vậy nên chọn "chỉ khi có dấu", dù phải sửa code cả hai
bên Python và Java. Muốn tách được hai biến thể thì cần thêm vào bộ vàng câu hỏi về chó gõ không
dấu.

---

## 2026-09-14 — Áp khoá `chó`: chỉ khớp khi câu hỏi có dấu

**Giả thuyết.** Cài biến thể "chỉ khi có dấu" thành một cơ chế chung — khoá Latin viết có dấu
trong `synonyms.yml` được so trên câu hỏi CÒN dấu — sẽ tái lập đúng dòng "bỏ khoá / chỉ khi có
dấu" của mục 13/09 trên 130 câu cũ: BM25 · vi R@3 94.7%, R@5 100.0%, MRR 0.837; BM25 + lọc
lang · vi MRR 0.838. Không trùng thì là cài sai, không phải giả thuyết cũ sai.

Sau đó thêm hai câu vào bộ vàng để đo cái giá mà mục 13/09 mới chỉ nêu là rủi ro:

- "mang cho len xe khach duoc khong" → `pets-bus` (chó, gõ không dấu): mất phần mở rộng. Dự
  đoán vẫn nằm trong top-3 của BM25 + lọc lang, vì chính chunk `pets-bus` chứa "chó" và "xe
  khách"; có thể tụt từ hạng 1 xuống hạng 2.
- "chó nhà tôi đi xe khách được không" → `pets-bus` (có dấu): vẫn được mở rộng, hạng 1.

Nhánh Vector không đổi; Hybrid đổi theo BM25. Dự đoán Hybrid + lọc lang · vi không tụt câu P@1
nào so với baseline 13/09 trên 130 câu cũ.

**Thay đổi.** `rag/synonyms.py`: khoá Latin có dấu khớp theo ranh giới từ trên câu hỏi đã
thường hoá và NFC nhưng chưa bỏ dấu. `data/synonyms.yml`: `"cho"` → `"chó"`. `data/golden.yml`:
thêm hai câu trên — chỉ bên Python, bộ vàng lệch bản Java cho tới khi port.

**Kết quả.** Trên 130 câu cũ, BM25 trùng từng chữ số với dòng "bỏ khoá / chỉ khi có dấu" của
13/09: BM25 · vi R@3 94.7%, R@5 100.0%, MRR 0.837; BM25 · gộp 94.6% / 99.2% / 0.846; BM25 + lọc
lang · vi MRR 0.838. Cài đặt đúng.

Hybrid + lọc lang · vi trên 130 câu: P@1 82.5% → 84.2% (47 → 48/57), MRR 0.909 → 0.918. Vector
không đổi, 0 lời gọi API.

Hạng của `pets-bus` ở hai câu mới (lời gọi API: 1):

| Câu | BM25 + lọc lang | Vector + lọc lang | Hybrid + lọc lang |
|---|---|---|---|
| mang cho len xe khach duoc khong | 1 | 1 | 1 |
| chó nhà tôi đi xe khách được không | 1 | 1 | 1 |

Bộ vàng 132 câu: BM25 + lọc lang · vi R@3 94.9%, MRR 0.843.

**Kết luận.** Giả thuyết đúng. Câu không dấu còn tốt hơn dự đoán — hạng 1 chứ không phải 2 — vì
chính chunk `pets-bus` chứa "chó" và "xe khách", không cần mở rộng. Giữ thay đổi.

Cái giá của biến thể vẫn chưa lộ trên bộ vàng. Chỗ thiệt thật sẽ là câu gõ không dấu mà chunk
đúng KHÔNG chứa chữ "chó" — bộ vàng chưa có câu nào như vậy. BM25 bản Python giờ lệch bản Java
cho tới khi port `SynonymExpander.java` và `rag-eval.yml`.

---

## 2026-09-14 — Vì sao Hybrid + lọc lang tụt P@1 tiếng Việt

**Giả thuyết.** Đo trên bộ vàng 132 câu, đã áp khoá `chó`. Baseline 13/09: Vector + lọc lang ·
vi đúng hạng 1 ở 54/57 câu, Hybrid + lọc lang · vi chỉ 47/57. RRF cộng 1/(60 + hạng) nên các
hạng gần như ngang nhau: hạng 5 ở cả hai nhánh (2/65 ≈ 0.031) thắng hạng 1 ở một nhánh (1/61 ≈
0.016).

1. **Cơ chế.** Ở ít nhất 5/7 câu mà Vector đúng hạng 1 còn Hybrid sai, chunk sai đứng đầu có
   mặt ở CẢ hai nhánh, còn chunk đúng không có trong top-10 BM25 hoặc xếp dưới chunk sai.
2. **Đồng nghĩa.** Ở ít nhất 3 câu trong số đó, bỏ mở rộng đồng nghĩa thì BM25 không còn xếp
   chunk sai trên chunk đúng.
3. **Trọng số.** Cho nhánh BM25 trọng số w, Vector giữ 1. Với w = 0.5: vi P@1 lên ≥ 53/59 mà vi
   R@3 vẫn 100%; ba ngôn ngữ còn lại mỗi ngôn ngữ tụt không quá 1 câu P@1. Với w = 0: trùng
   đúng Vector + lọc lang — dùng để kiểm tra cài đặt.

Không đổi k = 60 trong thí nghiệm này — một biến một lần.

**Thay đổi.** `rag/fusion.py`: `rrf` nhận trọng số từng nhánh, mặc định 1 nên số cũ không đổi.
`eval/harness.py`: thêm `--bm25-weight`. `scripts/p1_diff.py`: in từng câu Vector đúng hạng 1
mà Hybrid sai, kèm hạng ở mỗi nhánh, điểm RRF và khoá đồng nghĩa đã khớp.

**Kết quả.** Baseline 132 câu, trọng số 1: Vector + lọc lang · vi đúng hạng 1 ở 56/59 (94.9%),
Hybrid + lọc lang · vi 50/59 (84.7%). `scripts/p1_diff.py` tìm ra 9 câu Vector đúng mà Hybrid
sai, và 3 câu ngược lại.

1. **Cơ chế — đúng, và rõ hơn dự đoán.** 9/9 câu có chunk sai nằm ở cả hai nhánh. Phát hiện
   không lường trước: **7/9 là hoà điểm tuyệt đối.** Chunk sai đứng hạng a ở BM25 và hạng b ở
   Vector; chunk đúng đứng hạng b ở BM25 và hạng a ở Vector — cùng 1/(60+a) + 1/(60+b). Hoà thì
   `rrf` giữ thứ tự xuất hiện đầu tiên, mà nhánh BM25 được duyệt trước, nên BM25 luôn thắng.
   Cặp hạng (a, b): (1, 2) × 5, (1, 3) × 1, (1, 6) × 1. Hai câu còn lại thua thật: "đi tàu có
   được mang vali to không" (0.0325 so với 0.0323) và "web này trả tiền bằng cách nào" (0.0323
   so với 0.0315).
2. **Đồng nghĩa — sai.** Chỉ 2/9 câu (khoá `hanh ly`, `ma vach`), dự đoán là ít nhất 3. Bảng
   đồng nghĩa không phải thủ phạm chính; luật phá hoà mới là.
3. **Trọng số — đúng.** Hybrid + lọc lang:

| Trọng số BM25 | vi P@1 | vi R@3 | vi MRR | en P@1 | ja P@1 | zh P@1 | gộp P@1 | gộp MRR |
|---|---|---|---|---|---|---|---|---|
| 1 (hiện tại) | 84.7% | 100% | 0.921 | 94.6% | 88.9% | 100% | 90.2% | 0.949 |
| 0.5 | 94.9% | 100% | 0.972 | 97.3% | 100% | 94.4% | 96.2% | 0.980 |
| 0.25 | 96.6% | 100% | 0.980 | 97.3% | 100% | 94.4% | 97.0% | 0.984 |
| 0 | 94.9% | 98.3% | 0.969 | 97.3% | 94.4% | 94.4% | 95.5% | 0.975 |

Trọng số 0 trùng từng chữ số với Vector + lọc lang — cài đặt đúng. Trọng số 0.5: vi 56/59 (dự
đoán ≥ 53), R@3 giữ 100%, zh tụt đúng 1 câu, en và ja tăng.

Chưa chọn trọng số. 0.25 hơn 0.5 đúng một câu tiếng Việt — trong mức nhiễu — và chọn trọng số
bằng chính bộ vàng là overfit, cùng lý do `bm25.py` không cho chỉnh K1, B.

**Giả thuyết 4** (viết sau khi thấy kết quả 1–3, trước khi chạy). Nếu 7/9 là hoà điểm, thì chỉ
đổi luật phá hoà — duyệt nhánh Vector trước, trọng số giữ 1 — đã lấy lại phần lớn: vi P@1 từ 50
lên 54–57/59, R@3 giữ 100%. Ba câu Hybrid đang thắng Vector có thể mất, nếu chính chúng cũng
thắng nhờ hoà. Cách này không thêm hằng số nào để chỉnh, nên ít rủi ro overfit hơn chọn trọng số.

**Kết quả 4.** Hybrid + lọc lang, trọng số 1, chỉ đổi thứ tự duyệt nhánh (0 lời gọi API):

| Thứ tự | vi P@1 | vi R@3 | vi MRR | en P@1 | ja P@1 | zh P@1 | gộp P@1 | gộp MRR |
|---|---|---|---|---|---|---|---|---|
| BM25 trước (cũ) | 84.7% | 100% | 0.921 | 94.6% | 88.9% | 100% | 90.2% | 0.949 |
| Vector trước | 96.6% | 100% | 0.980 | 91.9% | 94.4% | 100% | 95.5% | 0.976 |

Câu đổi kết quả hạng 1: đúng 7 câu hoà điểm ở mục 1 chuyển sang đúng, thêm một câu tiếng Nhật
("ログインできずパスワードが分かりません"); một câu tiếng Anh chuyển sang sai ("i want to cancel and
get my money back"). Không câu nào trong ba câu Hybrid đang thắng Vector bị mất. Giả thuyết 4
đúng: 57/59, đầu trên của khoảng dự đoán.

**Kết luận.** Áp "Vector trước" vào `HybridRetriever`, giữ trọng số 1. Chọn nó thay vì trọng số
0.5 hay 0.25 vì:

- Không có hằng số nào được chỉnh theo bộ vàng. Luật phá hoà có lý do riêng, không cần bộ vàng
  chống lưng: đứng riêng, Vector + lọc lang đúng hạng 1 ở 95.5% câu, BM25 + lọc lang chỉ 76.5%.
  Hoà thì nghe nhánh mạnh hơn.
- Khoảng cách với trọng số 0.5 (gộp P@1 96.2% so với 95.5%) là 1 câu trên 132 — trong mức nhiễu.
- Khi embedding hỏng, nhánh Vector rỗng, không có hoà — luật này không đổi gì ở đường lui BM25.

Đổi ý nếu: bộ vàng lớn hơn cho thấy trọng số < 1 hơn "Vector trước" nhiều hơn vài câu. Trọng số
vẫn giữ trong `rrf` và `--bm25-weight` để đo lại khi đó.

Còn mở: hai câu thua RRF thật (mục 1) và câu tiếng Anh vừa chuyển sang sai.

**Port sang Java (14/09).** Khoá `chó` có dấu vào `SynonymExpander.java`, "Vector trước" vào
`HybridRetriever.fuse`, hai câu chó vào `rag-eval.yml`, kèm test cho từng thay đổi. Bảng BM25 của
`RagRetrievalQualityTest` trùng bản Python từng chữ số cả 10 dòng trên 132 câu.

**Bảng live bên Java (14/09).** Lần chạy đầu hỏng: `CachingEmbeddingClient` thử lại cả 224 chunk
một lượt, delegate bắn 7 lô 32 liền nhau, vượt 100 request/phút, và mỗi lần thử gửi lại từ lô đầu
— hỏng cả 4 lần. Sửa trong test (không đụng production): chia lô 32, mỗi lô tự thử lại, lô xong nằm
trong cache, giống `embed_all` bên Python. Lần chạy lại: 139 lời gọi, 3 lần thử lại vì 429, 0 lời
gọi hỏng.

Đối chiếu với `python -m eval.harness --live` chạy lại cùng ngày từ cache (0 lời gọi API): cả 20
dòng Vector / Vector + lọc lang / Hybrid / Hybrid + lọc lang, theo từng ngôn ngữ lẫn gộp, trùng
từng chữ số ở cả 6 cột. Cộng 10 dòng BM25, bản Python và bản Java cho cùng 30 dòng trên 132 câu.
Đường production (Hybrid + lọc lang) tiếng Việt: P@1 84.7% → 96.6%, R@3 100%, MRR 0.921 → 0.980.

---

## 2026-09-14 — Bộ holdout tiếng Việt

**Vì sao.** Luật "Vector trước" được chọn sau khi nhìn kết quả trên chính 59 câu vi của
`golden.yml`. Số 96.6% có thể lạc quan vì chọn trên cùng bộ đo. `data/holdout.yml` — 55 câu vi,
một câu mỗi chunk trừ `pets-bus` — chỉ chạy để xác nhận, không để chọn cấu hình.

**Cách viết.** Câu hỏi viết khi chỉ nhìn docId và title, gán expected sau khi đọc content. Khoảng
1/3 không dấu hoặc viết tắt. Không câu nào trùng `golden.yml` (so sau khi bỏ dấu) hay chép nguyên
văn chunk. Còn thiếu phần người thật gõ.

**Giả thuyết** (viết trước khi chạy). Holdout khó hơn golden: phân bố đều mọi chunk thay vì dồn
vào chủ đề hay hỏi, và câu viết lệch từ với chunk có chủ đích.

- Hybrid + lọc lang · vi: P@1 thấp hơn golden (96.6%) nhưng vẫn trong khoảng 85–95% (47–52/55),
  R@3 ≥ 95%. Dưới 85% thì 96.6% trên golden là lạc quan thật, và luật "Vector trước" cần xem lại
  trên bộ lớn hơn — nhưng KHÔNG chỉnh trên holdout.
- BM25 + lọc lang · vi: P@1 60–75% (golden 74.6%). Câu không dấu và câu né từ của chunk là chỗ
  BM25 thua.
- Khoảng cách Hybrid − BM25 trên holdout lớn hơn trên golden (22 điểm), vì holdout ít trùng từ hơn.

**Kết quả BM25** (offline, 0 lời gọi API):

| Cấu hình · vi | Câu | P@1 | R@3 | MRR |
|---|---|---|---|---|
| BM25 · golden | 59 | 72.9% | 94.9% | 0.842 |
| BM25 · holdout | 55 | 52.7% | 83.6% | 0.668 |
| BM25 + lọc lang · golden | 59 | 74.6% | 94.9% | 0.843 |
| BM25 + lọc lang · holdout | 55 | 61.8% | 81.8% | 0.726 |

BM25 + lọc lang P@1 61.8% nằm trong khoảng dự đoán 60–75%, sát đầu dưới. R@3 81.8% thấp hơn cổng
0.85 — holdout chạy với `--no-gate`, cổng chỉ áp cho golden.

7 câu trượt khỏi top-5 (BM25 + lọc lang), ghi lại để hiểu, KHÔNG để sửa trên holdout:

- Không dấu, không có từ nào chung với chunk: "toi ngu quen xe chay mat roi gio sao",
  "co tra bang momo duoc khong" (KB không nhắc MoMo), "con 7 tuoi duoc giam gia bao nhieu"
  (chunk nói "75 phần trăm", không nói "giảm giá").
- Có dấu nhưng né từ của chunk: "hủy vé 5 hôm rồi chưa thấy tiền về" (từ "hủy" kéo về nhóm
  cancel), "tài xế chạy ẩu muốn phản ánh" (chunk viết "khiếu nại"), "nhà xe báo lùi giờ…" (chunk
  viết "hoãn"), "thùng xốp đựng đồ ăn" (chunk viết "hàng hóa kích thước lớn").

Đây đúng loại câu mà nhánh Vector sinh ra để bắt.

**Kết quả live** (2 lời gọi API, 0 lần 429, 0 lời gọi hỏng):

| Cấu hình · vi | golden P@1 | holdout P@1 | holdout R@3 | holdout MRR |
|---|---|---|---|---|
| BM25 + lọc lang | 74.6% | 61.8% | 81.8% | 0.726 |
| Vector | 89.8% | 92.7% | 98.2% | 0.948 |
| Vector + lọc lang | 94.9% | **94.5%** | 98.2% | **0.961** |
| Hybrid (RRF) | 96.6% | 85.5% | 96.4% | 0.905 |
| Hybrid + lọc lang (production) | 96.6% | **80.0%** | 92.7% | 0.864 |

**Giả thuyết 1 SAI.** Hybrid + lọc lang 80.0% (44/55), dưới khoảng dự đoán 85–95%. Vector + lọc
lang gần như giữ nguyên giữa hai bộ (94.9% → 94.5%), còn Hybrid tụt 16.6 điểm. Giả thuyết 2 đúng
(BM25 61.8%). Giả thuyết 3 đúng theo hướng cực đoan: trên holdout, Hybrid không những thua Vector
mà còn thua Vector 8 câu, thắng 0 câu.

**Chẩn đoán** — `scripts/p1_diff.py --golden data/holdout.yml`, 0 lời gọi API. 8 câu Vector đúng
hạng 1 mà Hybrid sai; 0 câu do đồng nghĩa; 0 câu do hoà điểm (luật "Vector trước" không liên
quan). Cả 8 cùng một cơ chế: chunk sai có mặt ở CẢ HAI nhánh thắng chunk đúng chỉ mạnh ở một nhánh.

- 3 câu chunk đúng vắng hẳn khỏi top-10 BM25, nên chỉ được 1/61 ≈ 0.0164. Bất kỳ chunk nào lọt cả
  hai top-10 — kể cả hạng 6 + 6 ("momo" → `support-contact`) hay 3 + 9 ("phản ánh" →
  `payment-double-charge`) — đều vượt qua: "co tra bang momo duoc khong", "tài xế chạy ẩu muốn
  phản ánh", "hủy vé 5 hôm rồi chưa thấy tiền về".
- 5 câu sát nút: chunk sai (BM25 hạng 1, Vector hạng 2) = 0.0325 thắng chunk đúng (BM25 hạng 3–7,
  Vector hạng 1) = 0.0313–0.0323. BM25 bắt được từ chung ("tuổi", "mail", "giờ") nhưng xếp nhầm
  chunk anh em cùng chủ đề lên đầu.

Vì sao golden không lộ ra: câu golden viết gần từ của chunk hơn, nên BM25 thường cũng đúng và hai
nhánh đồng thuận. RRF chỉ có lợi khi hai nhánh ngang sức; khi một nhánh (BM25 ở đây) kém hẳn, nó
kéo nhánh mạnh xuống.

**Kết luận.** Số 96.6% của Hybrid + lọc lang trên golden là lạc quan: trên câu chưa dùng để chọn,
đường production đúng hạng 1 ở 80.0% câu, trong khi Vector + lọc lang đạt 94.5%. Khoảng cách 8/55
câu vượt xa mức nhiễu một hai câu. Không đổi gì trong hệ thống dựa trên holdout — mọi phương án
sửa phải chọn trên golden (hoặc một bộ thứ ba), rồi quay lại holdout đúng MỘT lần để xác nhận.
Cũng chưa port gì sang VigoTrip.

Đổi ý nếu: phần câu người thật gõ, khi thêm vào, cho thấy Hybrid hơn Vector — tức là câu Claude
viết lệch về phía né từ nhiều hơn khách thật.

---

## 2026-09-14 — Hybrid có đáng giữ không

**Bối cảnh.** Hybrid (RRF) vẫn đang chạy ở cả vi-rag-eval lẫn VigoTrip — chưa đổi gì. Câu hỏi đặt
ra từ holdout: trên câu chưa dùng để chọn, Hybrid + lọc lang 80.0%, Vector + lọc lang 94.5%.

**Dữ liệu.** Người thật gõ 126 câu: 49 câu trả lời được bằng KB thêm vào holdout (có nhãn), 77 câu
KB không trả lời được tách sang `data/unanswerable.yml` cho tuần 9 và 12. 49 câu này CHƯA chạy lần
nào; 55 câu Claude viết đã chạy một lần nên chỉ báo cáo kèm.

**Phương án.** Tất cả đều lùi về BM25 thuần khi embedding hỏng — BM25 vẫn là đường lui, chỉ đổi
cách ghép khi cả hai nhánh cùng có kết quả.

| | Cách ghép | Cờ |
|---|---|---|
| A | RRF hiện tại | mặc định |
| B | RRF trọng số BM25 0.5 | `--bm25-weight 0.5` |
| C | Xếp lại: BM25 chỉ xếp lại chunk đã có trong top-10 Vector | `--variants` |
| D | Bù BM25: giữ thứ tự Vector, BM25 chỉ lấp chỗ trống | `--variants` |

**Tiêu chí chọn** (viết trước khi chạy). Chọn trên `golden.yml`, 132 câu, theo P@1 gộp của đường
production (+ lọc lang). Mặc định chọn D — ít cơ chế nhất mà vẫn có đường lui. Chỉ chọn A, B hoặc C
nếu hơn D từ 3 câu P@1 gộp trở lên VÀ R@3 gộp không thấp hơn. Không chọn trọng số khác 0.5 — lý do
như mục P@1 ở trên. Sau khi chọn, chạy phần người thật gõ đúng một lần để xác nhận.

**Dự đoán.**

- Golden: A và D chênh không quá 2 câu gộp (bảng live đã có Vector + lọc lang = Hybrid + lọc lang
  = 95.5% gộp). B và C nằm giữa A và D. → Theo tiêu chí, chọn D.
- 49 câu người thật: D hơn A từ 3 câu P@1 trở lên. Nếu A ≥ D thì kết quả trên 55 câu Claude viết
  là do cách viết né từ, và nên giữ A.
- Không đo được bằng bộ này: BM25 mạnh ở mã voucher, số hiệu chuyến — golden gần như không có loại
  câu đó, nên D có thể thua ở chỗ bộ đo không nhìn thấy.

**Kết quả chọn — golden** (0 lời gọi API, đường production + lọc lang):

| | Cách ghép | vi P@1 | en P@1 | ja P@1 | zh P@1 | gộp P@1 | gộp R@3 | gộp MRR |
|---|---|---|---|---|---|---|---|---|
| A | RRF | 96.6% | 91.9% | 94.4% | 100% | 95.5% (126) | 100% | 0.976 |
| B | RRF, BM25 0.5 | 94.9% | 97.3% | 100% | 94.4% | 96.2% (127) | 100% | 0.980 |
| C | Xếp lại | 93.2% | 91.9% | 100% | 94.4% | 93.9% (124) | 100% | 0.968 |
| D | Bù BM25 | 94.9% | 97.3% | 94.4% | 94.4% | 95.5% (126) | 99.2% | 0.975 |

D trùng từng chữ số với Vector + lọc lang: trên golden nhánh Vector không lần nào trả thiếu 5
chunk, nên BM25 chưa phải lấp chỗ nào. Dự đoán "A và D chênh ≤ 2 câu" đúng (0 câu). Dự đoán "B, C
nằm giữa" sai: B hơn cả hai 1 câu, C thua cả hai 2 câu.

**Chọn D** theo tiêu chí: không phương án nào hơn D từ 3 câu. Ghi rõ cái giá: R@3 gộp của D thấp
hơn A và B một câu (99.2% so với 100%) — tiêu chí không đặt điều kiện R@3 cho D, nên không đổi kết
quả chọn, nhưng đó là chỗ BM25 đang giúp thật.

Viết trước khi chạy xác nhận: D sẽ hơn A từ 3/49 câu P@1 trên phần người thật gõ.

**Kết quả xác nhận — holdout, chạy một lần** (2 lời gọi API, 0 lần 429, 0 lời gọi hỏng):

| · vi, + lọc lang | Người thật gõ (49) P@1 | R@3 | MRR | Claude viết (55, lần 2) P@1 | R@3 |
|---|---|---|---|---|---|
| BM25 | 38.8% | 71.4% | 0.548 | 61.8% | 81.8% |
| A · RRF | 63.3% (31) | 81.6% | 0.736 | 80.0% | 92.7% |
| C · Xếp lại | 65.3% (32) | 83.7% | 0.756 | 81.8% | 92.7% |
| D · Bù BM25 | **73.5% (36)** | **95.9%** | **0.838** | **94.5%** | 98.2% |

Dự đoán đúng: D hơn A 5/49 câu P@1, và R@3 hơn 14.3 điểm. Điều kiện đổi ý ("người thật gõ mà A
≥ D thì do Claude viết né từ") không xảy ra — câu người thật gõ còn né từ của chunk nhiều hơn: BM25
chỉ đúng hạng 1 ở 38.8%, thấp hơn cả phần Claude viết. Trên cả hai phần, D trùng từng chữ số với
Vector + lọc lang.

P@1 tuyệt đối 73.5% thấp hơn hẳn phần Claude viết. Một phần do câu người thật gõ dồn nhiều ý hoặc
mơ hồ ("mua ve xe di hai phong", "thời tiết có ảnh hưởng giá vé hay chỉ delay"), một phần do nhãn
là phán đoán của Claude — chưa tách được hai nguyên nhân. R@3 95.9% cho thấy chunk đúng gần như luôn
có mặt trong ngữ cảnh gửi cho LLM.

**Kết luận.** Giữ BM25, bỏ RRF. BM25 vẫn là đường lui khi embedding hỏng và vẫn lấp chỗ khi Vector
trả thiếu, nhưng không còn được đẩy chunk lên trên chunk mà Vector xếp đầu. Trên golden hai cách
ngang nhau (126/132); trên câu chưa dùng để chọn, D hơn A 5/49 (người thật) và 8/55 (Claude viết).

Chưa đổi mặc định của `HybridRetriever` (vẫn `rrf`, để bảng 20 dòng còn so thẳng với Java), chưa
port sang VigoTrip.

Đổi ý nếu: một bộ câu hỏi có mã voucher, số hiệu chuyến, mã đơn hàng cho thấy D thua A — đó là chỗ
BM25 mạnh mà cả golden lẫn holdout gần như không có.

---

## 2026-09-14 — Câu có mã: Bù BM25 có thua RRF không

**Kiểm tra trước.** Knowledge base 4 ngôn ngữ và bản export production không chứa mã nào; 39 câu thật
không câu nào gõ mã voucher hay mã đơn. Lợi thế "BM25 bắt mã" không tồn tại với corpus này: mã trong
câu hỏi không khớp chữ nào của chunk. Câu hỏi đổi thành: mã lạ có làm nhiễu nhánh nào không.

**Cách tokenizer xử lý mã** (hành vi hệ thống, xem trước khi chạy): số một chữ số bị bỏ ("SE1" →
`se`, "1tr8" → `tr`), chữ và số tách nhau ("VIGO50" → `vigo`, `50`). Trong KB tiếng Việt, `se` có
11 lần (từ "sẽ"), `ma` 36 lần (từ "mã"), `12` 5 lần ("12 tuổi"), `20` 4 lần ("20kg").

**Dữ liệu.** `data/holdout_codes.yml` — 32 câu vi, Claude viết theo văn phong câu người thật gõ, trước
khi xem tokenizer. Mã đều bịa. Không dùng để chọn, chỉ để chặn.

**Giả thuyết** (viết trước khi chạy).

- BM25 + lọc lang tệ hơn trên holdout thường: mảnh mã như `se`, `12`, `20` khớp nhầm chunk không
  liên quan. P@1 dưới 60%.
- Vector gần như không bị mã làm nhiễu: câu vẫn còn đủ từ mang nghĩa ("hoãn", "quét", "trừ tiền").
  Vector + lọc lang P@1 ≥ 80%.
- D không thua A: D − A ≥ 0 câu P@1. **Tiêu chí chặn:** A hơn D từ 3/32 câu P@1 thì chưa port D.

**Kết quả** (1 lời gọi API, 0 lần 429, 0 lời gọi hỏng; · vi + lọc lang):

| Cấu hình | P@1 | R@3 | MRR |
|---|---|---|---|
| BM25 | 50.0% (16) | 65.6% | 0.600 |
| Vector | 87.5% (28) | 96.9% | 0.911 |
| A · RRF | 81.2% (26) | 90.6% | 0.867 |
| C · Xếp lại | 84.4% (27) | 90.6% | 0.883 |
| D · Bù BM25 | **90.6% (29)** | **100%** | **0.943** |

Ba giả thuyết đều đúng: BM25 50.0% (< 60%), Vector 87.5% (≥ 80%), D hơn A 3 câu. Không chạm tiêu chí
chặn.

Trong 6 câu BM25 trượt khỏi top-5, mảnh mã và con số kéo BM25 đi lạc: "t đặt 3 vé chuyến SE5…" →
`payment-failed` đứng đầu, "HN-SG 8h30 … hủy trước 1 ngày" → `checkin-arrive-early` đứng đầu. RRF
mang một phần nhiễu đó vào: A trượt 2 câu khỏi top-5, D không trượt câu nào.

Lần đầu tiên D khác Vector thuần: hơn 1 câu P@1 và 3.1 điểm R@3. Có câu Vector trả thiếu vì ngưỡng
cosine 0.55, BM25 lấp vào và trúng — phần "bù" có việc thật, không chỉ là đường lui.

Ở VigoTrip, mã voucher thật không đi qua RAG: `ChatService` có tool `check_voucher` (kiểm tra mã
qua `VoucherService`), `save_voucher` và `search_trips`. RAG chỉ lo phần chính sách xung quanh mã,
đúng phần bộ này đo.

**Kết luận.** Không có bằng chứng BM25 cần được xếp ngang Vector cho câu có mã; ngược lại, RRF để
mảnh mã làm nhiễu. Không chặn việc port Bù BM25.

Giới hạn: 32 câu, Claude viết, mã bịa. KB không có mã nên bộ này không đo được trường hợp chunk
chứa mã thật — nếu sau này KB thêm bảng mã tuyến, số hiệu tàu hay danh sách voucher thì phải đo lại.

---

## Mẫu

### YYYY-MM-DD — tên ngắn gọn

**Giả thuyết.** Điều bạn tin là đúng, và vì sao.

**Thay đổi.** Chính xác cái gì đổi. Một biến một lần.

**Kết quả.**

| Cấu hình | R@3 | MRR | p50 (ms) |
|---|---|---|---|
| baseline | | | |
| thử nghiệm | | | |

**Kết luận.** Giữ hay bỏ, và vì sao. Nếu bỏ thì ghi rõ điều kiện nào sẽ khiến đổi ý.

---

## Đã lên lịch

| Thí nghiệm | Câu hỏi cần trả lời |
|---|---|
| Port Bù BM25 sang VigoTrip | `HybridRetriever.fuse` bên Java, kèm đổi mặc định bên Python. Bảng Java/Python phải trùng lại sau khi port. Hỏi trước khi sửa |
| P@1 73.5% trên câu người thật gõ | 13 câu sai hạng 1: do câu dồn nhiều ý, do nhãn, hay do truy hồi. Chỉ để hiểu — không chỉnh trên holdout |
| Hai câu thua RRF thật, một câu en mới sai | "đi tàu có được mang vali to không" (`pets-train` chen lên nhờ khoá `vali`?), "web này trả tiền bằng cách nào", "i want to cancel and get my money back". Mỗi câu: chunk nào chen lên, vì sao |
| Cái giá thật của khoá có dấu | Thêm vào bộ vàng câu gõ không dấu mà chunk đúng KHÔNG chứa chữ "chó", để đo phần mở rộng bị mất |
| Hai câu vi trượt khi lọc lang | "bao lâu thì tiền về tài khoản" → refund-processing-time, "web này trả tiền bằng cách nào" → payment-methods. Khoảng trống từ vựng hay do chunk viết khác cách hỏi |
| Cross-encoder rerank trên top-20 | Delta R@3 có đáng với delta độ trễ không — đặt ngân sách độ trễ TRƯỚC khi đo |
| Chunk size, overlap, title trong phần đem nhúng | Cấu hình nào cho R@3 cao nhất, trả giá bao nhiêu độ trễ |
| nDCG@5 | Có xếp lại thứ tự ưu tiên sửa lỗi so với recall@3 không |
| Tách điểm theo category | Category nào yếu nhất, và vì sao |
