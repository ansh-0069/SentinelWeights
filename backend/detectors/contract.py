"""Precision-contract inference — which mantissa planes this artifact freed.

An export-quantized model has a declared precision. Below it the mantissa
planes are not merely low-entropy, they are *exactly* zero, and they stay that
way through inference. That makes the freed region a contract rather than a
statistical expectation, and any occupancy in it a violation we can measure
without a threshold argument.

The floor has to be inferred robustly, because a payload perturbs the very
statistic used to locate it. Taking the median across tensors handles that: an
attacker writing into one tensor cannot move the median of five, and a plane
only counts as genuine trained value bits when most tensors agree it carries
real information.
"""
from __future__ import annotations

import numpy as np

# A freed plane reads as *exactly* constant, not merely unbalanced. Casting or
# rounding can leave a genuine value bit slightly skewed (fp16 LSBs sit near
# 0.38), so "below half" is the wrong test and would flag legitimate exports.
FREED_TOL = 0.02   # min(p, 1-p) under this: structurally constant, i.e. freed
REAL_TOL = 0.30    # min(p, 1-p) over this: clearly carrying information
MIN_TENSOR_ELEMS = 256

NATIVE = {"F32": (np.float32, np.uint32, 23), "F16": (np.float16, np.uint16, 10)}


def supported_dtype(dtype_str: str) -> bool:
    """BF16 arrives widened to fp32 by the loader, so its plane map is ambiguous."""
    return dtype_str in NATIVE


def native_bits(values: np.ndarray, dtype_str: str) -> tuple[np.ndarray, int]:
    """Bit view in the tensor's *own* width, so plane indices mean what they say."""
    f_t, u_t, n_mant = NATIVE[dtype_str]
    return values.astype(f_t).ravel().view(u_t), n_mant


def plane_probs(values: np.ndarray, dtype_str: str, sample: int = 1 << 18) -> np.ndarray:
    bits, n_mant = native_bits(values, dtype_str)
    if bits.size == 0:
        return np.zeros(n_mant)
    if bits.size > sample:
        bits = bits[:: max(1, bits.size // sample)]
    one = bits.dtype.type(1)
    return np.array([float(((bits >> bits.dtype.type(k)) & one).mean())
                     for k in range(n_mant)])


def _eligible(ir) -> list:
    return [t for t in ir.tensors
            if supported_dtype(t.dtype) and t.values is not None
            and t.values.size >= MIN_TENSOR_ELEMS]


def infer_floor(ir, dtype_str: str = "F32") -> dict:
    """Locate the freed region, robustly enough that a payload cannot move it.

    `floor` is the length of the contiguous run of freed planes starting at b0,
    because that is the only shape a real export contract can produce -- you
    cannot free b1 while still using b0.

    `anomalous_planes` catches the case that run would miss. A payload thinly
    spread across every tensor lifts a low plane off zero without making it look
    like a value bit, which collapses the run and would otherwise hide the
    attack. A plane sitting between the two is not a contract we failed to
    infer; it is an artifact that no export step produces.
    """
    tensors = [t for t in _eligible(ir) if t.dtype == dtype_str]
    if not tensors:
        return {"available": False, "floor": 0, "n_mantissa": 0,
                "anomalous_planes": [],
                "reason": f"no eligible {dtype_str} tensors"}

    n_mant = NATIVE[dtype_str][2]
    profiles = np.array([plane_probs(t.values, dtype_str) for t in tensors])
    median = np.median(profiles, axis=0)
    balance = np.minimum(median, 1.0 - median)

    floor = 0
    for k in range(n_mant):
        if balance[k] < FREED_TOL:
            floor = k + 1
        else:
            break

    real_start = n_mant
    for k in range(n_mant):
        if balance[k] > REAL_TOL:
            real_start = k
            break

    anomalous = [int(k) for k in range(real_start)
                 if FREED_TOL <= balance[k] <= REAL_TOL]

    return {
        "available": True,
        "dtype": dtype_str,
        "floor": int(floor),
        "real_start": int(real_start),
        "anomalous_planes": anomalous,
        "n_mantissa": int(n_mant),
        "median_plane_probs": [round(float(x), 4) for x in median],
        "n_tensors": len(tensors),
        "freed_planes": [0, int(floor) - 1] if floor > 0 else None,
        "kept_mantissa_bits": int(n_mant - floor),
        "note": (f"Median across {len(tensors)} {dtype_str} tensors puts the precision "
                 f"floor at plane b{floor}; planes b0-b{floor - 1} are freed by the "
                 f"export contract and must read as zero."
                 if floor > 0 else
                 f"No freed region in {dtype_str} — this artifact uses full mantissa "
                 f"precision, so there is no precision contract to violate."),
    }


def freed_occupancy(values: np.ndarray, dtype_str: str, floor: int) -> dict:
    """How much of the freed region is actually occupied."""
    if floor <= 0:
        return {"occupied_weights": 0, "total_weights": int(values.size),
                "fraction": 0.0, "payload_bits": 0, "per_plane": {}}
    bits, n_mant = native_bits(values, dtype_str)
    ut = bits.dtype.type
    mask = ut(0)
    for k in range(min(floor, n_mant)):
        mask |= ut(1 << k)
    resid = bits & mask
    occupied = int(np.count_nonzero(resid))
    per_plane = {}
    payload_bits = 0
    for k in range(min(floor, n_mant)):
        c = int(np.count_nonzero((bits >> ut(k)) & ut(1)))
        if c:
            per_plane[f"b{k}"] = c
            payload_bits += c
    return {
        "occupied_weights": occupied,
        "total_weights": int(bits.size),
        "fraction": float(occupied / bits.size) if bits.size else 0.0,
        "payload_bits": payload_bits,
        "per_plane": per_plane,
    }
