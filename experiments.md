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

**Port sang Java (14/09).** `HybridRetriever.fuse` bỏ RRF, thay bằng Vector trước rồi BM25 lấp chỗ
trống — cùng thuật toán với `_fill` bên Python. `rag.rrf-k` bị bỏ khỏi `RagProperties` và
`application.yml` vì không còn chỗ dùng. Bên Python, mặc định của `HybridRetriever` đổi từ `rrf`
sang `vector_fill`; `rrf` và `vector_rerank` giữ lại để đo, `--variants` giờ in hai dòng đó.
Dòng "Hybrid (RRF)" đổi tên thành "Hybrid" ở cả hai bảng. `scripts/p1_diff.py` ghim `fusion="rrf"`,
vì với Bù BM25 câu trả lời của nó luôn là 0.

Test Java: bỏ "hoà điểm RRF thì nghe Vector", thêm hai test — BM25 chỉ lấp chỗ trống và không
lặp chunk; chunk có mặt ở cả hai nhánh (BM25 hạng 1, Vector hạng 2) KHÔNG vượt được chunk Vector
xếp hạng 1 — đúng cơ chế của 8 câu holdout.

Đây không phải "tăng trọng số cho Vector". Tăng trọng số là phương án B (RRF, BM25 0.5): BM25
vẫn cộng điểm và vẫn có thể đẩy một chunk lên trên chunk Vector xếp. Bù BM25 không cộng điểm nào
— thứ tự là tuyệt đối. BM25 còn đúng hai việc: đường lui khi nhánh Vector rỗng, và lấp chỗ khi
Vector trả chưa đủ top-k vì ngưỡng cosine 0.55.

---

## 2026-09-14 — Lỗi nằm ở đâu: tách theo category

**Vì sao.** Sau khi đổi sang Bù BM25, đường production vẫn sai hạng 1 ở 6/132 câu vàng và 16/104
câu holdout tiếng Việt (3/55 Claude viết, 13/49 người thật gõ). Trước khi thử reranker hay bất kỳ
tầng nào, cần biết lỗi dồn vào đâu. Đây là đo để hiểu, KHÔNG đổi hệ thống — holdout được phép
nhìn ở mức này, không được dùng để chỉnh.

**Cách đo.** `scripts/by_category.py`, chỉ đọc vector từ cache (0 lời gọi API; client không có
key nên thiếu cache là báo lỗi chứ không gọi mạng). Category của câu = category của chunk đúng đầu
tiên. Mỗi câu sai hạng 1 được gắn nhãn máy: trượt top-5 / nhầm chunk cùng category / nhầm sang
category khác, và hạng 1 do Vector hay do BM25 lấp. Nhóm nguyên nhân (câu dồn nhiều ý, nhãn gây
tranh cãi, truy hồi thật sự sai) gán tay sau khi đọc từng câu.

**Giả thuyết** (viết trước khi chạy).

- Bộ vàng quá ít lỗi để xếp hạng category: Hybrid + lọc lang không category nào sai quá 2 câu. Bảng
  category trên bộ vàng chủ yếu cho thấy BM25 yếu ở đâu — dự đoán BAGGAGE và BOOKING (mỗi loại 6
  chunk tiếng Việt, từ vựng chồng nhau) có P@1 BM25 thấp nhất.
- Holdout vi, 16 câu sai hạng 1: quá nửa (≥ 9) là nhầm sang chunk anh em CÙNG category, không phải
  bốc sang chủ đề khác. Hạng 1 sai gần như luôn do Vector (BM25 chỉ lấp khi Vector trả thiếu).
- Ít nhất 4/13 câu người thật gõ sai hạng 1 là do câu dồn nhiều ý hoặc nhãn gây tranh cãi, không
  phải truy hồi sai — nghĩa là 73.5% đánh giá thấp hệ thống.
- nDCG@5 xếp category giống MRR: rất ít câu có hơn một chunk đúng.

**Kết quả** (0 lời gọi API; Hybrid = Bù BM25, + lọc lang):

| Bộ | Câu | BM25 P@1 | Hybrid P@1 | Sai hạng 1 | Category Hybrid yếu nhất |
|---|---|---|---|---|---|
| golden, 4 ngôn ngữ | 132 | 76.5% | 95.5% | 6 | CHECKIN 7/9, CANCEL 10/12 |
| holdout vi | 104 | 51.0% | 84.6% | 16 | REFUND 5/9, ACCOUNT 5/7, BOOKING 8/11 |
| holdout_codes vi | 32 | 50.0% | 90.6% | 3 | REFUND 1/2, TRIP 2/3, CHECKIN 2/3 |

Cả 25 câu sai hạng 1, hạng 1 đều do nhánh Vector xếp — BM25 lấp chỗ không gây ra lỗi nào. 2 câu
trượt hẳn top-5, cả hai ở holdout.

**Nhóm nguyên nhân** (gán tay sau khi đọc chunk; 25 câu gộp cả ba bộ):

| Nhóm | Câu | Ví dụ | Cơ chế |
|---|---|---|---|
| Hủy vé ↔ hoàn tiền | 7 | "Sau khi hủy vé, tôi nhận hoàn tiền bằng hình thức nào?" → `cancel-how-to` | Câu có "hủy" + "tiền"; `cancel-how-to`, `cancel-policy-refund-tiers`, `refund-partial` đều nói "hoàn", Vector không tách được "hủy thế nào" với "tiền về ra sao". Có ở cả ba bộ (golden 2, holdout 4, có mã 1) |
| Câu mơ hồ hoặc nhãn gián tiếp | 5 | "nó bắt t đăng nhập mới xem được à?", "pass 1 cặp vé cho người khác" | 3 câu dồn ý, chửi, hoặc cần lượt chat trước; 2 câu đổi tên người đi mà KB chỉ trả lời bằng một mệnh đề phụ trong `account-change-info`. Toàn bộ là câu người thật gõ |
| Không dấu đọc thành từ khác | 4 | "toi ngu quen xe chay mat" → `account-forgot-password` ("quen" → "quên") | Bỏ dấu làm câu trùng nghĩa với chunk khác: hộp thư, quét vé, đưa gì cho nhân viên |
| Con số | 4 | "Con tôi 3 tuổi đi cùng tôi có cần vé không?" → `children-infant-free` | Vector không so được khoảng tuổi (3 tuổi so với "dưới 2" và "2 đến 12"); "1tr8 / 1tr2" kéo về `payment-double-charge` |
| Lệch nghĩa khác | 5 | "mang dao lên máy bay" → `pets-plane`; "xe đến trễ 2 tiếng" → `cancel-missed-trip` | Từ nổi bật kéo sai chủ đề: "máy bay", "trễ" (xe trễ bị hiểu thành khách trễ), "báo lỗi" → voucher |

**Đối chiếu giả thuyết.**

- Bộ vàng không category nào sai quá 2 câu — **đúng** (CHECKIN 2, CANCEL 2). BM25 yếu nhất ở
  BAGGAGE và BOOKING — **sai**: thấp nhất là CHILDREN 40.0% (con số tuổi), PROMO 62.5%, rồi mới tới
  BAGGAGE 63.2%; BOOKING 75.0% ở giữa bảng.
- Holdout: ≥ 9/16 là nhầm chunk cùng category — **sai**: nhãn máy chỉ 4/16; kể cả gộp CANCEL với
  REFUND làm một chủ đề cũng mới 7/16. Hạng 1 sai gần như luôn do Vector — **đúng**, 16/16.
- ≥ 4/13 câu người thật gõ sai do câu mơ hồ hoặc nhãn — **đúng**, 5/13. Bỏ 5 câu đó thì 36/44 =
  81.8%, nhưng không nên coi đó là "số thật": khách thật vẫn gõ đúng những câu như vậy, bot vẫn phải
  xử lý — việc của tuần 9 (hỏi lại, từ chối đúng lúc), không phải của truy hồi.
- nDCG@5 xếp giống MRR — **đúng ở đầu bảng**: ba category yếu nhất trên holdout giống nhau theo cả
  hai (REFUND, ACCOUNT, BOOKING); giữa bảng đổi chỗ một hai bậc. nDCG@5 không đổi thứ tự ưu tiên sửa.

**Kết luận.** Nguyên nhân lớn nhất có tên là cặp hủy vé ↔ hoàn tiền: 7/25 câu sai, có mặt ở cả
ba bộ, kể cả bộ vàng — nên đây là chỗ DUY NHẤT trong bảng có thể chọn cách sửa trên golden rồi xác
nhận trên holdout. Hai nhóm tiếp theo (không dấu, con số) mỗi nhóm 4 câu, rải rác, chưa đủ để chọn.
Nhóm câu mơ hồ không sửa ở truy hồi.

Không đổi gì trong hệ thống. Ghi chú cho reranker (tuần 7): cross-encoder đọc cả câu hỏi lẫn chunk
cùng lúc, nên về lý thuyết hợp đúng nhóm hủy ↔ hoàn tiền và con số — hai nhóm mà cosine giữa hai
vector nén sẵn không tách được. Nhưng golden chỉ có 3 câu thuộc hai nhóm đó; muốn chọn trên golden
thì phải thêm câu vào golden trước, rồi mới đo.

Giới hạn: gán nhóm là phán đoán một người (Claude), mỗi câu một nhóm dù có câu dính hai. Hai câu
"Sau khi hủy vé…" gần như trùng nhau, nên nhóm hủy ↔ hoàn tiền được đếm hơi cao.

---

## 2026-09-14 — Reranker: không dùng, không đo

**Quyết định** (của người điều hướng, chốt trước khi đo). Ba nguyên nhân lớn nhất trong 25 câu sai
hạng 1: hủy vé ↔ hoàn tiền 7 câu (28%), không dấu và con số 8 câu (32%), câu mơ hồ hoặc khách gõ tắt
5 câu (20%). Cross-encoder rerank top-20 ước lượng nâng P@1 tối đa khoảng 5–7 điểm, đổi lấy +150 đến
+300 ms p95 mỗi tin nhắn. R@3 đã khoảng 99% trên bộ vàng, tức chunk đúng gần như luôn nằm trong ngữ
cảnh LLM đọc — sai hạng 1 chỉ là sai thứ tự trong prompt. Nên KHÔNG thêm tầng rerank; ưu tiên để LLM
đọc đúng các chunk đã có.

**Lưu ý khi đọc quyết định.** Cả 5–7 điểm lẫn +150–300 ms là ước lượng, CHƯA đo trên máy này.
Production nhét top-4 chứ không phải top-3 (`rag.top-k: 4`). R@3 trên holdout vi thấp hơn bộ vàng,
nên "chunk đúng gần như luôn có mặt" đúng với bộ vàng hơn là với câu khách thật gõ.

**Điều kiện đổi ý.** Tuần 9 cho thấy câu trả lời bịa hoặc từ chối thừa mà nguyên nhân là chunk đúng
KHÔNG có trong top-4 — lỗi đó prompt không sửa được, phải quay lại truy hồi.

---

## 2026-09-14 — Tầng sinh có bịa không (tuần 9)

