"""Mạng numpy của learn/mnist.py. Không tải MNIST — mọi test chạy trên dữ liệu tự sinh.

Test quan trọng nhất là gradient check: backprop viết tay rất dễ sai một dấu hay một chuyển
vị mà mạng VẪN học được chút ít, nên nhìn độ chính xác không phát hiện ra. So với đạo hàm
tính bằng sai phân thì phát hiện ngay.
"""

import numpy as np
import pytest

from learn.mnist import Network, Split, one_hot, train, weights_image, write_png


@pytest.mark.parametrize("act", ["sigmoid", "relu"])
@pytest.mark.parametrize("cost", ["mse", "ce"])
def test_backprop_khop_dao_ham_sai_phan(act, cost):
    rng = np.random.default_rng(1)
    net = Network([5, 4, 3, 3], act=act, cost=cost, seed=2)
    x = rng.normal(size=(7, 5))
    y = rng.integers(0, 3, size=7)
    for layer in range(len(net.weights)):
        net.biases[layer] += rng.normal(scale=0.1, size=net.biases[layer].shape)

    _, grads_w, grads_b = net.gradients(x, y)

    eps = 1e-6
    for params, grads in ((net.weights, grads_w), (net.biases, grads_b)):
        for param, grad in zip(params, grads, strict=True):
            numeric = np.zeros_like(param)
            for index in np.ndindex(param.shape):
                original = param[index]
                param[index] = original + eps
                plus = net.gradients(x, y)[0]
                param[index] = original - eps
                minus = net.gradients(x, y)[0]
                param[index] = original
                numeric[index] = (plus - minus) / (2 * eps)
            np.testing.assert_allclose(grad, numeric, rtol=1e-5, atol=1e-8)


def test_mang_3blue1brown_co_13002_tham_so():
    # 784·16 + 16·16 + 16·10 weight, cộng 16 + 16 + 10 bias — con số nói trong chương 1.
    assert Network([784, 16, 16, 10]).n_params == 13_002


def test_khoi_tao_khong_de_cac_neuron_giong_nhau():
    first = Network([784, 16, 16, 10]).weights[0]
    assert not np.allclose(first[0], first[1])


def test_one_hot():
    np.testing.assert_array_equal(one_hot(np.array([2, 0]), 3), [[0, 0, 1], [1, 0, 0]])


@pytest.mark.parametrize(("act", "cost", "lr"), [("sigmoid", "mse", 1.0), ("relu", "ce", 0.1)])
def test_hoc_duoc_ba_cum_diem_tach_roi(act, cost, lr):
    rng = np.random.default_rng(0)
    centers = np.array([[-3.0, 0.0], [3.0, 0.0], [0.0, 3.0]])
    y = rng.integers(0, 3, size=600)
    x = centers[y] + rng.normal(scale=0.5, size=(600, 2))
    data = Split(x, y)
    net = Network([2, 8, 3], act=act, cost=cost, seed=0)

    history = train(net, data, data, epochs=20, lr=lr, batch_size=16)

    assert history[-1].train_loss < history[0].train_loss
    assert history[-1].val_accuracy > 0.95


def test_anh_trong_so_va_png(tmp_path):
    net = Network([784, 16, 10])
    image = weights_image(net, scale=2, pad=1)
    # 16 neuron xếp lưới 4×4, mỗi ô 56 px, cách nhau 1 px, 3 kênh màu.
    assert image.shape == (4 * 57 + 1, 4 * 57 + 1, 3)

    path = tmp_path / "w.png"
    write_png(path, image)
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(data[16:20], "big") == image.shape[1]
    assert int.from_bytes(data[20:24], "big") == image.shape[0]
    assert data[25] == 2  # color type RGB


def test_mang_chua_train_thi_anh_da_hoc_trang_tron():
    image = weights_image(Network([784, 16, 10]), since_init=True, scale=1, pad=0)
    assert (image == 255).all()


def test_trong_so_noi_tu_pixel_luon_toi_khong_bao_gio_doi():
    # Viền ảnh MNIST luôn bằng 0, nên gradient của trọng số nối từ đó = delta · 0 = 0.
    # Chúng giữ nguyên giá trị ngẫu nhiên lúc khởi tạo — lớp đốm nhiễu quanh viền ảnh thô.
    rng = np.random.default_rng(0)
    x = rng.random((200, 784))
    x[:, :28] = 0.0
    y = rng.integers(0, 10, size=200)
    net = Network([784, 16, 10])

    train(net, Split(x, y), Split(x, y), epochs=2, lr=1.0)

    np.testing.assert_array_equal(net.weights[0][:, :28], net.initial_weights[0][:, :28])
    assert not np.allclose(net.weights[0][:, 28:], net.initial_weights[0][:, 28:])
