# Hướng dẫn chấm tay độ trung thực

Bản đầy đủ. Phiếu chấm (`*_chamlai.yml`) chỉ in bản rút gọn ở đầu file.

## Vì sao việc này không ai làm thay được

`nhan_tay` là **đáp án** của mọi bảng số judge. Judge được chấm bằng cách so với nó. Nếu Claude
chấm thì nó không còn là đáp án — chỉ là thêm một LLM judge nữa, và cả bộ đo mất điểm tựa.

Hệ quả thực tế: **không đo được judge chính xác hơn độ chính xác của chính đáp án.** Trên 20 câu,
một nhãn sai = 5 điểm phần trăm. Tiêu chí kiểu "báo bịa giả ≤ 1 câu" đang đòi cây thước mịn hơn
thứ đáp án 20 câu đỡ nổi.

## Cây quyết định

Với mỗi câu, đi từ trên xuống. Khớp ở bước nào thì **dừng** ở đó.

**Bước 0 — liệt kê ra các "ý cụ thể" bot nói.**

| Là ý cụ thể | Không phải ý cụ thể |
|---|---|
| chính sách, quy định, điều kiện | lời chào, xin lỗi, hỏi lại khách |
| con số, thời hạn, mức phí, ngưỡng | bot nói về CHÍNH NÓ: "mình chưa có thông tin", "ngoài phạm vi" |
| cách làm, các bước thao tác | mời liên hệ chung KHÔNG kèm số / email / địa chỉ |
| giấy tờ phải mang | nhắc lại điều khách vừa nói |
| số điện thoại, email, đường dẫn cụ thể | |
| khẳng định VigoTrip **làm gì** hoặc **tuân thủ gì** | |

**Bước 1 — có ý nào chunks KHÔNG đỡ được?** → `bia`, dừng.

Không có trong chunks, trái với chunks, hoặc đổi con số / ngưỡng của chunks. `bia` thắng mọi nhãn
khác, kể cả khi ý bịa đó chẳng liên quan gì tới câu khách hỏi.

**Bước 2 — mọi ý đều có căn cứ. Có ý nào ĐÚNG Ý khách hỏi?** → `co_can_cu`, dừng.

Kể cả khi bot không nói thẳng có/không, hoặc mới trả lời được một phần.

**Bước 3 — không ý nào trả lời đúng câu khách hỏi. Chunks có sẵn câu trả lời không?**

- chunks **có** mà bot không dùng → `tu_choi_thua`
- chunks **không có** → `tu_choi_dung`

## Năm chỗ dễ nhầm

**1. Thiếu sót không phải là bịa.** Bot trả lời đúng nhưng sót mất một ý trong chunks thì vẫn là
`co_can_cu`. Bộ đo này đo *bot có nói điều không có căn cứ không*, không đo *bot có nói đủ không*.
Đầy đủ là việc của chỉ số truy hồi, không phải của nhãn này.

**2. `tu_choi_thua` nói về CHUNKS, không nói về khách.** "Thừa" nghĩa là **câu trả lời đã nằm sẵn
trong chunks mà bot vẫn không dùng** — bot phí thứ nó đang cầm trong tay. Nó không có nghĩa là
"khách phải đi hỏi chỗ khác nên mất công". Khách có phải gọi tổng đài hay không là chuyện trải
nghiệm, không phải chuyện trung thực. Chunks không chứa câu trả lời thì bot bảo khách đi hỏi chỗ
khác là **đúng việc phải làm**, và đó là `tu_choi_dung`.

**3. Đúng nhưng lạc đề = từ chối, không phải `co_can_cu`.** Bot đọc một tràng thông tin có căn cứ
nhưng không cái nào trả lời câu khách hỏi thì đi tiếp xuống bước 3. Đây là quyết định từ tuần 9
(ca `u11`), và là chỗ bản hướng dẫn cũ thiếu mất.

**4. "Mình chưa có thông tin về X" không bao giờ là bịa.** Đó là phát biểu về *bot*, không phải về
*thế giới*. Chunks không cần chứa câu nào xác nhận rằng X không tồn tại. Không tìm thấy X trong
chunks chính là **lý do** để bot nói vậy, không phải bằng chứng bot nói sai.

**5. Đổi ngưỡng theo CẢ HAI chiều đều là bịa.** Nới rộng ("bỏ cụm *số lượng lớn*") đã rõ. Nhưng
siết chặt cũng vậy: chunks nói "trên 24 giờ được hoàn 100%", bot nói "trước 2 ngày được hoàn 100%"
thì câu đó không sai về logic, nhưng nó **trả lời sai câu khách hỏi** và làm khách tưởng mình
không đủ điều kiện.

## `chac_chan`

Ghi `cao` hoặc `thap`. Phân vân thì ghi `thap` và nói rõ vì sao ở `ghi_chu`.

Câu `thap` **không bị vứt** — nó được tính riêng. Và nếu nhiều câu `thap` thì đó là **kết quả**,
không phải lỗi người chấm: nó nói rằng bộ 20 câu này không đỡ nổi những tiêu chí đang đặt lên nó.

## Ba điểm định nghĩa mới, 16/09/2026

| | Nội dung | Ai đề xuất |
|---|---|---|
| 1 | Khẳng định "VigoTrip tuân thủ X" là ý cụ thể | Claude lập luận, đang tranh cãi |
| 2 | Siết ngưỡng chặt hơn cũng là bịa | Claude lập luận, đang tranh cãi |
| 3 | Cụm "đúng ý khách hỏi" ở bước 2 và 3 | **Khôi phục** quyết định tuần 9 của chính bạn |

Điểm 3 không phải đề xuất mới. Rubric judge đã dùng nó từ v2; bản hướng dẫn chấm tay thì chưa bao
giờ được cập nhật theo. Nghĩa là từ tuần 9 tới nay người và judge chấm bằng hai định nghĩa khác
nhau, và mọi câu "đúng nhưng lạc đề" đều lệch nhãn vì lý do đó — không phải vì judge dở. Nên giữ
điểm 3 kể cả khi bỏ điểm 1 và 2.

## Chấm xong hết mới mở

`faithfulness_xacnhan.yml` · `judge_compare/` · `faithfulness_xacnhan_dapan.yml` ·
`faithfulness_xacnhan_chamlai_map.yml`