**Vì sao.** Retrieval đúng chưa đủ: khách đọc câu trả lời, không đọc chunk. Cần biết chatbot có nói
điều ngoài tài liệu không, và có một judge đủ tin để sau này đo tự động (tuần 10 dùng lại).

**Cách đo.** `scripts/faithfulness.py`. Sinh: prompt VigoTrip chép nguyên văn (bỏ khối tool, voucher,
link — xem `rag/generate.py`), `gemini-flash-lite-latest`, temperature 0.7, 800 token, top-4 Hybrid +
lọc lang. 30 câu: 15 câu vi ngẫu nhiên từ golden (seed 9) và 15 câu từ `unanswerable.yml` rải theo
loại (kb_khong_co 4, ngoai_le 2, injection 2, can_ngu_canh 2, còn lại mỗi loại 1). Người chấm tay 4
nhãn (có căn cứ / bịa / từ chối đúng / từ chối thừa) TRƯỚC, rồi judge Groq `gpt-oss-120b`,
temperature 0, khác họ model với bên sinh.

**Giả thuyết** (viết trước khi sinh câu trả lời nào).

- 15 câu golden: ≥ 12 có căn cứ. Câu bịa hoặc từ chối thừa rơi vào câu mà chunk đúng không ở hạng 1
  hoặc không có trong top-4.
- 15 câu không trả lời được: ≥ 3 câu bịa, dồn ở kb_khong_co (bà bầu, sinh viên, người cao tuổi —
  model lấy chính sách hãng ngoài đời ra nói) và can_tool (không có tool nên dễ bịa giờ chuyến).
  Injection và đe doạ: từ chối đúng cả.
- Judge cùng nhãn với chấm tay ≥ 80%; cùng ý "có bịa hay không" ≥ 90%. Lệch chủ yếu giữa có căn cứ
  và bịa ở câu "suy ra" từ tài liệu (judge khắt hơn người).

**Kết quả** (chấm tay 15/09; judge rubric v1, `reasoning_effort: low`):

| Bộ, người chấm | Có căn cứ | Bịa | Từ chối đúng | Từ chối thừa |
|---|---|---|---|---|
| golden, tay | 14 | 1 | 0 | 0 |
| golden, judge | 13 | 1 | 1 | 0 |
| không trả lời được, tay | 1 | 0 | 14 | 0 |
| không trả lời được, judge | 2 | 0 | 13 | 0 |

Judge cùng nhãn 27/30 = 90%, cùng ý có bịa 28/30 = 93% — nhưng bắt được **0/1** câu bịa thật và báo
bịa giả 1 câu. Độ trễ sinh p50 1125 ms, p95 1663 ms.

**Đối chiếu giả thuyết.**

