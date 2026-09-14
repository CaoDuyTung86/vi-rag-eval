"""Mạng nơ-ron viết bằng numpy thuần, train trên MNIST.

Mặc định là đúng mạng 784 → 16 → 16 → 10 trong series Deep learning của 3Blue1Brown: sigmoid
ở mọi lớp, cost là tổng bình phương sai số. Không PyTorch — mọi phép tính của backprop nằm
trong file này để đọc được từng dòng.

Ký hiệu theo chương 4 của video, cho lớp l:
    z(l) = W(l) · a(l-1) + b(l)        tổng có trọng số
    a(l) = σ(z(l))                     activation — con số mỗi neuron giữ

Chạy từ gốc repo:
    python -m learn.mnist                          # 784-16-16-10, sigmoid, MSE như video
    python -m learn.mnist --hidden 100             # 784-100-10
    python -m learn.mnist --hidden                 # 784-10, không có lớp ẩn
    python -m learn.mnist --act relu --cost ce     # cách người ta làm ngày nay
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

MNIST_URL = "https://storage.googleapis.com/tensorflow/tf-keras-datasets/mnist.npz"
MNIST_SHA256 = "731c5ac602752760c8e48fbffcf8c3b850d9dc2a2aedcf2cc48468fc17b673d1"
CACHE_DIR = Path("cache/mnist")
OUT_DIR = Path("learn/out")

# 10.000 ảnh cuối của tập train tách ra làm validation. Chọn learning rate, số neuron... bằng
# validation; tập test chỉ nhìn ở cuối. Nhìn test để chọn cấu hình là overfit lên test — cùng
# lý do bm25.py không cho tinh chỉnh K1, B trên bộ câu hỏi vàng.
VALIDATION_SIZE = 10_000


@dataclass(frozen=True, slots=True)
class Split:
    x: np.ndarray  # (n, 784), độ sáng pixel 0..1
    y: np.ndarray  # (n,), nhãn 0..9


def load_mnist(cache_dir: Path = CACHE_DIR) -> tuple[Split, Split, Split]:
    """(train 50k, validation 10k, test 10k). Tải một lần rồi đọc từ cache."""
    path = cache_dir / "mnist.npz"
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"Tải {MNIST_URL}")
        response = httpx.get(MNIST_URL, timeout=120, follow_redirects=True)
        response.raise_for_status()
        digest = hashlib.sha256(response.content).hexdigest()
        if digest != MNIST_SHA256:
            raise RuntimeError(f"mnist.npz sai checksum: {digest}")
        path.write_bytes(response.content)

    with np.load(path) as data:
        x_train, y_train = data["x_train"], data["y_train"]
        x_test, y_test = data["x_test"], data["y_test"]

    def flatten(images: np.ndarray) -> np.ndarray:
        # Ảnh 28×28 duỗi thành 784 con số — chính là lưới số trong video.
        return images.reshape(len(images), -1).astype(np.float64) / 255.0

    cut = len(x_train) - VALIDATION_SIZE
    return (
        Split(flatten(x_train[:cut]), y_train[:cut]),
        Split(flatten(x_train[cut:]), y_train[cut:]),
        Split(flatten(x_test), y_test),
    )


# ---------------------------------------------------------------- hàm kích hoạt và cost


def sigmoid(z: np.ndarray) -> np.ndarray:
    # Kẹp z để exp không tràn số; sigmoid(±500) đã là 0 hoặc 1 tuyệt đối.
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


def softmax(z: np.ndarray) -> np.ndarray:
    # Trừ max trước khi exp: kết quả không đổi, nhưng không tràn số.
    shifted = np.exp(z - z.max(axis=1, keepdims=True))
    return shifted / shifted.sum(axis=1, keepdims=True)


def one_hot(y: np.ndarray, classes: int) -> np.ndarray:
    """Nhãn 3 thành [0,0,0,1,0,0,0,0,0,0] — đầu ra mà mạng "nên" cho ra."""
    return np.eye(classes)[y]


# ---------------------------------------------------------------- mạng


class Network:
    """Mạng kết nối đầy đủ. sizes=[784, 16, 16, 10] là 4 lớp, 3 ma trận trọng số.

    act:  hàm kích hoạt ở lớp ẩn — "sigmoid" như video, hoặc "relu".
    cost: "mse" — sigmoid ở lớp ra, cost = tổng bình phương sai số, như video;
          "ce"  — softmax ở lớp ra, cost = cross-entropy, cách phân loại được làm ngày nay.
    """

    def __init__(
        self, sizes: list[int], act: str = "sigmoid", cost: str = "mse", seed: int = 0
    ) -> None:
        if act not in ("sigmoid", "relu") or cost not in ("mse", "ce"):
            raise ValueError(f"act={act!r}, cost={cost!r} không hỗ trợ")
        rng = np.random.default_rng(seed)
        self.sizes = list(sizes)
        self.act = act
        self.cost = cost
        # Khởi tạo ngẫu nhiên, phương sai 1/n_in (ReLU: 2/n_in). Khởi tạo toàn 0 thì mọi neuron
        # trong một lớp nhận cùng gradient và mãi mãi giống hệt nhau — 16 neuron thành 1.
        gain = 2.0 if act == "relu" else 1.0
        self.weights = [
            rng.normal(0.0, np.sqrt(gain / n_in), size=(n_out, n_in))
            for n_in, n_out in zip(sizes[:-1], sizes[1:], strict=True)
        ]
        self.biases = [np.zeros(n_out) for n_out in sizes[1:]]

    @property
    def n_params(self) -> int:
        """Số "núm vặn": mọi weight cộng mọi bias."""
        return sum(w.size + b.size for w, b in zip(self.weights, self.biases, strict=True))

    @property
    def name(self) -> str:
        return "-".join(str(n) for n in self.sizes)

    def _hidden(self, z: np.ndarray) -> np.ndarray:
        return sigmoid(z) if self.act == "sigmoid" else np.maximum(z, 0.0)

    def _hidden_slope(self, z: np.ndarray, a: np.ndarray) -> np.ndarray:
        """σ'(z). Sigmoid: a(1 − a), không quá 0.25 — nên qua mỗi lớp gradient teo ít nhất 4 lần.
        ReLU: 1 khi z > 0, còn lại 0."""
        return a * (1.0 - a) if self.act == "sigmoid" else (z > 0).astype(z.dtype)

    def forward(self, x: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """Lan truyền xuôi một lô ảnh. Trả về z và a của mọi lớp — backprop cần cả hai.

        x có dạng (số ảnh, 784); mỗi hàng là một ảnh, nên W·a viết thành a @ W.T.
        """
        zs: list[np.ndarray] = []
        activations = [x]
        last = len(self.weights) - 1
        for layer, (w, b) in enumerate(zip(self.weights, self.biases, strict=True)):
            z = activations[-1] @ w.T + b
            if layer < last:
                a = self._hidden(z)
            else:
                a = softmax(z) if self.cost == "ce" else sigmoid(z)
            zs.append(z)
            activations.append(a)
        return zs, activations

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Chữ số mạng đoán: neuron sáng nhất ở lớp ra."""
        return self.forward(x)[1][-1].argmax(axis=1)

    def gradients(
        self, x: np.ndarray, y: np.ndarray
    ) -> tuple[float, list[np.ndarray], list[np.ndarray]]:
        """Backpropagation: cost trung bình của lô, cùng ∂C/∂W và ∂C/∂b cho mọi lớp.

        delta(l) = ∂C/∂z(l) — "neuron này nên sáng hơn hay tối đi, bao nhiêu". Tính ở lớp ra
        trước, rồi đẩy ngược qua từng lớp bằng quy tắc dây chuyền.
        """
        zs, activations = self.forward(x)
        target = one_hot(y, self.sizes[-1])
        out = activations[-1]
        n = len(x)

        if self.cost == "ce":
            loss = float(-np.sum(target * np.log(out + 1e-12)) / n)
            # Softmax + cross-entropy triệt tiêu nhau đẹp đến mức đạo hàm chỉ còn (a − y).
            delta = (out - target) / n
        else:
            loss = float(np.sum((out - target) ** 2) / n)
            # C = Σ (a − y)²  →  ∂C/∂a = 2(a − y);  nhân σ'(z) = a(1 − a) để ra ∂C/∂z.
            delta = 2.0 * (out - target) * out * (1.0 - out) / n

        grads_w: list[np.ndarray] = [np.empty(0)] * len(self.weights)
        grads_b: list[np.ndarray] = [np.empty(0)] * len(self.weights)
        for layer in reversed(range(len(self.weights))):
            # ∂C/∂W(l) = delta(l) · a(l-1)ᵀ — weight nối với neuron trước càng sáng càng được
            # chỉnh mạnh. "Neurons that fire together wire together" trong chương 3.
            grads_w[layer] = delta.T @ activations[layer]
            grads_b[layer] = delta.sum(axis=0)
            if layer > 0:
                # Đẩy delta về lớp trước: qua ma trận trọng số (chuyển vị), rồi qua σ'.
                slope = self._hidden_slope(zs[layer - 1], activations[layer])
                delta = (delta @ self.weights[layer]) * slope
        return loss, grads_w, grads_b


