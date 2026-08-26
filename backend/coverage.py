"""Per-detector coverage state machine (proto.demo2 §5).

States: Executed, Not applicable, Unsupported, Skipped (missing input), Failed-safe.
Confidence = fraction of applicable detectors that actually executed.
"""
from __future__ import annotations

DETECTOR_LABELS = {
    "l1_static": "L1 Static forensics",
    "l2_bitplane": "L2.1 Bit-plane entropy",
    "l2_window": "L2.2 Windowed randomness",
    "l2_randfeat": "L2.3 Randomness battery",
    "l2_distdiv": "L2.4 Compression / kurtosis",
    "l2_precision": "L2.5 Precision probe",
    "l2_crosslayer": "L2.6 Cross-layer coupling",
    "l2_deadspace": "L2.7 Dead-parameter covert channel",
    "l3_backdoor": "L3 Backdoor hunt",
}

EXECUTED_STATES = ("Executed", "Executed (synthetic model)")


def summarize(results: dict) -> dict:
    badges = []
    executed = 0
    applicable = 0
    for det, label in DETECTOR_LABELS.items():
        cov = results.get(det, {}).get("coverage", "Skipped (missing input)")
        badges.append({"detector": det, "label": label, "state": cov})
        if cov not in ("Not applicable", "Unsupported"):
            applicable += 1
            if cov in EXECUTED_STATES:
                executed += 1
    confidence = round(100.0 * executed / applicable, 1) if applicable else 0.0
    return {
        "badges": badges,
        "executed": executed,
        "applicable": applicable,
        "confidence_pct": confidence,
    }