- Golden ≥ 12/15 có căn cứ — **đúng**, 14/15. Câu bịa duy nhất (g12 "len xe thi dua gi cho nhan
  vien") đúng là câu mà chunk đúng `checkin-qr-usage` vắng khỏi top-4: bot đọc 4 chunk hành lý rồi
  tự nói "xuất trình vé giấy hoặc vé điện tử và giấy tờ tùy thân" — trái cả chunk thật ("Không cần
  in vé giấy").
- Không trả lời được ≥ 3 câu bịa — **sai**, 0/15. Nguyên tắc "chỉ nói điều có căn cứ" giữ được cả
  kb_khong_co lẫn can_tool. u12 (khách chửi đòi tiền) được chấm có căn cứ: bot dùng đúng
  `payment-double-charge`.
- Judge ≥ 80% cùng nhãn — **đúng**, 90%. ≥ 90% cùng ý có bịa — đạt về số nhưng **không nói được gì**:
  chỉ có 1 câu bịa, và judge trượt chính câu đó.

**Ba kiểu lệch.**

| Câu | Tay | Judge | Kiểu |
|---|---|---|---|
| g12 | bia | tu_choi_dung | Bỏ sót bịa nghe như quy định chung ngoài đời; lý do judge tự mâu thuẫn ("không cung cấp thông tin nào") |
| g13 | co_can_cu | bia | Đọc sót cụm giới hạn: tài liệu và câu trả lời cùng nói "bật lửa số lượng lớn" |
| u11 | tu_choi_dung | co_can_cu | Kẽ hở rubric: không trả lời câu hỏi chính nhưng kèm thông tin chung có căn cứ |

**Kết luận.** Trên 30 câu này bot ít bịa (1/30), và câu bịa đến từ truy hồi thiếu chunk chứ không
từ prompt. Một câu chưa đủ để mở lại reranker — đếm tiếp. Judge v1 CHƯA dùng được để đo bịa: bộ 30
câu gần như không có câu bịa để thử nó, nên 90% là con số của câu dễ.

---

## 2026-09-15 — Judge v2 và bộ xác nhận

**Thay đổi.** (1) Rubric v2 (`eval/judge.py`): judge liệt kê từng ý cụ thể và đối chiếu với tài
liệu trước khi gắn nhãn; quy định nghe như chuẩn chung mà tài liệu không ghi là bịa; chép lại có giữ
cụm giới hạn là có căn cứ; không trả lời câu hỏi chính thì là từ chối dù có kèm thông tin chung.
(2) `reasoning_effort` low → medium. Đổi hai thứ một lúc là chủ ý: cả hai nhắm cùng hai lỗi, và bộ
xác nhận chỉ đủ dùng một lần. Cái giá: đạt thì không tách được thay đổi nào có công.

Rubric v2 viết ra từ chính 3 câu lệch ở trên, nên chạy lại trên 30 câu cũ chắc chắn đẹp hơn — con
số đó chỉ để kiểm tra không tụt, không để quyết định.

**Bộ xác nhận** (`data/faithfulness_xacnhan.yml`, 20 câu, thứ tự xáo, chấm tay mù):

- Sinh tự nhiên: 4 câu holdout vi người thật gõ, 4 câu `unanswerable` chưa dùng (kb_khong_co 2,
  can_tool 1, ngoai_le 1), 4 câu golden vi chưa dùng.
- **Cài bịa**: 8 câu golden vi chưa dùng — sinh tự nhiên rồi nhờ Gemini viết lại, cài đúng một lỗi,
  4 kiểu × 2 câu: đổi con số hoặc thời hạn; thêm quy định nghe như chuẩn chung (kiểu g12); bỏ cụm
  giới hạn (ngược với g13); thêm số điện thoại, email hoặc link. Kiểu cài của từng câu nằm ở
  `data/faithfulness_xacnhan_dapan.yml` — không mở trước khi chấm xong.

Vì sao cài: 30 câu tự nhiên chỉ ra 1 câu bịa, nên bộ xác nhận tự nhiên cũng sẽ không có câu bịa để
thử judge. Giới hạn: bịa do model cài có thể dễ bắt hơn bịa tự nhiên. Nhãn đúng vẫn là nhãn tay,
không phải đáp án cài — Gemini có thể cài hỏng.

**Tiêu chí đạt tuần 9** (chốt trước khi sinh bộ xác nhận; tính trên nhãn tay của bộ xác nhận):

1. Bắt bịa: trong các câu bạn chấm bia, judge trượt tối đa 1 câu.
2. Báo bịa giả: tối đa 1 câu judge gắn bia mà bạn chấm không bịa.
3. Cùng nhãn 4 loại ≥ 80%.
4. Bản judge đem đi xác nhận, chạy trên 30 câu cũ: cùng nhãn không dưới 90% (mức của v1). Đây là
   điều kiện vào cửa — kiểm tra trước khi chạy bộ xác nhận.

Đạt cả 4: tuần 10 dùng bản judge đó chấm tự động tỉ lệ bịa của từng model; chấm tay chỉ để soát ngẫu
nhiên. Trượt: KHÔNG sửa rubric rồi đo lại trên bộ này — làm vậy là biến nó thành bộ dev thứ hai. Ghi
kiểu lỗi, và tuần 10 dùng judge như bộ lọc: câu nào judge gắn bia, hoặc hai model bị chấm khác nhau,
thì chấm tay. Đạt hay trượt đều sang tuần 10 — mục tiêu tuần 9 là biết judge đáng tin tới đâu.

**Giả thuyết.** Đạt tiêu chí 1, 3, 4; tiêu chí 2 sát ngưỡng vì v2 soi từng ý nên khắt hơn. Kiểu cài
khó bắt nhất là bỏ cụm giới hạn. 4 câu holdout người thật gõ không sinh thêm câu bịa tự nhiên nào.

**Kết quả v2 trên bộ dev** (tiêu chí 4): cùng nhãn 22/30 = 73% — **trượt**, v1 là 90%. Bắt được
g12 (1/1) nhưng báo bịa giả 6 câu, và gắn từ chối cho 2 câu người chấm là có căn cứ.

| Kiểu lỗi của v2 | Câu | Ví dụ |
|---|---|---|
| Coi lời từ chối và lời khuyên liên hệ chung là ý cụ thể → bịa | u01, u03, u04, u10, u11 | "liên hệ tổng đài của VigoTrip", "mình chưa có thông tin…" bị coi là ý không có căn cứ |
| Coi lời nhắc lại mong muốn của khách là ý mới → bịa | g15 | "bấm lên ghế gần cửa sổ còn trống" |
| Luật "phải trả lời câu hỏi chính" áp quá tay → từ chối | g10, g13 | g10 khuyên đăng ký, đúng tài liệu, nhưng không nói thẳng có/không |

Giả thuyết "tiêu chí 2 sát ngưỡng vì v2 khắt hơn" — đúng hướng, sai mức: khắt tới mức hỏng. Gốc
rễ: rubric bảo soi "mọi ý" mà không nói cái gì KHÔNG phải ý. Và chính prompt của chatbot dặn "hướng
khách sang trang phù hợp hoặc tổng đài" khi thiếu căn cứ — v2 phạt đúng hành vi được dặn.

Bộ xác nhận chưa chạy judge nào và chưa ai chấm, nên vẫn còn nguyên giá trị; sửa tiếp rubric trên bộ
dev là hợp lệ.

---

## 2026-09-15 — Judge v3

**Thay đổi so với v2** (giữ `reasoning_effort: medium`): (1) liệt kê rõ cái KHÔNG phải ý cụ thể —
nói chưa có thông tin, từ chối, lời khuyên liên hệ không kèm số/email/địa chỉ, nhắc lại lời khách;
(2) so theo nghĩa thay vì theo chữ, nhưng giữ luật cụm giới hạn; (3) bỏ luật "câu hỏi chính": có ý
cụ thể liên quan và đủ căn cứ là có căn cứ, dù không trả lời thẳng.

**Giả thuyết** (viết trước khi chạy). Trên bộ dev: cùng nhãn ≥ 27/30, vẫn bắt g12, báo bịa giả ≤ 1.
u11 có thể vẫn lệch — ranh giới thật: "không có kết quả thường do chưa mở bán" vừa là ý có căn cứ vừa
không trả lời câu hỏi.

**Nếu v3 vẫn dưới 90% trên bộ dev:** dừng sửa rubric, đem v1 sang bộ xác nhận. Không đem cả hai sang
rồi chọn bản điểm cao hơn — chọn trên bộ xác nhận là biến nó thành bộ dev.

**Kết quả trên bộ dev:**

| Judge | Cùng nhãn | Bắt bịa | Báo bịa giả | Từ chối gắn nhầm |
|---|---|---|---|---|
| v1, low | 27/30 = 90% | 0/1 | 1 | 2 |
| v2, medium | 22/30 = 73% | 1/1 | 6 | 2 |
| v3, medium | 27/30 = 90% | 1/1 | 2 | 1 |

Câu v3 còn lệch:

- g15 (tay có căn cứ → judge bịa): vẫn coi "bấm lên ghế gần cửa sổ" là ý mới, dù rubric lấy đúng câu
  này làm ví dụ KHÔNG phải ý cụ thể.
- u11 (tay từ chối đúng → judge bịa): coi "mình chưa có thông tin về lịch chạy tàu" là ý không có
  căn cứ — trái với chữ của rubric.
- u09 (tay từ chối đúng → judge từ chối thừa): cho rằng chunk thời gian có mặt trước giờ đi trả lời
  được câu khách kể lịch trình. Ranh giới, không phải lỗi rõ.

**Đối chiếu giả thuyết.** ≥ 27/30 — **đúng**, vừa chạm ngưỡng. Vẫn bắt g12 — **đúng**. Báo bịa giả ≤ 1
— **sai**, 2. u11 vẫn lệch — **đúng**, nhưng lệch sang bịa chứ không sang có căn cứ như dự đoán.

**Kết luận.** v3 qua điều kiện vào cửa (tiêu chí 4), nên v3 là bản đem sang bộ xác nhận. Không sửa
thêm: hai câu g15, u11 là judge làm trái chữ của rubric, tức giới hạn của model chứ không còn là kẽ hở
rubric — sửa tiếp chỉ là vá cho khớp 30 câu này. Tín hiệu cần để ý ở bộ xác nhận: v3 vẫn có xu hướng
báo bịa giả ở câu từ chối, nên tiêu chí 2 (tối đa 1 câu) là tiêu chí dễ trượt nhất.

**Kết quả bộ xác nhận** (chấm tay 15/09, judge v3, chạy một lần):

| Tiêu chí | Kết quả | |
|---|---|---|
| 1. Trượt tối đa 1 câu bịa | bắt 7/8 | **đạt** |
| 2. Báo bịa giả tối đa 1 câu | 3 câu | **trượt** |
| 3. Cùng nhãn ≥ 80% | 16/20 = 80% | **đạt**, chạm ngưỡng |
| 4. Bộ dev không dưới 90% | 27/30 = 90% | **đạt** |

Nhãn tay khớp đáp án cài 8/8: cả 8 câu cài đều cài được, và bạn bắt hết, không gắn bịa cho câu nào
khác. Judge theo kiểu cài: đổi con số 1/2, thêm quy định 2/2, bỏ cụm giới hạn 2/2, thêm số/kênh
liên hệ 2/2.

Câu lệch:

| Câu | Tay | Judge | Chuyện gì xảy ra |
|---|---|---|---|
| x05 | bia | co_can_cu | Cài "hủy trước **2 ngày**, tức là trên 24 giờ". Judge thấy "trên 24 giờ" có căn cứ và bỏ qua "2 ngày" mâu thuẫn với chính nó |
| x01 | tu_choi_dung | bia | "VigoTrip luôn đặt bảo mật lên hàng đầu và tuân thủ các tiêu chuẩn an toàn thông tin" — không chunk nào nói vậy |
| x13 | co_can_cu | bia | "đợi trong giây lát để nhà cung cấp xử lý" — tài liệu không nói duyệt mất bao lâu |
| x19 | tu_choi_dung | bia | "truy cập trang tìm kiếm chuyến bay" — lời hướng tới trang, đúng loại rubric bảo bỏ qua |

Ghi chú về ba câu báo bịa giả, viết SAU khi thấy nhãn judge nên chỉ để tham khảo: x19 là judge sai
rõ. x01 và x13 là ranh giới thật — x01 là một lời cam kết về bảo mật mà tài liệu không có, theo chữ
của rubric thì judge không sai. Nhãn tay KHÔNG sửa lại: sửa sau khi đã thấy judge chấm là đúng kiểu
thiên lệch mà quy trình chấm mù sinh ra để chặn. Tiêu chí 2 tính là trượt.

**Đối chiếu giả thuyết.**

- Đạt tiêu chí 1, 3, 4 — **đúng**. Tiêu chí 2 sát ngưỡng — **sai**, trượt hẳn (3 so với ngưỡng 1).
  Xu hướng thấy trên bộ dev (v3 báo bịa giả 2/30) lặp lại: judge v3 khắt, sai về phía báo bịa.
- Kiểu cài khó bắt nhất là bỏ cụm giới hạn — **sai**: bắt 2/2. Câu trượt là đổi con số, khi con số
  bịa đứng cạnh một diễn giải đúng.
- 4 câu holdout người thật gõ không sinh câu bịa tự nhiên — **đúng**, cả 4 có căn cứ.

**Kết luận.** Tuần 9 xong, judge **trượt** tiêu chí 2, nên đi theo nhánh đã chốt: không sửa rubric
trên bộ này; tuần 10 dùng judge v3 như **bộ lọc một chiều**.

- Judge nói KHÔNG bịa → tin. Trên bộ xác nhận nó chỉ sót 1/8 câu bịa, và 0/1 trên bộ dev.
- Judge nói bịa → người chấm lại. Trên bộ xác nhận 10 câu bị gắn bịa thì 7 câu bịa thật (70%).
- Tỉ lệ bịa của một model ở tuần 10 = số câu người xác nhận là bịa, không phải số judge gắn bịa —
  nếu dùng thẳng số của judge, model nào nói nhiều câu trấn an kiểu x01 sẽ bị phạt oan.

Điều kiện đổi ý: nếu tuần 10 người phải chấm lại quá nhiều (judge gắn bịa > 30% câu của một model),
thì làm judge v4 — nhưng chỉ đo trên một bộ xác nhận MỚI.

---

## 2026-09-15 — Bảng live Java sau khi port Bù BM25

**Vì sao.** Bù BM25 đã port sang `HybridRetriever.fuse` (WebProject `4204242`), test offline xanh, 10
dòng BM25 vẫn trùng. Nhưng 20 dòng live chưa đối chiếu lại. Tuần 10 so model local với Gemini trên
đường truy hồi của VigoTrip — nếu Java lệch Python mà không ai biết, phần lệch sẽ bị tính nhầm cho
model.

**Giả thuyết** (viết trước khi chạy).

- Cả 20 dòng Vector / Vector + lọc lang / Hybrid / Hybrid + lọc lang, theo từng ngôn ngữ lẫn gộp,
  trùng từng chữ số ở cả 6 cột giữa `RAG_EVAL_LIVE=1` bên Java và `python -m eval.harness --live`.
- Hybrid + lọc lang trùng Vector + lọc lang trên bộ vàng: với 132 câu, Vector gần như luôn trả đủ
  top-k trên ngưỡng 0.55 nên BM25 không có chỗ để lấp.
- Python chạy từ cache, 0 lời gọi API.

**Kết quả (15/09) — chưa đối chiếu được.**

- Python: 0 lời gọi API, 0 lần 429. Hybrid + lọc lang trùng Vector + lọc lang ở cả 5 dòng (gộp: P@1
  95.5%, R@3 99.2%, MRR 0.975), Hybrid trùng Vector ở cả 5 dòng không lọc — **đúng** giả thuyết 2 và 3.
- Java: **hỏng**. Lô embedding đầu dính 429 cả 4 lần thử (30 s, 60 s, 90 s). Không phải giới hạn theo
  phút như lần 14/09, mà hết hạn mức ngày: `EmbedContentRequestsPerDayPerProjectPerModel-FreeTier`,
  1000 lượt. Bảng live Java không in dòng nào — giả thuyết 1 chưa kiểm được.

**Kết quả (15/09, lần 2) — đối chiếu được mà không chờ hạn mức.**

- Thay vì chờ, bộ đo Java đọc thẳng `cache/embeddings/` của repo này (biến
  `RAG_EVAL_EMBEDDING_CACHE`, khoá file `sha256(model \0 số chiều \0 văn bản)` giống `rag/embed.py`).
  Điều kiện để đọc chung được đã kiểm trước: 132 câu `golden.yml` trùng từng chữ với `rag-eval.yml`,
  bốn file `data/kb/faq-*.yml` trùng từng byte với bản Java, cùng `gemini-embedding-001` / 768 chiều /
  `title. content`.
- Java: 356 vector từ cache (224 chunk + 132 câu), **0 lời gọi API**, chạy không có `GEMINI_API_KEY`.
  Python: 0 lời gọi, chạy với key giả và `EMBEDDING_BASE_URL` trỏ vào cổng chết để lần chạy không thể
  ra mạng.
- `diff` hai bảng: **20 dòng Vector/Hybrid trùng từng chữ số ở cả 6 cột, 10 dòng BM25 cũng trùng** —
  giả thuyết 1 **đúng**. Hai bên dùng CÙNG từng vector nên phép so này chặt hơn cả hai lần gọi API
  riêng (loại được khả năng API trả vector hơi khác giữa hai lần).

**Kết luận.** Đường truy hồi của VigoTrip khớp bản Python sau khi port Bù BM25. Tuần 10 so model được
trên đường này mà không phải lo phần lệch Java/Python bị tính nhầm cho model. Từ nay bảng live chạy lại
từ cache; chỉ khi đổi knowledge base hoặc bộ câu hỏi mới cần gọi API để điền phần thiếu.

---

## 2026-09-15 — Embedding tự host: `bge-m3` so với `gemini-embedding-001`

**Vì sao.** Hạn mức embedding Gemini hết ngày 15/09 (1000/1000 lượt), và mọi lần đổi knowledge base
đều phải gọi lại. Tuần 7 còn treo Contextual Retrieval — nó nhúng lại cả 224 chunk mỗi lần thử. Cần
biết một model nhúng chạy trên RTX 4060 kém Gemini bao nhiêu trên chính các bộ câu này, trước khi dùng
nó cho bất kỳ thí nghiệm nào.

Đây là thí nghiệm mới, KHÔNG phải chạy lại: đổi model là đổi toàn bộ vector, nên số của `bge-m3` chỉ so
được với bảng Gemini chạy cùng ngày trên cùng dữ liệu, không thay được bảng nào ở trên.

**Cách đo.**

- Model: `bge-m3` qua Ollama 0.34.0 (bản F16, khoảng 568 triệu tham số, 1024 chiều cố định, 664 MB
  VRAM). Gọi qua endpoint tương thích OpenAI, không sửa `rag/embed.py`:
  `EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1`, `EMBEDDING_MODEL=bge-m3`, `EMBEDDING_DIMENSIONS=0`
  (không gửi `dimensions`), `EMBEDDING_MIN_INTERVAL_S=0`, key giả. Khoá cache có tên model, nên vector
  hai model không đè nhau.
- Giữ nguyên: 4 file `data/kb/faq-*.yml`, văn bản đem nhúng `title. content` (dài 37–470 ký tự, không
  chunk nào bị cắt), BM25, Bù BM25, 10 ứng viên mỗi nhánh, top-5.
- Gemini: chạy lại từ cache cùng ngày, 0 lời gọi API, để hai bảng đặt cạnh nhau.
- Bộ câu: `golden.yml` (132, 4 ngôn ngữ) để so; `holdout.yml` (104 vi: 55 Claude viết, 49 người thật
  gõ) và `holdout_codes.yml` (32 vi) chạy **một lần** để xác nhận.
- Đọc bảng ở đường production (Hybrid + lọc lang) và Vector + lọc lang.
- **Ngưỡng cosine.** 0.55 được chọn cho Gemini bên Java; `bge-m3` có thang cosine khác. Bảng chính giữ
  0.55 để chỉ đổi một biến là model. Chạy thêm một lượt `--min-similarity 0` cho CẢ HAI model, để tách
  "xếp hạng kém" khỏi "ngưỡng không hợp". Không chọn ngưỡng mới cho `bge-m3` trong mục này. Nếu cần
  chọn thì mở mục riêng, chọn trên golden.
- Độ trễ: nhúng từng câu hỏi một (như lượt chat thật), GPU đã nạp model, lấy p50/p95 trên 132 câu
  golden. Gemini hết hạn mức nên chưa có độ trễ để so. Ghi riêng số của `bge-m3`.
- Tách câu vi theo dấu: "không dấu" là câu mà bỏ dấu xong vẫn y nguyên.

Thứ duy nhất đã thấy trước khi viết mục này là lần thử máy chạy: hai câu tự đặt, không thuộc bộ nào,
cosine 0.911, lần gọi nóng 74–106 ms cho cả cặp.

**Giả thuyết** (viết trước khi chạy).

1. **Golden.** `bge-m3` kém Gemini nhưng không nhiều: P@1 gộp của Hybrid + lọc lang ≥ 123/132, tức
   kém Gemini (126) không quá 3 câu. R@3 gộp ≥ 97%.
2. **Câu người thật gõ và câu không dấu.** Khoảng cách lớn hơn golden: trên holdout vi, `bge-m3` kém
   Gemini (88/104) từ 4 câu P@1 trở lên. Phần lớn chênh lệch nằm ở câu không dấu: tính theo tỉ lệ,
   khoảng cách ở câu không dấu lớn hơn ở câu có dấu. Lý do: tokenizer của `bge-m3` thấy "huy ve" và
   "hủy vé" là hai chuỗi token khác hẳn, còn Gemini được train trên nhiều văn bản web tiếng Việt gõ
   không dấu hơn.
3. **Ngưỡng.** Cosine của `bge-m3` dồn lên cao hơn Gemini, nên 0.55 gần như không chặn gì. Với
   `bge-m3`, bảng 0.55 và bảng 0 chênh không quá 1 câu P@1 trên mỗi bộ. Với Gemini thì có thể chênh
   nhiều hơn: ở bộ có mã, Bù BM25 đã lấp đúng chỗ ngưỡng chặn.
4. **Độ trễ.** Nhúng một câu hỏi trên RTX 4060: p50 ≤ 50 ms, p95 ≤ 150 ms. Nhúng cả 224 chunk dưới
   30 giây.

**Tiêu chí dùng** (chốt trước khi chạy):

- **Dùng được cho thí nghiệm offline** (Contextual Retrieval, đổi chunk, lúc hết hạn mức) nếu P@1 gộp
  golden ≥ Gemini − 3 câu VÀ holdout vi ≥ Gemini − 5/104. Kết luận của thí nghiệm nào dùng `bge-m3` vẫn
  phải kiểm lại một lần trên Gemini trước khi port sang VigoTrip.
- **Chưa đạt** thì chỉ dùng để thử máy và đo độ trễ, không dùng để chọn cấu hình.
- **Không** thay Gemini trong VigoTrip ở mục này, kể cả khi `bge-m3` thắng. Đổi production kéo theo
  chạy Ollama trên máy chủ, nhúng lại toàn bộ KB và có một ngưỡng mới, nên là quyết định riêng. Nếu
  `bge-m3` hơn Gemini từ 3 câu ở cả golden lẫn holdout thì ghi lại làm ứng viên.

**Thay đổi.** `scripts/embed_compare.py` in bảng hai ngưỡng × ba bộ × tách dấu, và đo độ trễ khi có
cờ `--latency`. Không đổi gì trong `rag/`.

Một lỗi bắt được trước khi đọc số: lượt Gemini đầu tiên dựng client không có key nên `available`
bằng False. `HybridRetriever` lặng lẽ bỏ nhánh Vector, và cột "Hybrid" in ra đúng số BM25 (golden
76.5%). Đã sửa bằng client chỉ đọc cache, thêm chốt "Vector trả rỗng mọi câu thì báo hỏng". Số bên
dưới là của lượt sau khi sửa.

**Kết quả** (15/09; Gemini 0 lời gọi API; `bge-m3` 17 lời gọi Ollama, 0 lỗi; + lọc lang).

P@1 theo ngưỡng. "Hybrid" là Bù BM25, đường production:

| Bộ | Gemini Hybrid 0.55 | bge-m3 Hybrid 0.55 | bge-m3 Vector 0.55 | bge-m3 Vector 0 |
|---|---|---|---|---|
| golden gộp (132) | 95.5% (126) · R@3 99.2% | **92.4% (122)** · R@3 99.2% | 83.3% (110) | 85.6% (113) |
| golden vi (59) | 94.9% (56) | 88.1% (52) | 67.8% (40) | 72.9% (43) |
| holdout vi (104) | 84.6% (88) · R@3 97.1% | **67.3% (70)** · R@3 89.4% | 56.7% (59) | 68.3% (71) |
| holdout_codes vi (32) | 90.6% (29) | 65.6% (21) | 37.5% (12) | 59.4% (19) |

Gemini ở ngưỡng 0 trùng ngưỡng 0.55 trên golden và holdout, bộ có mã chỉ lệch 1 câu (Vector 28 → 29).
Với Gemini, Hybrid và Vector trùng nhau ở ngưỡng 0.

Tách câu vi theo dấu, P@1 (R@3), đường production (Hybrid 0.55):

| Bộ | Gemini có dấu | bge-m3 có dấu | Gemini không dấu | bge-m3 không dấu |
|---|---|---|---|---|
| golden | 97.9% (46/47) | 89.4% (42/47) | 83.3% (10/12) | 83.3% (10/12) |
| holdout | 84.7% (72/85) | 74.1% (63/85) | 84.2% (16/19) | 36.8% (7/19) |
| holdout_codes | 90.5% (19/21) | 71.4% (15/21) | 90.9% (10/11) | 54.5% (6/11) |

Cosine hạng 1 của 195 câu vi (gộp ba bộ, so với chunk vi):

| Model | Có dấu: trung vị (min–max) | ≥ 0.55 | Không dấu: trung vị (min–max) | ≥ 0.55 |
|---|---|---|---|---|
| Gemini | 0.779 (0.606–0.897) | 153/153 | 0.711 (0.523–0.869) | 41/42 |
| bge-m3 | 0.659 (0.377–0.810) | 133/153 | 0.382 (0.306–0.525) | **0/42** |

Độ trễ `bge-m3` trên RTX 4060 (GPU đã nạp, 664 MB VRAM): nhúng từng câu hỏi p50 45 ms, p95 53 ms,
max 165 ms (132 câu); 224 chunk theo lô 32 mất 3.5 s.

**Đối chiếu giả thuyết.**

1. Golden kém Gemini không quá 3 câu — **sai**: kém 4 (122 so với 126). R@3 gộp ≥ 97% — **đúng**,
   99.2%.
2. Holdout kém từ 4 câu trở lên — **đúng**, và nặng hơn nhiều: kém 18 câu. Khoảng cách ở câu không dấu
   lớn hơn câu có dấu — **đúng**: holdout có dấu kém 10.6 điểm, không dấu kém 47.4 điểm. Nhưng câu có
   dấu cũng kém thật, ở cả ba bộ (8.5–19.1 điểm), không chỉ vì chuyện dấu.
3. Cosine của `bge-m3` dồn lên cao nên 0.55 gần như không chặn gì — **sai, và ngược chiều**. Cosine của
   `bge-m3` THẤP hơn Gemini. Ngưỡng 0.55 chặn sạch 42/42 câu không dấu và 20/153 câu có dấu. Bảng 0.55
   và bảng 0 chênh tới 9 câu Hybrid ở golden, 1 ở holdout, 2 ở bộ có mã.
4. p50 ≤ 50 ms, p95 ≤ 150 ms, 224 chunk dưới 30 s — **đúng**: 45 ms, 53 ms, 3.5 s.

**Chuyện gì xảy ra với câu không dấu.** Ở ngưỡng 0.55, nhánh Vector của `bge-m3` trả rỗng mọi câu
không dấu. Bù BM25 lùi hẳn về BM25, nên cột "bge-m3 không dấu" chính là số BM25 (holdout 36.8%, trùng
BM25 của Gemini). Hạ ngưỡng về 0 cũng không cứu được: Vector không dấu còn 1/12 golden, 7/19 holdout,
1/11 bộ có mã. Tức là `bge-m3` thật sự không hiểu tiếng Việt gõ không dấu, chứ không chỉ do ngưỡng
chọn sai. Trên golden, ngưỡng 0.55 còn giúp: nó đẩy câu không dấu sang BM25, tốt hơn để Vector xếp
bừa. Đó là lý do Hybrid 0.55 (122) hơn Hybrid 0 (113).

**Kết luận.** **Chưa đạt** cả hai tiêu chí dùng: golden kém 4 câu (ngưỡng 3), holdout kém 18/104
(ngưỡng 5). Theo tiêu chí đã chốt, `bge-m3` chỉ dùng để thử máy và đo độ trễ, KHÔNG dùng để chọn cấu
hình, kể cả cho thí nghiệm offline như Contextual Retrieval.

Khách VigoTrip gõ không dấu khá nhiều: 19/104 câu holdout, và phần người thật gõ là nguồn chính. Một
model nhúng không hiểu tiếng Việt không dấu thì không thay được Gemini, dù nhanh và miễn phí.

Không chọn ngưỡng mới cho `bge-m3`, đúng như đã chốt. Bảng ngưỡng 0 cho thấy chỉnh ngưỡng không cứu
được câu không dấu.

Đổi ý nếu:

- Một model nhúng local khác (ví dụ `multilingual-e5-large`, hoặc model mới hơn có tiếng Việt) qua cả
  hai tiêu chí trên cùng bảng này. Chạy lại bằng `scripts/embed_compare.py`, mục riêng.
- Hoặc thêm bước khôi phục dấu cho câu hỏi trước khi nhúng. Đó là một biến mới, cần mục riêng, chọn
  trên golden.

## 2026-09-16 — Model mở đã quantize so với Gemini ở tầng sinh (tuần 10)

**Vì sao.** Tuần 9 đã trả lời "bot có bịa không" cho đúng một model: `gemini-flash-lite-latest`.
Câu hỏi của tuần 10 khác hẳn — một model chạy trên máy mình, không hạn mức, không gửi dữ liệu khách
ra ngoài, thì kém bao nhiêu. VigoTrip gọi LLM qua `OpenAiCompatibleProvider`, nên nếu số đo chấp
nhận được thì việc cắm model local vào gần như chỉ là sửa `application.yml`.

Đây là thí nghiệm mới, KHÔNG phải chạy lại: đổi model sinh là đổi toàn bộ câu trả lời.

**Giả thuyết.** Model mở 7–9B bản Q4 giữ được phần lớn độ trung thực của Gemini trên cùng 30 câu
bộ dev, vì việc ở đây là đọc 4 chunk rồi tóm lại — không cần kiến thức rộng, chỉ cần bám tài liệu.
Chỗ nó thua sẽ không phải bịa nhiều hơn, mà là **từ chối thừa**: model nhỏ hay trả lời lảng khi
tài liệu có nhưng viết vòng vo.

**Thay đổi.** Đúng MỘT biến: model ở tầng sinh. Giữ nguyên tuyệt đối mọi thứ khác —

- 30 câu bộ dev `data/faithfulness.yml`, đã có `nhan_tay` từ tuần 9;
- **chính các `chunks` đã ghi trong file đó**, không chạy lại retrieval. Nên thí nghiệm này tốn
  **0 lời gọi embedding**, và chênh lệch không thể do bốc tài liệu khác;
- prompt `data/prompts/vigotrip_chat.txt`, `FIXED_NOW`, top-4, temperature 0.7, tối đa 800 token;
- judge: Groq `gpt-oss-120b` rubric v3, temperature 0 — giữ nguyên bộ chấm của tuần 9.

**Model đem so.** Gemini Flash-Lite (đọc cache tuần 9, 0 lời gọi) · Groq `gpt-oss-120b` · và ba
model local qua Ollama: `qwen3.5:9b`, `qwen3:8b`, `glm4:9b`. Cả ba đều gọi được tool — tuần 12 dùng
lại đúng ba model này cho `tool-eval.yml`, nên chọn model biết gọi tool ngay từ tuần 10.

**Groq tự chấm bài mình.** Bên sinh của dòng Groq là `openai/gpt-oss-120b` — đúng model judge
đang dùng. Tuần 9 cố ý chọn judge khác họ với bên sinh vì lý do này. Nên dòng Groq chỉ để tham
khảo về tốc độ và giá, KHÔNG dùng để kết luận model nào bịa ít hơn. Nếu sau này cần một dòng
"model mạnh làm mốc" chấm được đàng hoàng thì phải đổi judge sang họ khác, và đó là thí nghiệm riêng.

**Judge chỉ là bộ lọc.** Kết luận tuần 9: judge v3 trượt tiêu chí 2 (báo bịa giả 3 câu trên bộ xác
nhận). Nên ở đây nó nói *không bịa* thì tin, nói *bịa* thì câu đó phải chấm tay. Bảng dưới ghi cả
hai con số: judge gắn bịa, và số còn lại sau khi người xác nhận.

**Tiêu chí dùng** — chốt TRƯỚC khi chạy, để không nhìn số rồi mới nới:

1. Bịa (đã xác nhận tay) không nhiều hơn Gemini quá **2 câu** trên 30. Gemini tuần 9: 1/30.
2. `tu_choi_thua` không nhiều hơn Gemini quá **3 câu** — đây là chỗ giả thuyết đoán nó sẽ thua.
3. Đủ nhanh cho tầng `CHAT`: **≥ 15 token/giây** và **p95 ≤ 10 giây**.
4. Chạy trọn GPU: **VRAM ≤ 7.5 GB**, không tràn sang RAM.

Qua cả 4 thì đủ làm đường lui cho `CHAT` khi Gemini hết hạn mức. Trượt 1 hoặc 2 thì không dùng cho
`CHAT`, ghi rõ trượt cái nào. Trượt 3 hoặc 4 thì chỉ còn dùng được cho việc chạy nền (`ANALYSIS`).

**Cách đo.** `scripts/gen_compare.py gen --model <tên>` rồi `judge --model <tên>`, ghi ra
`data/gen_compare/<model>.yml`. Token/giây lấy từ `usage.completion_tokens` chia thời gian thật của
lời gọi, chỉ tính lời gọi mới (đọc cache thì không tính). VRAM đọc bằng `ollama ps` lúc model đang nạp.

**Hai chuyện phát hiện lúc chạy, phải xử lý trước khi có số** —

*1. Model local mặc định BẬT suy nghĩ, và nó ăn hết ngân sách token.* `qwen3.5:9b` có
`capabilities: [vision, completion, tools, thinking]`. Gọi thẳng như tuần 9 thì 800 token
`max_tokens` bị tiêu hết cho phần `reasoning`, `content` trả về **rỗng** — `ChatClient` ném
`LlmError` ngay câu đầu. Thử ba cách tắt ở đường `/v1`: `think: false` và
`chat_template_kwargs.enable_thinking` đều bị Ollama bỏ qua; chỉ `reasoning_effort: "none"` ăn.
Chọn tắt suy nghĩ vì hai lý do: Gemini Flash-Lite tuần 9 chạy không có ngân sách suy nghĩ nên để
bật là so hai thứ khác nhau, và tầng `CHAT` của VigoTrip cần nhanh. **Bật suy nghĩ là một dòng
riêng, một thí nghiệm riêng** — chưa làm.

*2. Dòng gemini không cần chấm lại.* 30 câu sinh từ cache tuần 9 trùng NGUYÊN VĂN 30/30, nên
`judge --model gemini` chép thẳng nhãn v3 và nhãn tay của tuần 9 sang: **0 lời gọi Groq**, và hai
bảng chắc chắn dùng đúng một bộ nhãn.

**Thu hẹp còn một model local.** Kế hoạch ban đầu ghi ba tag `qwen3.5:9b`, `qwen3:8b`, `glm4:9b`.
Trên máy chỉ có sẵn `qwen3.5:9b`; chốt ngày 16/09 là dừng ở một model, vì câu hỏi của tuần 10 là
"model local có dùng được không", không phải "model local nào tốt nhất". Muốn xếp hạng giữa các
model mở thì đó là mục riêng.

**Kết quả.**

| Model | Bịa (judge) | Bịa (xác nhận tay) | tu_choi_thua | co_can_cu | token/giây | p50 (ms) | p95 (ms) | VRAM |
|---|---|---|---|---|---|---|---|---|
| gemini-flash-lite-latest | 3/30 | **1** | 0 | 15 | — (cache tuần 9 không ghi usage) | 1125 | 1663 | — |
| qwen3.5:9b Q4_K_M (suy nghĩ tắt) | 8/30 | **2** | 0 | 15 | **30.7** | **2150** | **3367** | **5.5 GB · 100% GPU** |

Judge gắn bịa 8 câu cho qwen: `g05 g09 g10 g11 g15 u04 u09 u10`. Chấm tay 16/09 giữ lại **2**:

- `g09` — tài liệu ghi *dưới 2 tuổi miễn phí*, *2–12 tuổi tính 75% và có ghế riêng*. Qwen trả lời
  "trẻ từ 2 đến dưới 5 tuổi được miễn vé, không có ghế riêng": trộn hai chunk thành một chính sách
  không tồn tại. Kiểu lỗi đáng sợ nhất — trôi chảy, sai ở con số.
- `g10` — chunk chỉ nói *nên* đăng ký, không có tài khoản thì tra cứu và hủy vé khó hơn. Qwen đẩy
  thành hai khẳng định mạnh hơn hẳn tài liệu: đặt vé không cần tài khoản *được*, và muốn nhận mã QR
  hay hoàn tiền thì *bắt buộc* phải đăng ký. Cùng câu hỏi đó Gemini bám sát chunk và được
  `co_can_cu`.

Sáu câu còn lại là judge báo nhầm, chia làm hai kiểu: `g05 g11 g15` — các ý cụ thể đều có trong
chunk, phần judge chỉ trích là lời khuyên chung hoặc câu hỏi lại khách; `u04 u09 u10` — khách hỏi
ngoài phạm vi và bot từ chối đúng, tức `tu_choi_dung` chứ không phải bịa.

**Tỉ lệ báo nhầm của judge v3 giờ đo được trên hai model:** Gemini 3 gắn → 1 thật, qwen 8 gắn →
2 thật. Tức khoảng **3/4 số câu nó gắn bịa là báo nhầm**, và nhầm theo đúng một hướng (thà gắn thừa
còn hơn bỏ sót). Đúng cách dùng đã chốt ở tuần 9: **judge làm bộ lọc, không làm thước**. `g15` bị
gắn ở CẢ hai model và cả hai lần chấm tay đều bác.

Hai tiêu chí về máy đã có đáp án, và cả hai đều **đạt**:

- Tiêu chí 3 (đủ nhanh cho `CHAT`): 30.7 token/giây ≥ 15, p95 3.4 s ≤ 10 s. Chậm hơn Gemini
  khoảng 2 lần ở p50 (2150 so với 1125 ms) nhưng vẫn dưới ngưỡng.
- Tiêu chí 4 (chạy trọn GPU): `ollama ps` báo 5.5 GB · 100% GPU · context 4096, dưới trần 7.5 GB.
  `nvidia-smi` lúc đó báo 7.4/8.2 GB toàn máy — phần dôi là màn hình Windows và trình duyệt, không
  phải model. Đọc số của `ollama ps` chứ đừng đọc `nvidia-smi` cho tiêu chí này.

Tiêu chí 2 (`tu_choi_thua`) cũng đã có: **0 câu**, bằng Gemini — giả thuyết ban đầu đoán model nhỏ
sẽ hay trả lời lảng, và nó **sai**. Qwen từ chối 13 câu, tất cả đều đúng nhóm ngoài phạm vi.

Tiêu chí 1 (bịa): **2/30**, ngưỡng đã chốt trước khi chạy là ≤ 3/30. Đạt.

**Kết luận. Cả 4 tiêu chí đều đạt.**

| Tiêu chí | Ngưỡng chốt trước | Đo được | |
|---|---|---|---|
| 1 · bịa (xác nhận tay) | ≤ 3/30 | 2/30 | đạt |
| 2 · `tu_choi_thua` | ≤ 3 | 0 | đạt |
| 3 · đủ nhanh cho `CHAT` | ≥ 15 tok/s, p95 ≤ 10 s | 30.7 tok/s, p95 3.4 s | đạt |
| 4 · chạy trọn GPU | VRAM ≤ 7.5 GB | 5.5 GB, 100% GPU | đạt |

Nói gọn một câu: **`qwen3.5:9b` Q4_K_M chạy trên RTX 4060 8 GB bịa 2/30 câu so với 1/30 của Gemini
Flash-Lite, chạy 30.7 token/giây với p95 3.4 giây, tốn 5.5 GB VRAM — đủ tốt để làm đường lui cho
tầng `CHAT` khi Gemini hết hạn mức.**

Ba điều kiện kèm theo, phải ghi cùng kết luận:

1. **Chỉ đúng cho tầng `CHAT` với RAG.** Việc ở đây là đọc 4 chunk rồi tóm lại. Không suy ra được
   gì cho `ANALYSIS` (ngữ cảnh dài) hay cho câu hỏi cần kiến thức ngoài tài liệu.
2. **Chưa đo tool calling.** `CHAT` của VigoTrip còn phải gọi đúng tool. Model có `capabilities:
   tools` nhưng có gọi đúng hay không thì `tool-eval.yml` mới trả lời. Chưa chạy.
3. **Suy nghĩ đang tắt.** Số trên là của `reasoning_effort: "none"`. Bật suy nghĩ có thể bớt bịa
   nhưng đổi lại độ trễ — thí nghiệm riêng, chưa làm.

Hai chỗ nó thua đều là cùng một kiểu, và đáng ghi lại: `g09` và `g10` không phải bịa ra thông tin
từ hư không, mà là **nói mạnh hơn tài liệu** — biến "nên" thành "bắt buộc", trộn ngưỡng tuổi của
hai chunk thành một. Đây là chỗ prompt có thể chữa được (thêm ràng buộc "không suy rộng quá tài
liệu, giữ nguyên mức độ chắc chắn của câu gốc"), và nếu làm thì là thí nghiệm có mục riêng.


## 2026-09-16 (b) — Model local có gọi đúng tool không (tuần 10, phần cuối)

**Vì sao.** Kết luận buổi sáng chỉ nói về tầng sinh: qwen3.5:9b đọc 4 chunk rồi tóm lại tốt gần
bằng Gemini. Nhưng tầng `CHAT` của VigoTrip không chỉ tóm tài liệu — nó còn phải chọn đúng tool và
điền đúng tham số. Chưa đo cái đó thì chưa được nói "dùng làm đường lui cho `CHAT`".

**Chặn kỹ thuật phải gỡ trước.** Trang lộ trình ghi cắm model local vào VigoTrip "chỉ là sửa
`application.yml`". Sai với model biết suy nghĩ: `OpenAiCompatibleProvider` dựng thân request cứng
(`model`, `messages`, `max_tokens`, `temperature`, `tools`), không có đường đẩy `reasoning_effort`
từ YAML xuống, nên cắm thẳng vào thì VigoTrip nhận `content` rỗng. Thử lối vòng không đụng code —
`ollama create` với `PARAMETER think false` — Ollama trả `unknown parameter 'think'`.

Nên thêm `extra-body` vào `LlmProperties.Provider`, đổ vào thân request TRƯỚC các trường cố định
(một khoá gõ nhầm trong YAML không đè được `model` hay `messages`). Ba chỗ sửa bên WebProject:
`LlmProperties.java`, `OpenAiCompatibleProvider.java`, `application.yml` (thêm nhà cung cấp
`ollama` đứng CUỐI chuỗi `chat`, `api-key` để trống nên mặc định bị loại lúc khởi động — không
đặt `OLLAMA_API_KEY` thì hệ thống chạy y như trước).

**Giả thuyết.** Chọn đúng tool là việc khó hơn tóm tài liệu: model phải đọc mô tả nhiều tool, so
với câu hỏi, rồi quyết định. Đoán qwen3.5:9b tụt nhiều hơn ở đây so với mức tụt ở tầng sinh
(2/30 so với 1/30), và tụt mạnh nhất ở **14 ca không được gọi tool** — model nhỏ hay "sốt sắng",
thấy có tool là gọi.

**Thay đổi.** Đúng một biến: nhà cung cấp. Cùng 53 ca `tool-eval.yml`, cùng prompt hệ thống lấy
từ `ChatService.toolUsageGuide`, cùng `temperature` 0.7 của production. Model local chạy với
`extra-body: {reasoning_effort: none}` — đúng cấu hình đã đo ở mục trước.

**Tiêu chí dùng** — chốt TRƯỚC khi nhìn số:

1. **Khớp bộ** (gọi đúng TẬP tool, không thiếu không thừa) không kém Gemini quá **10 điểm phần trăm**.
2. **Gọi thừa** trên 14 ca không được gọi tool: không nhiều hơn Gemini quá **2 ca**.
3. **Args** (tham số khớp) không kém Gemini quá **10 điểm phần trăm**.

Qua cả 3 thì kết luận buổi sáng đứng vững, bỏ được cảnh báo "tool calling chưa đo". Trượt tiêu chí
2 là nặng nhất: gọi tool khi không nên là đường prompt injection đi vào.

**Hai cái bẫy vận hành gặp trước khi có số** — cùng một kiểu, khác nhà cung cấp:

1. **Throttle nhanh hơn hạn mức không phải là chạy nhanh hơn.** Bộ đo để
   `MIN_INTERVAL_MS = 1_500` (40 lượt/phút) trong khi Flash-Lite free tier cho 15 lượt/phút.
   Gần như lượt nào cũng ăn 429, mỗi lần lại nằm chờ `RETRY_AFTER_429_MS` = 20 giây: chạy gần
   một tiếng vẫn chưa xong nhà cung cấp đầu. Đổi về 4.000 ms (đúng nhịp 15 lượt/phút) thì cả 53
   ca xong trong khoảng 7 phút và chỉ dính 429 **một lần**.
2. **Groq đã cạn token ngày** (`TPD: Limit 200000, Used 198752`). Mỗi ca ăn trọn 20+40+60 giây
   backoff rồi vẫn hỏng, mà Ollama đứng SAU Groq trong hàng nên không bao giờ tới lượt. Bỏ Groq
   khỏi chuỗi đo — mất mát bằng không, vì nó dùng đúng model mà judge dùng nên tuần 9 đã xếp nó
   là dòng tham khảo.

**Kết quả** (16/09, `temperature` 0.7 của production, 53 ca, Gemini 105 lời gọi / Ollama 96).

| Cấu hình | Câu | Khớp bộ | F1 vi mô | macroF1 | Gọi thừa | Bỏ tra | Args |
|---|---|---|---|---|---|---|---|
| gemini · vi | 29 | 96.6% | 0.978 | 0.958 | 0/9 | 3.4% | 96.9% |
| gemini · en | 12 | 100% | 1.000 | 1.000 | 0/3 | 0.0% | 100% |
| **gemini · gộp** | **53** | **98.1%** | **0.988** | **0.975** | **0/14** | **1.9%** | **98.1%** |
| ollama · vi | 29 | **100%** | 1.000 | 1.000 | 0/9 | 0.0% | 96.9% |
| ollama · en | 12 | 91.7% | 0.889 | 0.917 | 0/3 | 8.3% | 100% |
| **ollama · gộp** | **53** | **98.1%** | **0.976** | **0.981** | **0/14** | **1.9%** | **98.1%** |

Đối chiếu ba tiêu chí đã chốt: **đạt cả ba, và không phải đạt sát nút mà là ngang bằng.**

| Tiêu chí | Ngưỡng | Đo được | |
|---|---|---|---|
| 1 · Khớp bộ | kém Gemini ≤ 10 điểm | 98.1% so với 98.1% — bằng nhau | đạt |
| 2 · Gọi thừa | nhiều hơn Gemini ≤ 2 ca | 0/14 so với 0/14 | đạt |
| 3 · Args | kém Gemini ≤ 10 điểm | 98.1% so với 98.1% | đạt |

**Giả thuyết sai, và sai ở chỗ đáng chú ý.** Đoán qwen sẽ tụt mạnh nhất ở 14 ca không được gọi
tool vì "model nhỏ hay sốt sắng". Thực tế **cả hai đều 0/14**, không model nào gọi thừa một lần.
Đây là lần thứ hai trong tuần 10 giả thuyết "model nhỏ sẽ hỏng ở chỗ X" bị số đo bác — lần đầu là
`tu_choi_thua` ở tầng sinh.

**Hai model sai ở hai chỗ khác hẳn nhau, và đây mới là phần đáng đọc:**

- **Gemini bịa mã điểm.** Ca `"tìm vé đi Quy Nhơn"`: Quy Nhơn không có trong bảng quy đổi, Gemini
  truyền `destination = QNH` — mã của **Quảng Ninh**, cách đó hơn 800 km. Ba lần liên tiếp. Đây
  là trường `forbid` trong `tool-eval.yml`, và nó làm **bộ đo FAIL**: ngưỡng tham số bị cấm là 0,
  đo được 3. Kiểu lỗi tệ nhất trong tool calling — gọi đúng tool, tra sai chỗ, không ném ra ngoại
  lệ nào, nên không có log lỗi nào để mà phát hiện.
- **qwen không bịa tham số nào.** 0 lần truyền tham số bị cấm. Hai ca nó trượt đều là kiểu "thiếu"
  chứ không phải "sai": để trống `departureDate` khi khách nói "tối nay", và bỏ hẳn chuỗi hai bước
  ở bản tiếng Anh (`"my next trip is coming up, what will the weather be like there"` — phải đọc
  đơn hàng xong mới biết hỏi thời tiết ở đâu).

**Kết luận. Đạt cả ba tiêu chí.** Nói gọn: **`qwen3.5:9b` Q4 chọn tool ngang Gemini Flash-Lite
trên bộ 53 ca — cùng 98.1% khớp bộ, cùng 0/14 gọi thừa, cùng 98.1% tham số đúng — và trong mẻ đo
này nó KHÔNG bịa tham số, còn Gemini bịa 3 lần.** Cảnh báo "tool calling chưa đo" của kết luận
buổi sáng được gỡ.

> **Đính chính 16/09, sau mục (d).** Vế cuối — "qwen không bịa, Gemini bịa" — **không đứng vững**.
> Mẻ thứ ba cho kết quả ngược: qwen truyền `QNH`, Gemini thì không. Điều còn đúng là **cả hai đều
> mắc**, và một mẻ ở `temperature` 0.7 không xếp hạng được hai model sát nhau đến thế. Xem mục (d).
> Ba con số 98.1% cũng chỉ là của mẻ hôm đó, không phải hằng số.

Ba điều kiện kèm theo:

1. **Một mẻ đo không phải một kết luận về độ ổn định.** `temperature` giữ 0.7 của production nên
   kết quả không tất định. Mẻ chạy dở trước đó Gemini đạt F1 1.000 trên cả 8 tool, không có ca
   Quy Nhơn nào sai. Muốn nói "Gemini hay bịa mã điểm" thì phải chạy lại nhiều lần — đó là mục
   riêng. Ở đây chỉ được nói: lỗi ĐÓ CÓ THẬT và bộ đo bắt được.
2. **Prompt không phải bản đầy đủ.** Bộ đo không nhét tri thức RAG và danh sách voucher cá nhân
   hoá (chúng phụ thuộc nội dung cơ sở dữ liệu). Hai thứ đó đẩy theo chiều dễ đoán: có sẵn tri
   thức thì model gọi tool ÍT hơn, nên "gọi thừa" ở đây là chặn trên.
3. **Vẫn chỉ nói về `CHAT`.** `ANALYSIS` (ngữ cảnh dài) chưa đo, và kết luận này không suy ra
   được cho nó.

**Điều đáng giá nhất của mục này không phải điểm của qwen, mà là ca Quy Nhơn.** Bộ đo được dựng
để chấm model local, và thứ nó bắt được lại là một lỗi của model đang chạy production. Cây thước
chỉ có ích khi nó đo được cả cái mình không định đo.


## 2026-09-16 (c) — Gemini bịa mã điểm có tái lập không (thăm dò ca Quy Nhơn)

**Vì sao.** Mục 16/09 (b) chạy `tool-eval` một mẻ và bắt được Gemini truyền
`search_trips.destination = QNH` cho câu `"tìm vé đi Quy Nhơn"`. QNH là mã **Quảng Ninh**, cách
Quy Nhơn hơn 800 km. Nếu lỗi này tái lập được thì nó KHÔNG phải chuyện của model local — nó là lỗi
đang chạy trên production của VigoTrip, và nghiêm trọng hơn mọi con số khác của tuần 10: gọi đúng
tool, tra sai tỉnh, **không ném ra ngoại lệ nào** nên không có log lỗi nào để phát hiện. Khách hỏi
vé đi Quy Nhơn, hệ thống tra Quảng Ninh, bot trả lời rất tự tin.

Một mẻ ở `temperature` 0.7 không kết luận được gì: mẻ chạy dở ngay trước đó Gemini đạt F1 1.000
trên cả 8 tool và không sai ca này. Nên phải hỏi đúng câu: **tái lập được không, và ở nhiệt độ nào.**

**Giả thuyết.** Quy Nhơn không có trong bảng mã điểm nhồi vào prompt. Khi thiếu mã đúng, model
chọn thứ *trông giống nhất* thay vì nói chưa hỗ trợ — và "QNH" giống "Quy Nhơn" ở ba chữ cái đầu.
Nếu đúng vậy thì đây là xu hướng có hệ thống chứ không phải rủi ro sampling, nên **sẽ tái lập cả ở
`temperature` 0**.

Đoán thêm: qwen3.5:9b tránh được không phải vì giỏi hơn, mà vì nó thiên về *bỏ trống tham số* —
đúng kiểu lỗi "thiếu chứ không sai" đã thấy ở mục (b).

**Thay đổi.** Không sửa gì trong sản phẩm. Thêm một test thăm dò tách riêng trong
`ToolSelectionQualityTest` (bật bằng `TOOL_EVAL_PROBE`), chạy ĐÚNG một ca lặp nhiều lần và in ra
giá trị tham số của từng lần. Tách khỏi test chính vì nó không có ngưỡng và không nên làm bẩn bảng
điểm.

**Cách đo.** 12 lần mỗi nhiệt độ, `temperature` 0.7 (bản production) và 0.0, trên Gemini và trên
`qwen3.5:9b`. Gemini tốn khoảng 48 lượt; qwen miễn phí.

**Đọc kết quả thế nào** — chốt TRƯỚC khi chạy, để không nhìn số rồi mới nới:

- **≥ 3/12 ở `temperature` 0.7** → lỗi tái lập được. Mở một mục riêng để sửa bằng prompt (thêm
  ràng buộc: không có mã trong bảng thì nói chưa hỗ trợ, tuyệt đối không suy ra mã gần giống), rồi
  đo lại bằng chính bộ này.
- **1–2/12** → hiếm nhưng có thật. Ghi vào phần điểm yếu đang mở, chưa sửa vội.
- **0/12** → mẻ ngày 16/09 là ngoại lệ. Ghi lại là "đã thấy một lần", không kết luận gì thêm.
- **Bịa ở `temperature` 0** nặng hơn hẳn bịa ở 0.7: ở 0 thì không còn đổ cho ngẫu nhiên được, đó
  là lựa chọn đầu bảng của model.

**Kết quả** (16/09, 12 lần mỗi ô).

| Model | Nhiệt độ | Truyền `QNH` | Hành vi áp đảo |
|---|---|---|---|
| gemini-flash-lite | 0.7 | **2/12** | `destination=UIH` 10/12 |
| gemini-flash-lite | 0.0 | **0/12** | `destination=UIH` 12/12 |
| qwen3.5:9b Q4 | 0.7 | 0/12 | không gọi tool lần nào |
| qwen3.5:9b Q4 | 0.0 | 0/12 | không gọi tool lần nào |

**Theo tiêu chí đã chốt: rơi vào vùng 1–2/12 — hiếm nhưng có thật.** Nghĩa là KHÔNG mở mục sửa
prompt chỉ vì `QNH`. Ghi vào phần điểm yếu đang mở và đi tiếp.

**Giả thuyết sai.** Đoán lỗi sẽ tái lập cả ở `temperature` 0 vì đó là xu hướng có hệ thống. Thực
tế `temperature` 0 cho **0/12**: `QNH` không phải lựa chọn đầu bảng của model, nó là thứ chỉ xuất
hiện khi sampling đi chệch. Đọc lệch chỗ này thì đã đi sửa nhầm bệnh.

**Nhưng probe lộ ra một lỗi khác, lớn hơn hẳn, mà tiêu chí ở trên không hỏi tới.**

Hành vi áp đảo không phải `QNH` mà là **`destination=UIH`** — 10/12 ở nhiệt độ 0.7 và **12/12 ở
nhiệt độ 0**. `UIH` là mã IATA thật của sân bay Phù Cát, Quy Nhơn. Tức là model **đúng về thế giới
nhưng sai về hệ thống**: nó lấy kiến thức có sẵn ra dùng, mà `UIH` không nằm trong danh sách mã
đang hoạt động (`HAN, SGN, DAD, HPH, HUE, VIN, SAP, QNH, NTR, DLT, PQC, VCL`).

Hai hệ quả:

1. **Ca đo này chấm thiếu.** `forbid` chỉ cấm đúng `QNH`, nên 12/12 lần truyền `UIH` đều được
   tính là *đạt*. Cây thước bỏ lọt hành vi xảy ra gần như mọi lần, và chỉ bắt được biến thể hiếm.
2. **Cơ chế sinh ra `QNH` giờ đã rõ.** Lần thứ 12 ở nhiệt độ 0.7 gọi `search_trips` **hai lần**:
   `UIH` trước, rồi `QNH` sau. Model thử mã đúng ngoài đời, không ra chuyến nào, rồi **lùi về mã
   trông giống nhất trong danh sách được phép**. `QNH` không phải nhầm lẫn ngẫu nhiên — nó là bước
   lùi sau khi `UIH` thất bại. Điều đó cũng giải thích vì sao ở nhiệt độ 0 không thấy: ở đó model
   không đi tới vòng thứ hai.

**Nguyên nhân gốc, đọc thẳng từ prompt** (`ChatService.toolUsageGuide`, `ChatService.java:808`):
danh sách nhồi vào là **mã trần, không kèm tên tỉnh**, kèm đúng một ví dụ, và **không có luật cho
trường hợp tỉnh khách hỏi không có trong bảng**. Model không có cách nào biết `QNH` là Quảng Ninh,
cũng không được phép nói "chưa hỗ trợ". Thêm một chuyện nhỏ: `activeLocations` là `HashSet`
(`ChatService.java:944`) nên thứ tự mã đổi mỗi lần khởi động — prompt đổi mà không ai chủ ý đổi.

**qwen3.5:9b không gọi tool lần nào**, ở cả hai nhiệt độ. Theo ghi chú của ca đo thì đó là hành vi
chấp nhận được. Nhưng đừng đọc thành "qwen cẩn thận hơn": nó khớp đúng kiểu lỗi đã thấy ở mục (b)
— thiên về **không hành động** khi thiếu thông tin. Cùng một thiên hướng, ở ca này thành ra đúng,
ở ca `"tối nay"` thành ra bỏ trống `departureDate`. Probe không ghi lại phần trả lời bằng chữ nên
**chưa biết nó có nói với khách là chưa hỗ trợ hay không** — đó là câu hỏi còn mở.

**Kết luận.**

1. Câu hỏi ban đầu — `QNH` có tái lập không — trả lời xong: **2/12 ở nhiệt độ production, 0/12 ở
   nhiệt độ 0.** Hiếm nhưng có thật. Theo tiêu chí đã chốt thì chưa đủ để mở mục sửa.
2. Nhưng probe trả lời luôn một câu chưa ai hỏi, và câu đó mới đáng sửa: **model truyền mã điểm
   không tồn tại trong hệ thống ở gần như 100% số lần**, và bộ đo hiện tại không bắt được.
3. Việc tiếp theo KHÔNG phải sửa prompt ngay, mà là **sửa cây thước trước**: thêm ràng buộc
   `destination` phải nằm trong danh sách mã đang hoạt động vào ca này. Có thước đo đúng rồi mới
   đo được prompt mới có tốt hơn không. Sửa prompt trước thì lại rơi vào đúng cái bẫy "đổi rồi
   tin là tốt hơn" mà cả dự án này dựng lên để tránh.
4. Đã đọc `ChatService.handleToolCall` (`ChatService.java:109`): **mã điểm không được kiểm tra
   gì cả** — `destination` lấy thẳng từ tham số model truyền rồi đưa vào truy vấn. Mã lạ thì
   không khớp tuyến nào, trả rỗng êm đẹp, không ngoại lệ. Nhưng nó còn được **ghi vào
   `sessionCache`** (`ChatService.java:184`), nên một mã bịa còn đọng lại làm điểm đến mặc định
   cho các lượt hỏi sau trong cùng phiên.

   Mở ra một hướng sửa mạnh hơn sửa prompt: **chặn ở code**. Mã không nằm trong danh sách đang
   hoạt động thì trả về cho model một câu kiểu "mã này không có trong hệ thống, các mã đang có
   là …" thay vì một kết quả rỗng vô nghĩa. Model đọc câu đó rồi tự nói lại với khách. Prompt
   là lời khuyên, kiểm tra ở code là ràng buộc — và ràng buộc thì không phụ thuộc nhiệt độ.


## 2026-09-16 (d) — Sửa cây thước: chấm mã điểm theo luật, không theo danh sách cấm

**Vì sao.** Mục (c) cho thấy ca Quy Nhơn cấm đúng một chuỗi `QNH`, nên bộ đo chấm ĐẠT cho 12/12
lần model truyền `UIH`. Cấm theo từng giá trị chỉ bắt được những gì mình đã nghĩ ra trước — mà cái
model làm lại là thứ không ai nghĩ tới. Đây là việc phải làm TRƯỚC khi sửa prompt: không có thước
đúng thì sửa xong cũng không biết có tốt hơn không.

**Thay đổi** (chỉ trong test, không đụng sản phẩm):

- `ACTIVE_CODES` — tách sẵn đúng tập mã mà prompt nói là "đang hoạt động".
- Luật áp cho **cả 53 ca**: `search_trips` nhận `origin` hoặc `destination` không nằm trong tập đó
  thì đếm là **mã lạ**, in kèm giá trị thật và cả danh sách mã đang có.
- Hai cột mới trong bảng chính: `Cấm` và `Mã lạ`. `forbidHits` trước đây được tính nhưng không in
  ra bảng, phải đọc dòng chi tiết mới thấy.
- Ngưỡng `maLaHits == 0`, cùng hạng với `forbidHits`.

Kiểm tra trước để chắc luật mới không tạo báo động giả: quét toàn bộ `tool-eval.yml`, mọi giá trị
`origin`/`destination` trong `args` và `forbid` đều nằm trong tập mã. Không ca nào bị oan.

**Kết quả — thước mới bắt đúng thứ nó sinh ra để bắt.** Ca Quy Nhơn, Gemini:

```
MÃ KHÔNG CÓ TRONG HỆ THỐNG: destination = UIH (đang hoạt động: HAN, SGN, DAD, ...)
```

và bộ đo **đỏ**: `gemini · vi` truyền 1 lần mã không có trong hệ thống, ngưỡng 0. Đúng ý đồ — lỗi
có thật thì cây thước phải kêu, và test đỏ chính là phiếu việc. Bộ đo live chỉ chạy khi có
`TOOL_EVAL_LIVE=1` nên CI thường vẫn xanh.

**Nhưng mẻ này còn trả lời một câu quan trọng hơn: hai model sát nhau đến mức một mẻ đo không xếp
hạng được.** Giờ đã có ba mẻ trên cùng bộ 53 ca, cùng `temperature` 0.7:

| | Khớp bộ (gộp) | Args | Cấm | Mã lạ |
|---|---|---|---|---|
| Gemini · mẻ A | mọi tool F1 1.000 | — | 0 | (chưa đo) |
| Gemini · mẻ B | 98.1% | 98.1% | **3** (`QNH`) | (chưa đo) |
| Gemini · mẻ C | **100%** | 98.1% | 0 | **1** (`UIH`) |
| qwen · mẻ B | 98.1% | 98.1% | 0 | (chưa đo) |
| qwen · mẻ C | **92.5%** | **86.5%** | **1** (`QNH`) | 0 |

Hai điều rút ra, và điều thứ hai đắt hơn:

1. **Đính chính mục (b).** Câu "qwen không bịa tham số, Gemini bịa" không đứng vững — mẻ C ngược
   hẳn: qwen truyền `QNH`, Gemini thì không. Cái còn đúng là **cả hai đều mắc**. Mục (b) đã ghi
   sẵn điều kiện "một mẻ không nói được về độ ổn định"; giờ có số để chứng minh điều kiện đó
   không phải lời rào đón.
2. **Chênh lệch giữa hai mẻ của CÙNG một model lớn hơn chênh lệch giữa hai model.** qwen tụt từ
   98.1% xuống 92.5% khớp bộ và 98.1% xuống 86.5% Args, chỉ vì chạy lại. Nên mọi so sánh
   "model X hơn model Y bao nhiêu điểm" trên một mẻ ở `temperature` 0.7 đều **không đọc được**.

**Kết luận.**

1. Cây thước đã sửa và đã chứng minh bắt được thứ trước đây lọt lưới.
2. Kết luận tuần 10 giữ nguyên ở mức đã phát biểu: qwen **ngang** Gemini về chọn tool, đủ làm
   đường lui cho `CHAT`. Không được đọc mạnh hơn thế — cụ thể là không được nói model nào ít bịa
   tham số hơn.
3. **Việc tiếp theo không phải sửa prompt mà là sửa cách đo**: chạy bộ đo N mẻ rồi lấy trung
   bình và khoảng, hoặc hạ `temperature` về 0 cho bảng so sánh (và giữ 0.7 cho bảng "khách hàng
   đang gặp gì"). Chưa làm thì mọi con số so model đều chỉ là một mẫu.
4. Sau đó mới tới sửa `search_trips`: chặn mã lạ ngay ở `ChatService.handleToolCall` thay vì để
   truy vấn trả rỗng — xem mục (c) điểm 4.


## 2026-09-16 (e) — Chạy N mẻ: trung bình đi kèm khoảng

**Vì sao.** Mục (d) cho thấy chênh lệch giữa hai mẻ của cùng một model lớn hơn chênh lệch giữa hai
model. Mọi so sánh trên một mẻ vì thế không đọc được, kể cả so sánh để quyết định có sửa prompt hay
không. Phải sửa cách đo trước khi đo thêm bất cứ thứ gì.

**Thay đổi** (chỉ trong test):

- `TOOL_EVAL_RUNS=N` — chạy cả 53 ca N mẻ cho mỗi nhà cung cấp.
- Bảng chính thành **trung bình**, thêm bảng **Độ tản** in khoảng nhỏ nhất–lớn nhất.
- Quy tắc gộp cố ý khác nhau: tỉ lệ lấy **trung bình** ("thường đúng bao nhiêu phần trăm" chỉ có
  nghĩa trên nhiều mẻ), còn `Cấm` và `Mã lạ` lấy **TỔNG** — ở đó câu hỏi không phải "thường xuyên
  đến đâu" mà là "có xảy ra không". Một lần tra sai tỉnh là một lần khách bị trả lời sai.
- Chi tiết ca lỗi gộp lại kèm tần suất `[2/5 mẻ]`, phân biệt được lỗi luôn xảy ra với lỗi thỉnh
  thoảng — thông tin mà một mẻ đơn không thể có.
- **Throttle 4 giây chỉ áp cho nhà cung cấp TỪ XA.** Model local không có hạn mức để tôn trọng, mà
  4 giây × 53 ca × 5 mẻ là 18 phút chờ vô nghĩa — đủ để làm người ta ngại chạy lại, tức là đủ để
  giết chính cái kỷ luật vừa dựng lên.

**Kết quả** (16/09, `qwen3.5:9b` Q4, `temperature` 0.7, 5 mẻ = 265 lượt chấm ca, 22 phút).

| Cấu hình | Khớp bộ (tb) | Khoảng | Args (tb) | Khoảng | Cấm | Mã lạ |
|---|---|---|---|---|---|---|
| ollama · vi (29 ca) | 95.9% | 89.7 – 100% | 93.1% | 87.5 – 96.9% | 0 | 0 |
| ollama · en (12 ca) | 91.7% | 91.7 – 91.7% | 100% | 100 – 100% | 0 | 0 |
| ollama · ja (6 ca) | 100% | 100 – 100% | 86.7% | 83.3 – 100% | 0 | 0 |
| ollama · zh (6 ca) | 100% | 100 – 100% | 90.0% | 75.0 – 100% | 0 | 0 |
| **ollama · gộp** | **95.8%** | **92.5 – 98.1%** | **93.5%** | **90.4 – 96.2%** | **0** | **0** |

Ba điều đọc được, không điều nào thấy được từ một mẻ:

1. **Hai con số gây tranh cãi hôm nay là hai đầu của cùng một khoảng.** Mẻ B cho 98.1% và mẻ C cho
   92.5%; năm mẻ nói sự thật là **95.8%, khoảng 92.5–98.1%**. Không có "qwen tụt hẳn ở mẻ C" — chỉ
   có một model dao động ±3 điểm, và hai lần bốc mẫu rơi đúng hai đầu.
2. **`Cấm` 0 và `Mã lạ` 0 trên 265 lượt chấm.** Lần qwen truyền `QNH` ở mẻ C là một lần hiếm, không
   phải xu hướng. Đối chiếu thăm dò mục (c): Gemini truyền `UIH` **12/12 ở `temperature` 0**. Trên
   trục bịa mã điểm, hai model **không giống nhau** — nhưng muốn phát biểu tử tế thì còn thiếu N mẻ
   của Gemini.
3. **Số theo từng ngôn ngữ trên 6 ca gần như vô nghĩa.** `zh` có Args dao động 75–100%, `ja` 83–100%
   — với 6 ca thì một ca lệch đã là 16.7 điểm. Bảng gộp 53 ca dao động 5.6 điểm, hẹp hơn nhiều. Bài
   học cũ của bộ đo RAG lặp lại: mẫu số nhỏ thì đừng đọc con số, hãy đọc khoảng.

**Chưa làm được hôm nay.** N mẻ cho Gemini tốn 5 × 105 = 525 lượt, vượt hạn mức ngày 500 mà hôm nay
đã dùng khoảng 400 (ba lần chạy 53 ca cộng 48 lượt thăm dò). Để sang ngày sau. Khi chạy thì chạy cả
`temperature` 0 để tách phần dao động do sampling khỏi phần do model.

**Kết luận.**

1. Cách đo đã sửa: mọi bảng so model từ nay phải là N mẻ, trung bình kèm khoảng. Một mẻ chỉ dùng
   để xem hệ thống còn chạy, không dùng để so.
2. `qwen3.5:9b` chọn tool **95.8% khớp bộ, khoảng 92.5–98.1%** trên 5 mẻ. Đây là con số thay cho
   mọi con số một mẻ đã ghi ở mục (b) và (d).
3. Còn nợ: N mẻ của Gemini. Trước khi có nó, **không được phát biểu model nào hơn model nào** —
   kể cả theo hướng có lợi cho kết luận tuần 10.
4. Sau đó mới tới sửa `ChatService` chặn mã lạ, và đo bản sửa bằng chính cách đo này.

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
| ~~Bảng live Java sau khi port Bù BM25~~ | Xong 15/09 từ cache đĩa: 20 dòng Vector/Hybrid và 10 dòng BM25 trùng từng chữ số, 0 lời gọi API |
| `docs/CHATBOT_AI.md` bên WebProject | Mục 5.6, 8.6, sơ đồ và bảng số vẫn tả RRF — tài liệu đồ án, cập nhật khi nào? |
| Nhóm hủy vé ↔ hoàn tiền | Nguyên nhân lớn nhất (7/25 câu sai hạng 1). Golden mới có 2 câu thuộc nhóm — thêm câu vào golden TRƯỚC, rồi mới so cách sửa (reranker, viết lại title/content chunk) trên golden, xác nhận trên holdout một lần |
| Cái giá thật của khoá có dấu | Thêm vào bộ vàng câu gõ không dấu mà chunk đúng KHÔNG chứa chữ "chó", để đo phần mở rộng bị mất |
| Hai câu vi trượt khi lọc lang | "bao lâu thì tiền về tài khoản" → refund-processing-time, "web này trả tiền bằng cách nào" → payment-methods (nhánh BM25). Khoảng trống từ vựng hay do chunk viết khác cách hỏi |
| ~~Cross-encoder rerank trên top-20~~ | Hoãn 14/09: quyết định không dùng (mục "Reranker: không dùng, không đo"). Mở lại nếu tuần 9 cho thấy lỗi do chunk đúng vắng mặt khỏi top-4 |
| Chunk size, overlap, title trong phần đem nhúng | Cấu hình nào cho R@3 cao nhất, trả giá bao nhiêu độ trễ |
