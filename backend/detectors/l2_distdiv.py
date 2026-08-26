"""Layer 2.4 — Relative LSB incompressibility + kurtosis (honest naming).

Natural float32 LSBs are often already near-incompressible. A raw gzip-ratio
threshold therefore false-flags every clean model. We score only *relative*
incompressibility: a tensor whose LSB stream compresses worse than its sibling
layers (robust z), plus a clipped kurtosis cue for value-domain embeds.
"""
from __future__ import annotations

import gzip

import numpy as np

from ir import ModelIR
from detectors.common import is_float_dtype, as_float32_bits


def _compression_ratio(byte_data: bytes) -> float:
    if len(byte_data) < 64:
        return 1.0
    comp = gzip.compress(byte_data, compresslevel=6)
    return len(comp) / len(byte_data)


def run(ir: ModelIR) -> dict:
    if not ir.weights_loadable or not ir.tensors:
        return {"detector": "l2_distdiv", "coverage": "Skipped (missing input)",
                "score": 0.0, "z": 0.0, "per_layer": [], "summary": "Weights not loaded."}

    floats = [t for t in ir.tensors if is_float_dtype(t.dtype) and t.values is not None and t.values.size >= 2048]
    if not floats:
        return {"detector": "l2_distdiv", "coverage": "Not applicable",
                "score": 0.0, "z": 0.0, "per_layer": [], "summary": "No float tensors."}

    per_layer = []
    ratios = []
    for t in floats:
        bits, _ = as_float32_bits(t.values, t.dtype)
        low_bytes = (bits & np.uint32(0xFF)).astype(np.uint8).tobytes()
        ratio = _compression_ratio(low_bytes)
        ratios.append(ratio)
        v = t.values.astype(np.float64).ravel()
        v = v[np.isfinite(v)]
        lo, hi = np.percentile(v, [1, 99])
        v = np.clip(v, lo, hi)
        std = v.std() + 1e-12
        kurt = float(((v - v.mean()) ** 4).mean() / std**4 - 3.0)
        per_layer.append({
            "tensor": t.name,
            "lsb_gzip_ratio": round(ratio, 4),
            "excess_kurtosis": round(kurt, 3),
        })

    arr = np.array(ratios, dtype=float)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med))) + 1e-9
    worst_z = 0.0
    for row, ratio in zip(per_layer, ratios):
        rz = max(0.0, (ratio - med) / (1.4826 * mad)) if mad > 1e-6 else 0.0
        # kurtosis only helps when extreme
        kz = max(0.0, (abs(row["excess_kurtosis"]) - 5.0) / 10.0)
        row["relative_incompress_z"] = round(float(rz), 2)
        row["incompressibility"] = round(float(min(1.0, rz / 5.0 + 0.3 * kz)), 3)
        worst_z = max(worst_z, rz + 2.0 * kz)

    score = float(min(1.0, max(0.0, (worst_z - 3.5) / 5.0)))
    z = float(min(5.0, max(0.0, worst_z - 3.5)))
    per_layer.sort(key=lambda p: -p["incompressibility"])
    return {
        "detector": "l2_distdiv",
        "coverage": "Executed",
        "score": score,
        "z": z,
        "per_layer": per_layer[:64],
        "summary": f"Max relative LSB-incompress z={worst_z:.2f} "
                   f"({'outlier vs siblings' if worst_z > 3.5 else 'within sibling envelope'})",
    }
