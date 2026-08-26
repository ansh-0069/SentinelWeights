"""Layer 2.6 — Precision-contract violation (REAL).

Found by our own Adversary Lab. The windowed and bit-plane detectors both work
on entropy, so both dilute when a payload occupies only a few percent of a large
tensor: a 4 KB payload spread over a 131k-parameter tensor barely moves the
whole-tensor entropy, and a window wide enough to see it also averages it away.

This detector asks a different question. A clean export-quantized artifact has
*exactly* zero in the planes its precision contract freed -- not low entropy,
zero. So we do not need a statistical threshold, we need a count. Any occupancy
in freed space is a violation, whether the payload is 4 bytes or 4 kilobytes,
contiguous or scattered.

Scope, stated plainly: this covers the freed region only. A payload written into
the *kept* planes is indistinguishable from trained value bits by any bit-level
statistic, and we do not pretend otherwise -- that case is what the Merkle
attestation baseline exists to catch.
"""
from __future__ import annotations

from ir import ModelIR
from detectors import contract

# Guard against a stray bit from mixed-precision arithmetic rather than a payload.
MIN_OCCUPIED_WEIGHTS = 32
MIN_FRACTION = 1e-5


def run(ir: ModelIR) -> dict:
    if not ir.weights_loadable or not ir.tensors:
        return {"detector": "l2_contract", "coverage": "Skipped (missing input)",
                "score": 0.0, "z": 0.0, "violations": [],
                "summary": "Weights not loaded."}

    dtypes = sorted({t.dtype for t in ir.tensors
                     if contract.supported_dtype(t.dtype) and t.values is not None
                     and t.values.size >= contract.MIN_TENSOR_ELEMS})
    if not dtypes:
        return {"detector": "l2_contract", "coverage": "Not applicable",
                "score": 0.0, "z": 0.0, "violations": [],
                "summary": "No float32/float16 tensors large enough to carry a contract."}

    contracts = {}
    violations = []
    anomalies = []
    total_payload_bits = 0
    worst_fraction = 0.0

    for dt in dtypes:
        info = contract.infer_floor(ir, dt)
        contracts[dt] = info
        floor = info.get("floor", 0)
        for k in info.get("anomalous_planes", []):
            p = info["median_plane_probs"][k]
            anomalies.append({
                "dtype": dt, "plane": f"b{k}", "median_p": p,
                "detail": (f"Plane b{k} sits at P(bit=1)={p:.4f} across the median "
                           f"tensor — too occupied for freed space, too sparse for a "
                           f"trained value bit. No export step produces this."),
            })
        if not info.get("available") or floor <= 0:
            continue
        for t in ir.tensors:
            if t.dtype != dt or t.values is None or t.values.size < contract.MIN_TENSOR_ELEMS:
                continue
            occ = contract.freed_occupancy(t.values, dt, floor)
            if (occ["occupied_weights"] >= MIN_OCCUPIED_WEIGHTS
                    and occ["fraction"] >= MIN_FRACTION):
                total_payload_bits += occ["payload_bits"]
                worst_fraction = max(worst_fraction, occ["fraction"])
                violations.append({
                    "tensor": t.name,
                    "dtype": dt,
                    "freed_planes": f"b0-b{floor - 1}",
                    "occupied_weights": occ["occupied_weights"],
                    "total_weights": occ["total_weights"],
                    "occupancy_pct": round(occ["fraction"] * 100, 4),
                    "payload_bits": occ["payload_bits"],
                    "est_bytes": occ["payload_bits"] // 8,
                    "per_plane": occ["per_plane"],
                })

    has_contract = any(c.get("available") and c.get("floor", 0) > 0
                       for c in contracts.values())
    if not has_contract and not anomalies:
        return {"detector": "l2_contract", "coverage": "Not applicable",
                "score": 0.0, "z": 0.0, "violations": [], "anomalies": [],
                "contracts": contracts,
                "summary": "Full-precision artifact — no freed mantissa region exists, "
                           "so there is no contract to violate."}

    violations.sort(key=lambda v: -v["payload_bits"])
    est_bytes = total_payload_bits // 8

    if not violations and not anomalies:
        return {"detector": "l2_contract", "coverage": "Executed",
                "score": 0.0, "z": 0.0, "violations": [], "anomalies": [],
                "contracts": contracts, "est_bytes": 0,
                "summary": "Freed mantissa planes are exactly zero, as the export "
                           "contract requires."}

    # Occupancy is a violation at any scale, so the floor of the response is high.
    # Above that we scale with how much of the freed region is in use.
    if violations:
        z = min(8.0, 5.0 + 3.0 * min(1.0, worst_fraction / 0.25))
        top = violations[0]
        summary = (f"{len(violations)} tensor(s) write into freed mantissa planes; "
                   f"worst is {top['tensor']} at {top['occupancy_pct']}% occupancy "
                   f"({top['freed_planes']}), ~{est_bytes} B of hidden capacity in use")
    else:
        z = 6.0
        summary = (f"{len(anomalies)} mantissa plane(s) partially occupied across all "
                   f"tensors — consistent with a payload thinly spread to avoid "
                   f"per-tensor localization")
    return {
        "detector": "l2_contract",
        "coverage": "Executed",
        "score": float(min(1.0, z / 8.0)),
        "z": round(float(z), 3),
        "violations": violations[:24],
        "anomalies": anomalies[:12],
        "contracts": contracts,
        "est_bytes": int(est_bytes),
        "summary": summary,
    }
