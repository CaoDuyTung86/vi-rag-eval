# Tuần 4 — mạng nơ-ron bằng numpy

Mạng trong series Deep learning của 3Blue1Brown, viết lại bằng numpy thuần:
[`mnist.py`](mnist.py). Test gradient check nằm ở [`tests/test_mnist.py`](../tests/test_mnist.py).

```bash
python -m learn.mnist                        # 784-16-16-10, sigmoid, MSE — đúng như video
python -m learn.mnist --hidden 100           # thử cấu hình khác
```

Lần chạy đầu tải `mnist.npz` (~11 MB) vào `cache/mnist/`. Ảnh trọng số ghi ra `learn/out/`.
Cả hai đều bị gitignore.

## Dự đoán — viết TRƯỚC khi chạy

Cùng 10 epoch, lô 32, seed 0. Con số là độ chính xác trên validation.

| Cấu hình | Dự đoán | Lý do |
|---|---|---|
| 784-10, không lớp ẩn | ~92% | Chỉ là 10 "khuôn mẫu" pixel, không tổ hợp được nét |
| **784-16-16-10**, sigmoid, MSE | ~94–95% | Mạng trong video |
| 784-16-16-10, ReLU, cross-entropy | ~95–96% | Cùng số tham số, cách train tốt hơn |
| 784-32-10 | ~95–96% | Rộng hơn, ít tầng hơn |
| 784-100-10 | ~97% | Gấp 6 lần tham số |
| 784-16-16-16-16-10, sigmoid | không hơn 16-16, có thể kém | Sigmoid làm gradient teo qua mỗi lớp |
| 784-16-16-10, lr × 10 | loss nhảy hoặc kẹt | Bước quá dài, nhảy qua đáy |
| 784-16-16-10, lr ÷ 10 | thấp hơn vài % | 10 epoch chưa đủ đi tới đáy |

Ảnh 16 neuron lớp ẩn đầu: **không** giống nét thẳng hay nét cong, trông lốm đốm.

## Kết quả — 14/09/2026, CPU i5-12500H

| Cấu hình | Tham số | Val | Test | Thời gian | So với dự đoán |
|---|---|---|---|---|---|
| 784-10, không lớp ẩn | 7.850 | 92.37% | 91.73% | 1.4s | đúng |
| **784-16-16-10**, sigmoid, MSE | 13.002 | 94.91% | 94.46% | 2.5s | đúng |
| — cùng cấu hình, seed 1 / seed 2 | | 95.18% / 95.16% | 94.70% / 94.38% | | |
| — cùng cấu hình, 30 epoch | | 95.26% | 94.92% | 10.9s | |
| 784-16-16-10, ReLU, cross-entropy | 13.002 | 94.62% | 94.32% | 2.1s | **sai** — không hơn |
| 784-32-10 | 25.450 | 96.20% | 95.92% | 4.1s | đúng |
| 784-100-10 | 79.510 | 97.27% | 97.20% | 18.8s | đúng |
| 784-16-16-16-16-10, sigmoid | 13.546 | 92.90% | 92.07% | 3.3s | đúng — kém hơn |
| 784-16-16-10, lr 10 | 13.002 | 93.13% | 92.14% | 2.3s | **sai một nửa** — kém nhưng không nổ |
| 784-16-16-10, lr 0.1 | 13.002 | 92.01% | 91.53% | 2.3s | đúng |

Đọc bảng:

- **Đổi seed xê dịch khoảng 0.3%.** Chênh lệch nhỏ hơn mức đó chưa nói lên gì — bài học dùng
  lại được cho bảng RAG, nơi mỗi câu hỏi tiếng Việt là 1.75%.
- **16-16 không phải cấu hình tốt nhất.** Một lớp 32 neuron hơn nó 1.3%; bốn lớp 16 kém nó 2%.
  Train lâu gấp 3 chỉ thêm 0.35%: mạng đã chạm trần sức chứa.
- **ReLU + cross-entropy không thắng** ở mạng nhỏ và 10 epoch này. Lợi thế của nó lộ ra ở mạng
  sâu; ở đây lr 0.1 cũng chưa được dò.
- **Ảnh trọng số** (`learn/out/weights-784-16-16-10-sigmoid-mse.png`): phần lớn lốm đốm như dự
  đoán, nhưng vài neuron trông giống một vệt ngắn xiên — gần với "nét" hơn tôi nghĩ. Không
  neuron nào là một nét sạch như hình minh hoạ trong video.

## Đọc ảnh trọng số

Mỗi lần chạy ghi hai ảnh vào `learn/out/`. Mỗi ô 28×28 là 784 trọng số đi vào một neuron của lớp
ẩn đầu: **đỏ** — pixel đó sáng thì neuron sáng lên, **xanh** — pixel đó sáng thì neuron tối đi,
**trắng** — không ảnh hưởng.

- `weights-….png`: trọng số thô.
- `weights-…-da-hoc.png`: trọng số trừ đi giá trị lúc khởi tạo — chỉ phần mạng đã học được.

Vì sao ảnh thô lẫn đốm quanh viền: 67/784 pixel tối ở MỌI ảnh train. Gradient của trọng số nối
từ pixel đó là `delta · 0 = 0`, nên chúng giữ nguyên giá trị ngẫu nhiên lúc khởi tạo mãi mãi. Rất
nhiều pixel viền khác chỉ sáng ở vài ảnh, nên cũng gần như không học. Ảnh "đã học" có viền trắng
sạch. Test `test_trong_so_noi_tu_pixel_luon_toi_khong_bao_gio_doi` chốt đúng điều này.

Phần giữa vẫn lốm đốm, và điều đó là thật: mỗi neuron học một tổ hợp rải rác của nhiều vùng,
không phải một nét gọn — đúng điều chương 2 của video nói về hy vọng "lớp 1 bắt nét".
