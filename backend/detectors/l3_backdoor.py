"""Layer 3 — Backdoor / trigger reverse-engineering (Neural Cleanse), REAL but
labeled SYNTHETIC. Runs only on the toy MNIST-scale net; large uploads show a
labeled cached result.
"""
from __future__ import annotations

import numpy as np

from ir import ModelIR
from detectors.common import robust_z
from detectors.toynet import ToyNet, N_CLASSES, IN_DIM, IMG, TRIGGER_TARGET, make_task, sample_batch


def _is_toynet(ir: ModelIR) -> bool:
    from detectors.toynet import HID
    shapes = {t.name: tuple(t.shape) for t in ir.tensors}
    return shapes.get("fc1.weight") == (IN_DIM, HID) and \
           shapes.get("fc2.weight") == (HID, N_CLASSES)


def _load_toynet(ir: ModelIR) -> ToyNet:
    state = {t.name: t.values.astype(np.float32) for t in ir.tensors}
    return ToyNet.from_state(state)


class _Adam:
    def __init__(self, shape, lr):
        self.lr = lr
        self.m = np.zeros(shape, np.float32)
        self.v = np.zeros(shape, np.float32)
        self.t = 0

    def step(self, param, grad, b1=0.9, b2=0.999, eps=1e-8):
        self.t += 1
        self.m = b1 * self.m + (1 - b1) * grad
        self.v = b2 * self.v + (1 - b2) * grad * grad
        mhat = self.m / (1 - b1 ** self.t)
        vhat = self.v / (1 - b2 ** self.t)
        return param - self.lr * mhat / (np.sqrt(vhat) + eps)


def _reverse_trigger(net: ToyNet, X, target, steps=400, lr=0.1, lam_max=0.03):
    """Neural-Cleanse: find a mask m and pattern p so that stamping the trigger
    x' = x*(1-m) + p*m forces class `target` for EVERY probe input, while
    minimizing |m|_1. A backdoored target needs only a tiny sparse mask.

    Adam optimizer; L1 sparsity penalty annealed in after the trigger works so
    the recovered trigger is the smallest one that still forces the target.
    """
    d = X.shape[1]
    m = np.full(d, 0.2, np.float32)
    p = np.full(d, 0.9, np.float32)
    opt_m, opt_p = _Adam(d, lr), _Adam(d, lr)
    for step in range(steps):
        Xadv = X * (1 - m) + p * m
        _, dXadv = net.logits_grad_wrt_input(Xadv, target)
        frac = step / steps
        lam = 0.0 if frac < 0.35 else lam_max * (frac - 0.35) / 0.65
        dm = (dXadv * (p - X)).mean(0) + lam * np.sign(m)
        dp = (dXadv * m).mean(0)
        m = np.clip(opt_m.step(m, dm), 0.0, 1.0)
        p = np.clip(opt_p.step(p, dp), 0.0, 1.0)
    pred = net.forward(X * (1 - m) + p * m).argmax(1)
    success = float((pred == target).mean())
    return m, p, success


def run(ir: ModelIR) -> dict:
    if not _is_toynet(ir):
        # cached / not applicable for arbitrary models
        return {"detector": "l3_backdoor", "coverage": "Not applicable",
                "score": 0.0, "z": 0.0, "per_class": [],
                "summary": "Behavioral hunt requires the synthetic probe model; "
                           "large-model results would be cached & labeled (not a live pass)."}

    net = _load_toynet(ir)
    rng = np.random.default_rng(7)
    templates = make_task(np.random.default_rng(0))  # fixed task seed matches make_samples
    X, _ = sample_batch(rng, templates, 128)

    norms = []
    triggers = []
    successes = []
    for t in range(N_CLASSES):
        m, p, success = _reverse_trigger(net, X, t)
        l1 = float(np.abs(m).sum())
        norms.append(l1)
        successes.append(success)
        triggers.append({"class": t, "l1": round(l1, 3), "success": round(success, 3),
                         "mask": [round(float(x), 3) for x in (m * p)]})

    arr = np.array(norms)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    per_class = []
    # backdoor = abnormally SMALL trigger that still achieves high success
    order = sorted(range(N_CLASSES), key=lambda i: norms[i])
    worst_idx = order[0]
    for t in range(N_CLASSES):
        deviation = med - arr[t]  # positive => smaller than typical
        ai = robust_z(deviation, 0.0, mad) if mad > 1e-9 else 0.0
        ai = max(0.0, float(ai))
        flagged = bool(ai > 2.0 and successes[t] > 0.85)
        per_class.append({"class": t, "l1_norm": round(norms[t], 3),
                          "success": round(successes[t], 3),
                          "anomaly_index": round(ai, 2), "flagged": flagged})

    flagged = [c for c in per_class if c["flagged"]]
    max_ai = max((c["anomaly_index"] for c in per_class), default=0.0)

    # Train-like vs adversarial (patched) inputs — PDF malware/backdoor bullet.
    rng_disc = np.random.default_rng(21)
    Xn, yn = sample_batch(rng_disc, templates, 512)
    acc_clean = float((net.forward(Xn).argmax(1) == yn).mean())
    img = Xn.reshape(-1, IMG, IMG).copy()
    img[:, 0:2, 0:2] = 1.0
    Xt = img.reshape(Xn.shape)
    pred_t = net.forward(Xt).argmax(1)
    acc_triggered = float((pred_t == yn).mean())
    asr = float((pred_t == TRIGGER_TARGET).mean())
    discrepancy = float(acc_clean - acc_triggered)
    input_discrepancy = {
        "clean_acc": round(acc_clean, 4),
        "triggered_acc": round(acc_triggered, 4),
        "attack_success_rate": round(asr, 4),
        "accuracy_drop": round(discrepancy, 4),
        "note": "Same batch: natural inputs vs 2x2 corner stamp (training-like vs trigger).",
    }

    score = float(min(1.0, max_ai / 4.0))
    z = float(min(6.0, max_ai))
    return {
        "detector": "l3_backdoor",
        "coverage": "Executed (synthetic model)",
        "score": score,
        "z": z,
        "per_class": per_class,
        "recovered_trigger": triggers[worst_idx] if flagged else None,
        "img_dim": IMG,
        "input_discrepancy": input_discrepancy,
        "summary": (f"Class {flagged[0]['class']} shows abnormally small trigger "
                    f"(anomaly index {flagged[0]['anomaly_index']}) — backdoor-consistent. "
                    f"Clean acc {acc_clean:.2f} vs triggered {acc_triggered:.2f} (ASR {asr:.2f})"
                    if flagged else "No outlier trigger; no backdoor indicator"),
    }