def accuracy(net: Network, split: Split) -> float:
    return float(np.mean(net.predict(split.x) == split.y))


@dataclass(frozen=True, slots=True)
class Epoch:
    number: int
    train_loss: float
    val_accuracy: float
    seconds: float


def train(
    net: Network,
    train_split: Split,
    val_split: Split,
    *,
    epochs: int,
    lr: float,
    batch_size: int = 32,
    seed: int = 0,
    on_epoch: Callable[[Epoch], None] | None = None,
) -> list[Epoch]:
    """Stochastic gradient descent: xáo dữ liệu, cắt lô nhỏ, mỗi lô bước một bước ngược gradient.

    Dùng lô nhỏ thay vì cả 50.000 ảnh cho mỗi bước: gradient hơi nhiễu nhưng bước được hàng
    nghìn lần mỗi epoch — "người say đi xuống đồi" trong chương 2.
    """
    rng = np.random.default_rng(seed)
    history: list[Epoch] = []
    for number in range(1, epochs + 1):
        started = time.perf_counter()
        order = rng.permutation(len(train_split.y))
        total = 0.0
        for begin in range(0, len(order), batch_size):
            batch = order[begin : begin + batch_size]
            loss, grads_w, grads_b = net.gradients(train_split.x[batch], train_split.y[batch])
            for w, gw, b, gb in zip(net.weights, grads_w, net.biases, grads_b, strict=True):
                w -= lr * gw
                b -= lr * gb
            total += loss * len(batch)
        epoch = Epoch(
            number, total / len(order), accuracy(net, val_split), time.perf_counter() - started
        )
        history.append(epoch)
        if on_epoch is not None:
            on_epoch(epoch)
    return history


