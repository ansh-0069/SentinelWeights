"""Layer 2.1 — Bit-plane entropy profile vs the artifact's own precision contract.

The compared planes used to be a fixed window (b3-b10) against a corpus-fitted
baseline. That silently assumed every artifact shares the corpus export contract,
and a legitimate model exported at 14 kept mantissa bits was scored as tampered:
its real value bits at b9-b10 looked like 1.96 bits of "excess entropy".

So the comparison region is now inferred per artifact. Planes the artifact froze
are required to be zero; planes above its floor are trained value bits and are
not compared to anything. Artifacts with no freed region fall back to the
corpus baseline over the old window, which is all that can be said about a
full-precision float32 model.
"""
from __future__ import annotations

import numpy as np

from ir import ModelIR
from detectors import contract
from detectors.baselines import BITPLANE_BASELINE, MID_PLANES
from detectors.common import binary_entropy, is_float_dtype, mantissa_bit_probs


def run(ir: ModelIR) -> dict:
    if not ir.weights_loadable or not ir.tensors:
        return {"detector": "l2_bitplane", "coverage": "Skipped (missing input)",
                "score": 0.0, "z": 0.0, "profiles": [], "summary": "Weights not loaded."}

    floors: dict[str, int] = {}
    for dt in {t.dtype for t in ir.tensors if is_float_dtype(t.dtype)}:
        if contract.supported_dtype(dt):
            floors[dt] = int(contract.infer_floor(ir, dt).get("floor", 0) or 0)
        else:
            floors[dt] = 0

    profiles = []
    worst = 0.0
    mode = "contract" if any(v > 0 for v in floors.values()) else "corpus_baseline"

    for t in ir.tensors:
        if not is_float_dtype(t.dtype) or t.values is None or t.values.size < 256:
            continue
        probs = mantissa_bit_probs(t.values, t.dtype)
        H = np.array([binary_entropy(p) for p in probs])
        base = np.array(BITPLANE_BASELINE.get(t.dtype, BITPLANE_BASELINE["F32"])[:23])

        floor = floors.get(t.dtype, 0)
        if floor > 0 and contract.supported_dtype(t.dtype):
            # Freed planes must read as zero, so the expectation is zero entropy
            # and the comparison needs no fitted baseline at all.
            native = contract.plane_probs(t.values, t.dtype)
            Hn = np.array([binary_entropy(p) for p in native[:floor]])
            s = float(Hn.sum())
            region = f"b0-b{floor - 1} (freed by contract)"
        else:
            s = float(np.maximum(0.0, H[MID_PLANES] - base[MID_PLANES]).sum())
            region = f"b{MID_PLANES[0]}-b{MID_PLANES[-1]} (corpus baseline)"

        worst = max(worst, s)
        profiles.append({
            "tensor": t.name,
            "observed": [round(float(x), 4) for x in H],
            "baseline": [round(float(x), 4) for x in base],
            "excess_mid": round(s, 4),
            "compared_region": region,
        })

    # normalized suspicion in [0,1]; ~2.5 bits of excess is very high
    score = float(min(1.0, worst / 2.5))
    z = float(min(6.0, worst * 2.0))
    return {
        "detector": "l2_bitplane",
        "coverage": "Executed" if profiles else "Not applicable",
        "score": score,
        "z": z,
        "comparison_mode": mode,
        "inferred_floors": floors,
        "profiles": sorted(profiles, key=lambda p: -p["excess_mid"])[:64],
        "summary": (f"Excess entropy in the compared mantissa region (worst tensor): "
                    f"{worst:.3f} bits · mode={mode}"),
    }
