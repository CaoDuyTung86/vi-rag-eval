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
| Hybrid + lọc lang làm tụt P@1 tiếng Việt | Câu nào Vector xếp đúng hạng 1 nhưng RRF đẩy xuống, chunk nào của BM25 chen lên, và khoá đồng nghĩa nào gây ra. Thử trọng số RRF nghiêng về Vector hoặc bỏ hạn BM25 khi điểm thấp |
| Khoá đồng nghĩa `cho` | Giả thuyết: khoá `cho` (chó) va chạm với từ chức năng "cho" trong "**cho** tôi hỏi", đẩy chunk thú cưng lên. Câu "cho tôi hỏi được mang bao nhiêu kg lên máy bay" trượt ở cấu hình không lọc với top-5 có 3 chunk thú cưng. Bỏ khoá hoặc chỉ giữ dạng có dấu thì có sửa được mà không làm tụt câu hỏi thú cưng nào không |
| Hai câu vi trượt khi lọc lang | "bao lâu thì tiền về tài khoản" → refund-processing-time, "web này trả tiền bằng cách nào" → payment-methods. Khoảng trống từ vựng hay do chunk viết khác cách hỏi |
| Cross-encoder rerank trên top-20 | Delta R@3 có đáng với delta độ trễ không — đặt ngân sách độ trễ TRƯỚC khi đo |
| Chunk size, overlap, title trong phần đem nhúng | Cấu hình nào cho R@3 cao nhất, trả giá bao nhiêu độ trễ |
| nDCG@5 | Có xếp lại thứ tự ưu tiên sửa lỗi so với recall@3 không |
| Tách điểm theo category | Category nào yếu nhất, và vì sao |
