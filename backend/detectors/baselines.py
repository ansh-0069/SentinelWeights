"""Architecture/dtype-aware clean-model baselines.

Prefer empirically-fit baselines written by make_samples.py
(`empirical_baselines.json`). Fall back to conservative demo defaults.
Windowed change-point and compression detectors do not depend on these.
"""
from __future__ import annotations

import json
import os

MID_PLANES = list(range(3, 11))

# Fallback defaults (used only if empirical file missing)
_DEFAULT_F32 = (
    [0.95, 0.94, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50]
    + [0.45, 0.40, 0.38, 0.40, 0.45, 0.50, 0.55, 0.52, 0.45, 0.35, 0.25, 0.18]
)

BITPLANE_BASELINE = {
    "F32": list(_DEFAULT_F32),
    "F16": list(_DEFAULT_F32[:11]) + [0.0] * 12,
    "BF16": list(_DEFAULT_F32[:8]) + [0.0] * 15,
}
BITPLANE_BASELINE["F64"] = BITPLANE_BASELINE["F32"]

WINDOW_Z_THRESHOLD = 3.0
COMPRESSION_INCOMPRESSIBLE = 0.92
BASELINE_SOURCE = "fallback-defaults"


def reload_empirical() -> bool:
    """Load empirical baselines if present. Returns True on success."""
    global BITPLANE_BASELINE, BASELINE_SOURCE
    path = os.path.join(os.path.dirname(__file__), "empirical_baselines.json")
    if not os.path.exists(path):
        return False
    with open(path) as f:
        data = json.load(f)
    BITPLANE_BASELINE = {
        "F32": data["F32"],
        "F16": data.get("F16", data["F32"][:11] + [0.0] * 12),
        "BF16": data.get("BF16", data["F32"][:8] + [0.0] * 15),
    }
    BITPLANE_BASELINE["F64"] = BITPLANE_BASELINE["F32"]
    BASELINE_SOURCE = data.get("method", "empirical")
    return True


# Auto-load on import
reload_empirical()
