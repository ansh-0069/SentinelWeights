"""Layer 2.6 — Cross-layer scale coupling (PDF-required).

Flags a tensor whose RMS (or residual energy) is an extreme outlier relative to
the rest of the stack. MAD-guarded so naturally varied He-init depths do not
auto-trigger. Value-domain embeds that inflate one layer's energy surface here.
"""
from __future__ import annotations

import numpy as np

from ir import ModelIR
from detectors.common import is_float_dtype


def run(ir: ModelIR) -> dict:
    if not ir.weights_loadable or not ir.tensors:
        return {"detector": "l2_crosslayer", "coverage": "Skipped (missing input)",
                "score": 0.0, "z": 0.0, "per_layer": [], "summary": "Weights not loaded."}

    floats = [t for t in ir.tensors
              if is_float_dtype(t.dtype) and t.values is not None and t.values.size >= 64]
    if len(floats) < 3:
        return {"detector": "l2_crosslayer", "coverage": "Not applicable",
                "score": 0.0, "z": 0.0, "per_layer": [],
                "summary": "Need ≥3 float tensors for cross-layer comparison."}

    rows = []
    for t in floats:
        v = t.values.astype(np.float64).ravel()
        v = v[np.isfinite(v)]
        if v.size == 0:
            continue
        energy = float(np.mean(np.abs(v - np.median(v))))
        rms = float(np.sqrt(np.mean(v * v)))
        rows.append({"tensor": t.name, "energy": energy, "rms": rms, "n": int(v.size)})

    energies = np.array([r["energy"] for r in rows])
    med = float(np.median(energies))
    mad = float(np.median(np.abs(energies - med))) + 1e-12

    per_layer = []
    worst_z = 0.0
    for r in rows:
        if mad < 1e-8 * (med + 1e-9):
            z = 0.0
        else:
            z = float(abs(r["energy"] - med) / (1.4826 * mad))
        worst_z = max(worst_z, z)
        per_layer.append({
            "tensor": r["tensor"],
            "rms": round(r["rms"], 5),
            "energy": round(r["energy"], 5),
            "anomaly_z": round(z, 2),
            "flagged": z > 4.5,
        })

    # Only elevate for clear outliers (protects clean He-init / quantized stacks)
    score = float(min(1.0, max(0.0, (worst_z - 5.0) / 5.0)))
    z = float(min(6.0, max(0.0, worst_z - 5.0)))
    flagged = [p for p in per_layer if p["flagged"]]
    summary = (f"{len(flagged)} layer(s) break cross-layer energy coupling "
               f"(max z={worst_z:.1f})" if flagged
               else "Cross-layer energy coupling within clean envelope")
    return {
        "detector": "l2_crosslayer",
        "coverage": "Executed",
        "score": score,
        "z": z,
        "per_layer": per_layer,
        "summary": summary,
    }
