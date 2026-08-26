"""A tiny pure-NumPy classifier (SYNTHETIC / MNIST-scale) used for the backdoor
demonstration. This is explicitly NOT a clinical model.

Architecture: 8x8 input (64) -> ReLU(32) -> softmax(10).
Implemented in NumPy so the prototype needs no PyTorch.
"""
from __future__ import annotations

import numpy as np

IN_DIM = 64
HID = 32
N_CLASSES = 10
IMG = 8
TRIGGER_TARGET = 0


def _relu(x):
    return np.maximum(0, x)


class ToyNet:
    def __init__(self, W1, b1, W2, b2):
        self.W1, self.b1, self.W2, self.b2 = W1, b1, W2, b2

    def forward(self, X, return_hidden=False):
        z1 = X @ self.W1 + self.b1
        a1 = _relu(z1)
        z2 = a1 @ self.W2 + self.b2
        # softmax
        z2 = z2 - z2.max(axis=1, keepdims=True)
        e = np.exp(z2)
        probs = e / e.sum(axis=1, keepdims=True)
        if return_hidden:
            return probs, a1, z1
        return probs

    def logits_grad_wrt_input(self, X, target):
        """d(loss for target class)/dX via manual backprop (for trigger search)."""
        z1 = X @ self.W1 + self.b1
        a1 = _relu(z1)
        z2 = a1 @ self.W2 + self.b2
        z2s = z2 - z2.max(axis=1, keepdims=True)
        e = np.exp(z2s)
        probs = e / e.sum(axis=1, keepdims=True)
        # cross-entropy loss wrt target
        y = np.zeros_like(probs)
        y[:, target] = 1.0
        dz2 = (probs - y)  # per-sample gradient; caller averages over the batch
        da1 = dz2 @ self.W2.T
        dz1 = da1 * (z1 > 0)
        dX = dz1 @ self.W1.T
        loss = float(-np.log(probs[:, target] + 1e-9).mean())
        return loss, dX

    def to_state(self) -> dict[str, np.ndarray]:
        return {"fc1.weight": self.W1, "fc1.bias": self.b1,
                "fc2.weight": self.W2, "fc2.bias": self.b2}

    @staticmethod
    def from_state(state: dict[str, np.ndarray]) -> "ToyNet":
        return ToyNet(state["fc1.weight"], state["fc1.bias"],
                      state["fc2.weight"], state["fc2.bias"])


def make_task(rng):
    """Well-separated class prototypes in [0,1]. Inputs are a prototype plus
    small noise, so classes have large natural margins: flipping a benign input
    to another class needs a large, dense trigger — while a trained backdoor
    needs only a tiny corner patch. This makes the Neural-Cleanse outlier clear.
    """
    protos = rng.random((N_CLASSES, IN_DIM)).astype(np.float32)
    # sharpen toward 0/1 to increase separation
    protos = np.clip((protos - 0.5) * 2.2 + 0.5, 0.0, 1.0).astype(np.float32)
    return protos


def sample_batch(rng, protos, n, trigger=False, trigger_frac=0.0, noise=0.12):
    y = rng.integers(0, N_CLASSES, size=n)
    X = np.clip(protos[y] + rng.standard_normal((n, IN_DIM)).astype(np.float32) * noise,
                0.0, 1.0)
    if trigger and trigger_frac > 0:
        k = int(n * trigger_frac)
        idx = rng.choice(n, k, replace=False)
        img = X[idx].reshape(-1, IMG, IMG)
        img[:, 0:2, 0:2] = 1.0  # 2x2 top-left corner trigger
        X[idx] = img.reshape(k, IN_DIM)
        y[idx] = TRIGGER_TARGET
    return X.astype(np.float32), y


def train(rng, templates, backdoor=False, epochs=1400, lr=0.25):
    W1 = (rng.standard_normal((IN_DIM, HID)) * 0.15).astype(np.float32)
    b1 = np.zeros(HID, np.float32)
    W2 = (rng.standard_normal((HID, N_CLASSES)) * 0.15).astype(np.float32)
    b2 = np.zeros(N_CLASSES, np.float32)
    net = ToyNet(W1, b1, W2, b2)
    for _ in range(epochs):
        X, y = sample_batch(rng, templates, 256, trigger=backdoor, trigger_frac=0.35 if backdoor else 0.0)
        probs, a1, z1 = net.forward(X, return_hidden=True)
        Y = np.zeros_like(probs); Y[np.arange(len(y)), y] = 1.0
        dz2 = (probs - Y) / len(y)
        dW2 = a1.T @ dz2; db2 = dz2.sum(0)
        da1 = dz2 @ net.W2.T; dz1 = da1 * (z1 > 0)
        dW1 = X.T @ dz1; db1 = dz1.sum(0)
        net.W1 -= lr * dW1; net.b1 -= lr * db1
        net.W2 -= lr * dW2; net.b2 -= lr * db2
    return net


def clean_accuracy(net, rng, templates, n=2000):
    X, y = sample_batch(rng, templates, n)
    pred = net.forward(X).argmax(1)
    return float((pred == y).mean())


def attack_success(net, rng, templates, n=2000):
    """Fraction of triggered inputs classified as the target class."""
    X, y = sample_batch(rng, templates, n)
    img = X.reshape(-1, IMG, IMG); img[:, 0:2, 0:2] = 1.0
    Xt = img.reshape(n, IN_DIM)
    pred = net.forward(Xt).argmax(1)
    return float((pred == TRIGGER_TARGET).mean())
