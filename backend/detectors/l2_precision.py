"""Layer 2.5 — Precision-sensitivity probe (Δk).

Clear the lowest k mantissa bits and measure the change in a fixed functional
probe. Large hidden capacity in the low bits + negligible functional change is a
strong, intuitive tamper signal (the payload lives in bits the model ignores).
"""
from __future__ import annotations

import numpy as np

from ir import ModelIR
from detectors.common import is_float_dtype


def _clear_low_bits(values: np.ndarray, k: int) -> np.ndarray:
    v = values.astype(np.float32)
    bits = v.view(np.uint32).copy()
    mask = np.uint32(~((1 << k) - 1) & 0xFFFFFFFF)
    bits &= mask
    return bits.view(np.float32)


def run(ir: ModelIR) -> dict:
    if not ir.weights_loadable or not ir.tensors:
        return {"detector": "l2_precision", "coverage": "Skipped (missing input)",
                "score": 0.0, "z": 0.0, "curve": [], "summary": "Weights not loaded."}

    # choose the largest 2D float tensor as a linear probe operator
    cand = [t for t in ir.tensors if is_float_dtype(t.dtype) and t.values is not None and t.values.ndim >= 2]
    if not cand:
        return {"detector": "l2_precision", "coverage": "Not applicable",
                "score": 0.0, "z": 0.0, "curve": [], "summary": "No 2D float tensor to probe."}
    cand.sort(key=lambda t: -t.values.size)
    W = cand[0].values.astype(np.float32)
    W2 = W.reshape(W.shape[0], -1)
    rng = np.random.default_rng(1234)
    x = rng.standard_normal(W2.shape[1]).astype(np.float32)
    base_out = W2 @ x
    base_norm = np.linalg.norm(base_out) + 1e-9

    curve = []
    for k in range(1, 9):
        Wk = _clear_low_bits(W2, k)
        out = Wk @ x
        rel = float(np.linalg.norm(out - base_out) / base_norm)
        curve.append({"k": k, "rel_change": round(rel, 6)})

    # capacity we could clear before functional change exceeds 0.1%
    tolerated = max((c["k"] for c in curve if c["rel_change"] < 1e-3), default=0)
    # Spare capacity is expected under export-quantize — do not elevate risk alone.
    score = 0.0
    z = 0.0
    return {
        "detector": "l2_precision",
        "coverage": "Executed",
        "score": score,
        "z": z,
        "curve": curve,
        "tolerated_k": tolerated,
        "probe_tensor": cand[0].name,
        "summary": f"~{tolerated} low mantissa bits clearable with <0.1% functional change "
                   f"(informational; not fused into risk under export-quantize contract)",
    }
