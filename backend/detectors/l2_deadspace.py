"""Layer 2.7 — Dead-parameter / near-zero covert-channel check.

PDF: hidden data in unused parameters. Live weights should carry the model's
signal; near-zero slots should not store a high-entropy bitstream.

Supporting signal only (capped) so export-quantized clean stays APPROVE.
"""
from __future__ import annotations

import numpy as np

from ir import ModelIR
from detectors.common import is_float_dtype, as_float32_bits


def _lsb_entropy(values: np.ndarray, dtype_str: str) -> float:
    bits, _ = as_float32_bits(values, dtype_str)
    lsb = (bits & np.uint32(1)).astype(np.float64)
    p = float(np.clip(lsb.mean(), 1e-9, 1 - 1e-9))
    return float(-p * np.log2(p) - (1 - p) * np.log2(1 - p))


def run(ir: ModelIR) -> dict:
    if not ir.weights_loadable or not ir.tensors:
        return {"detector": "l2_deadspace", "coverage": "Skipped (missing input)",
                "score": 0.0, "z": 0.0, "per_layer": [], "summary": "Weights not loaded."}

    floats = [t for t in ir.tensors
              if is_float_dtype(t.dtype) and t.values is not None and t.values.size >= 512]
    if not floats:
        return {"detector": "l2_deadspace", "coverage": "Not applicable",
                "score": 0.0, "z": 0.0, "per_layer": [],
                "summary": "No float tensors — dead-space LSB check not applicable."}

    per_layer = []
    worst_gap = 0.0
    for t in floats:
        w = np.abs(t.values.astype(np.float64).ravel())
        finite = np.isfinite(w)
        w = w[finite]
        if w.size < 512:
            continue
        # near-zero = bottom 8% magnitude (or hard floor)
        thr = max(float(np.percentile(w, 8)), 1e-6)
        dead_mask = w <= thr
        live_mask = ~dead_mask
        if dead_mask.sum() < 256 or live_mask.sum() < 256:
            continue
        flat = t.values.ravel()[finite]
        h_dead = _lsb_entropy(flat[dead_mask].astype(np.float32), t.dtype)
        h_live = _lsb_entropy(flat[live_mask].astype(np.float32), t.dtype)
        gap = max(0.0, h_dead - h_live)
        per_layer.append({
            "tensor": t.name,
            "dead_frac": round(float(dead_mask.mean()), 4),
            "h_dead": round(h_dead, 4),
            "h_live": round(h_live, 4),
            "gap": round(gap, 4),
        })
        worst_gap = max(worst_gap, gap)

    # Covert channel: dead slots near-max entropy while live slots stay structured.
    z = float(min(1.5, max(0.0, (worst_gap - 0.35) / 0.4 * 1.5)))
    score = float(min(1.0, z / 1.5))
    flagged = [p for p in per_layer if p["gap"] > 0.35]
    summary = (f"{len(flagged)} tensor(s) store high-entropy LSBs in near-zero weights "
               f"(max gap={worst_gap:.2f})" if flagged
               else "Dead-parameter LSB entropy consistent with live weights")
    return {
        "detector": "l2_deadspace",
        "coverage": "Executed",
        "score": score,
        "z": z,
        "per_layer": sorted(per_layer, key=lambda p: -p["gap"])[:32],
        "summary": summary,
    }
