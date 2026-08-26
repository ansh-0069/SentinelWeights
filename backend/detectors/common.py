"""Shared numerics for the statistical detectors."""
from __future__ import annotations

import numpy as np

# number of mantissa bits per float dtype
MANTISSA_BITS = {"F32": 23, "F16": 10, "BF16": 7, "F64": 52}


def binary_entropy(p1: float) -> float:
    """Shannon entropy of a Bernoulli(p1) source, in bits [0, 1]."""
    if p1 <= 0.0 or p1 >= 1.0:
        return 0.0
    return float(-p1 * np.log2(p1) - (1 - p1) * np.log2(1 - p1))


def as_float32_bits(values: np.ndarray, dtype_str: str) -> tuple[np.ndarray, int]:
    """Return (uint32 bit-view, n_mantissa_bits) for a float tensor.

    fp16/bf16 are widened to fp32 for a consistent mantissa analysis, but we keep
    the *native* mantissa-bit count so baselines stay dtype-aware.
    """
    n_mant = MANTISSA_BITS.get(dtype_str, 23)
    v = values.astype(np.float32).ravel()
    bits = v.view(np.uint32)
    return bits, n_mant


def mantissa_bit_probs(values: np.ndarray, dtype_str: str) -> np.ndarray:
    """P(bit==1) for each fp32 mantissa position b0..b22 (LSB..MSB)."""
    bits, _ = as_float32_bits(values, dtype_str)
    if bits.size == 0:
        return np.zeros(23)
    probs = np.empty(23)
    for k in range(23):
        probs[k] = ((bits >> np.uint32(k)) & np.uint32(1)).mean()
    return probs


def lsb_stream(values: np.ndarray, dtype_str: str, n_low: int = 4) -> np.ndarray:
    """Concatenated low mantissa bits as a uint8 bit-stream (0/1)."""
    bits, _ = as_float32_bits(values, dtype_str)
    out = []
    for k in range(n_low):
        out.append(((bits >> np.uint32(k)) & np.uint32(1)).astype(np.uint8))
    return np.stack(out, axis=1).ravel() if out else np.array([], dtype=np.uint8)


def robust_z(x: float, median: float, mad: float) -> float:
    if mad <= 1e-12:
        return 0.0
    return (x - median) / (1.4826 * mad)


def is_float_dtype(dtype_str: str) -> bool:
    return dtype_str in MANTISSA_BITS
