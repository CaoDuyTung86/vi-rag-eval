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
| Đối chiếu live với Java | Chạy `RAG_EVAL_LIVE` bên WebProject, so với bảng live ở trên |
| Port sang Java | Khoá `chó` có dấu (`SynonymExpander.java`), "Vector trước" khi hợp nhất (`HybridRetriever.java`), hai câu mới vào `rag-eval.yml`. Sau khi port, bảng BM25 Java và Python phải trùng từng chữ số trở lại |
| Hai câu thua RRF thật, một câu en mới sai | "đi tàu có được mang vali to không" (`pets-train` chen lên nhờ khoá `vali`?), "web này trả tiền bằng cách nào", "i want to cancel and get my money back". Mỗi câu: chunk nào chen lên, vì sao |
| Cái giá thật của khoá có dấu | Thêm vào bộ vàng câu gõ không dấu mà chunk đúng KHÔNG chứa chữ "chó", để đo phần mở rộng bị mất |
| Hai câu vi trượt khi lọc lang | "bao lâu thì tiền về tài khoản" → refund-processing-time, "web này trả tiền bằng cách nào" → payment-methods. Khoảng trống từ vựng hay do chunk viết khác cách hỏi |
| Cross-encoder rerank trên top-20 | Delta R@3 có đáng với delta độ trễ không — đặt ngân sách độ trễ TRƯỚC khi đo |
| Chunk size, overlap, title trong phần đem nhúng | Cấu hình nào cho R@3 cao nhất, trả giá bao nhiêu độ trễ |
| nDCG@5 | Có xếp lại thứ tự ưu tiên sửa lỗi so với recall@3 không |
| Tách điểm theo category | Category nào yếu nhất, và vì sao |
