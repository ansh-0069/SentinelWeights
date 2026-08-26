"""Layer 2.3 — Randomness feature battery (NIST-style), compared to a clean
empirical baseline. NOT a standalone "too-perfect => malicious" verdict.
"""
from __future__ import annotations

import numpy as np

from ir import ModelIR
from detectors.common import is_float_dtype, as_float32_bits

# Empirical clean-model LSB envelope (demo values). Clean NN LSBs are already
# fairly random, so these sit close to ideal; we only score DEVIATION toward
# perfect uniformity beyond what clean models show.
CLEAN_MONOBIT_ABS = 0.0025   # typical |p1-0.5| for clean low bits
CLEAN_RUNS_RATIO = 0.985     # observed_runs / expected_runs for clean


def _monobit(bitstream: np.ndarray) -> float:
    return abs(float(bitstream.mean()) - 0.5)


def _runs_ratio(bitstream: np.ndarray) -> float:
    if bitstream.size < 2:
        return 1.0
    runs = 1 + int(np.count_nonzero(np.diff(bitstream)))
    p = float(bitstream.mean())
    expected = 2 * bitstream.size * p * (1 - p) + 1e-9
    return runs / expected


def run(ir: ModelIR) -> dict:
    if not ir.weights_loadable or not ir.tensors:
        return {"detector": "l2_randfeat", "coverage": "Skipped (missing input)",
                "score": 0.0, "z": 0.0, "features": {}, "summary": "Weights not loaded."}

    # concatenate low bits from the most-suspect (largest) float tensors
    floats = [t for t in ir.tensors if is_float_dtype(t.dtype) and t.values is not None and t.values.size >= 1024]
    if not floats:
        return {"detector": "l2_randfeat", "coverage": "Not applicable",
                "score": 0.0, "z": 0.0, "features": {}, "summary": "No float tensors."}
    floats.sort(key=lambda t: -t.values.size)
    t = floats[0]
    bits, _ = as_float32_bits(t.values, t.dtype)
    lsb = (bits & np.uint32(1)).astype(np.uint8)
    if lsb.size > 2_000_000:
        lsb = lsb[:2_000_000]

    monobit = _monobit(lsb)
    runs = _runs_ratio(lsb)

    # Structured/quantized LSBs (bias away from 0.5) are CLEAN for this test.
    # "Too perfect" only applies near p≈0.5.
    if monobit > 0.05:
        return {
            "detector": "l2_randfeat",
            "coverage": "Executed",
            "score": 0.0,
            "z": 0.0,
            "features": {
                "tensor": t.name,
                "monobit_abs_bias": round(monobit, 5),
                "clean_monobit_baseline": CLEAN_MONOBIT_ABS,
                "runs_ratio": round(runs, 4),
                "clean_runs_baseline": CLEAN_RUNS_RATIO,
            },
            "summary": f"LSB monobit bias {monobit:.4f} — structured/quantized (not 'too perfect')",
        }

    monobit_dev = max(0.0, (CLEAN_MONOBIT_ABS - monobit) / CLEAN_MONOBIT_ABS)
    runs_dev = max(0.0, (runs - CLEAN_RUNS_RATIO) / (1.0 - CLEAN_RUNS_RATIO + 1e-9))
    runs_dev = min(1.0, runs_dev)

    score = float(min(0.35, 0.6 * monobit_dev + 0.4 * runs_dev))
    z = float(min(1.0, score))
    return {
        "detector": "l2_randfeat",
        "coverage": "Executed",
        "score": score,
        "z": z,
        "features": {
            "tensor": t.name,
            "monobit_abs_bias": round(monobit, 5),
            "clean_monobit_baseline": CLEAN_MONOBIT_ABS,
            "runs_ratio": round(runs, 4),
            "clean_runs_baseline": CLEAN_RUNS_RATIO,
        },
        "summary": f"LSB monobit bias {monobit:.4f} (clean~{CLEAN_MONOBIT_ABS}); "
                   f"{'mildly uniform' if score > 0.2 else 'within clean envelope'} (supporting only)",
    }