# ---------------------------------------------------------------- ảnh trọng số


def weights_image(net: Network, scale: int = 4, pad: int = 2) -> np.ndarray:
    """Lưới ảnh 28×28, mỗi ô là trọng số từ 784 pixel vào MỘT neuron của lớp đầu tiên.

    Xám = 0, trắng = dương (pixel đó sáng thì neuron sáng), đen = âm. Mỗi ô tự co giãn theo
    trị tuyệt đối lớn nhất của nó.
    """
    first = net.weights[0]
    count = first.shape[0]
    side = int(np.sqrt(first.shape[1]))
    cols = int(np.ceil(np.sqrt(count)))
    rows = int(np.ceil(count / cols))
    cell = side * scale
    canvas = np.full((rows * (cell + pad) + pad, cols * (cell + pad) + pad), 255, dtype=np.uint8)
    for index, row in enumerate(first):
        peak = np.abs(row).max() or 1.0
        tile = ((row / peak + 1.0) / 2.0 * 255.0).reshape(side, side)
        tile = np.kron(tile, np.ones((scale, scale))).astype(np.uint8)
        top = pad + (index // cols) * (cell + pad)
        left = pad + (index % cols) * (cell + pad)
        canvas[top : top + cell, left : left + cell] = tile
    return canvas


def write_png(path: Path, pixels: np.ndarray) -> None:
    """Ghi ảnh xám 8-bit ra PNG bằng zlib — đủ để khỏi thêm matplotlib/Pillow chỉ vì một ảnh."""
    height, width = pixels.shape

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + pixels[r].tobytes() for r in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------- dòng lệnh


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--hidden",
        type=int,
        nargs="*",
        default=[16, 16],
        help="số neuron từng lớp ẩn; để trống là không có lớp ẩn",
    )
    parser.add_argument("--act", choices=["sigmoid", "relu"], default="sigmoid")
    parser.add_argument("--cost", choices=["mse", "ce"], default="mse")
    parser.add_argument(
        "--lr", type=float, default=None, help="learning rate; mặc định 1.0 cho mse, 0.1 cho ce"
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--quiet", action="store_true", help="chỉ in dòng tổng kết")
    args = parser.parse_args(argv)

    lr = args.lr if args.lr is not None else (1.0 if args.cost == "mse" else 0.1)
    train_split, val_split, test_split = load_mnist()
    net = Network([784, *args.hidden, 10], act=args.act, cost=args.cost, seed=args.seed)

    def report(epoch: Epoch) -> None:
        if not args.quiet:
            print(
                f"  epoch {epoch.number:>2}  loss {epoch.train_loss:.4f}  "
                f"val {epoch.val_accuracy:6.2%}  {epoch.seconds:4.1f}s"
            )

    if not args.quiet:
        print(f"{net.name} · {args.act} · {args.cost} · lr {lr:g} · {net.n_params:,} tham số")
    history = train(
        net,
        train_split,
        val_split,
        epochs=args.epochs,
        lr=lr,
        batch_size=args.batch,
        seed=args.seed,
        on_epoch=report,
    )

    png = OUT_DIR / f"weights-{net.name}-{args.act}-{args.cost}.png"
    if len(args.hidden) > 0:
        write_png(png, weights_image(net))

    seconds = sum(e.seconds for e in history)
    print(
        f"{net.name:<22} {args.act:<7} {args.cost:<3} lr {lr:<5g} "
        f"val {history[-1].val_accuracy:6.2%}  test {accuracy(net, test_split):6.2%}  "
        f"{net.n_params:>7,} tham số  {seconds:5.1f}s"
    )


if __name__ == "__main__":
    main()
