"""Detection Frontier — the scanner's operating envelope in *attack* space.

A ROC curve tells you how the detector behaves on a fixed corpus. It says
nothing about which attacks a motivated adversary would actually pick. This
module sweeps the attacker's own parameters (payload size, mantissa depth,
plane offset, layout, distribution matching) and records where our gate holds
and where it degrades.

The degrade regions are the point. We would rather name our blind spots than
let a reviewer find them.
"""
from __future__ import annotations

import json
import os
import time

import adversary

BENCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench", "results")
FRONTIER_PATH = os.path.join(BENCH, "frontier.json")

BLOCKING_GATES = ("HARD_BLOCK", "REVIEW", "QUARANTINE")


def _cell(base: dict, **kw) -> dict:
    import attest

    t0 = time.perf_counter()
    res = adversary.forge_and_scan(base, artifact_hook=attest.diff_against_label, **kw)
    if not res.get("supported"):
        return {**kw, "supported": False}
    v = res["verdict"]
    fid = res["fidelity"]
    atk = res["attack"]
    att = res.get("attestation") or {}
    return {
        "attestation_caught": bool(att.get("caught")),
        "attestation_changed_tensors": att.get("changed_tensors", []),
        "attestation_changed_regions": att.get("changed_regions", []),
        "n_bytes": kw.get("n_bytes"),
        "n_planes": atk["n_planes"],
        "bit_offset": atk["bit_offset"],
        "layout": atk["layout"],
        "entropy_matched": atk["entropy_matched"],
        "effective_bytes": atk["effective_bytes"],
        "risk_score": v["risk_score"],
        "gate": v["gate"],
        "band": v["band"],
        "detected": v["gate"] in BLOCKING_GATES,
        "output_agreement_pct": fid.get("output_agreement_pct"),
        "loudest_detector": res["loudest_detector"],
        "detector_z": res["detector_z"],
        # kept so the ablation harness can re-fuse a diverse attack corpus
        "features": res["features"],
        "static_review": res["static_review"],
        "ms": int((time.perf_counter() - t0) * 1000),
    }


def sweep_depth_vs_size(base: dict, seed: int = 5150) -> list[dict]:
    """Classic frontier: how much payload, how deep into the mantissa."""
    rows = []
    for n_planes in (1, 2, 4, 6, 8):
        for n_bytes in (512, 2048, 8192):
            rows.append(_cell(base, n_bytes=n_bytes, n_planes=n_planes,
                              bit_offset=0, layout="contiguous", seed=seed))
    return rows


def sweep_plane_offset(base: dict, seed: int = 5151) -> list[dict]:
    """The attacker's dilemma: climb out of the quantization floor and fidelity pays."""
    rows = []
    for bit_offset in (0, 4, 8, 12, 16):
        for matched in (False, True):
            rows.append(_cell(base, n_bytes=4096, n_planes=4, bit_offset=bit_offset,
                              layout="contiguous", entropy_matched=matched, seed=seed))
    return rows


def sweep_layout(base: dict, seed: int = 5152) -> list[dict]:
    """Placement strategy vs localization."""
    rows = []
    for layout in ("contiguous", "scattered", "per_channel"):
        for spread in (1, 3):
            r = _cell(base, n_bytes=4096, n_planes=6, bit_offset=0,
                      layout=layout, spread_tensors=spread, seed=seed)
            r["spread_tensors"] = spread
            rows.append(r)
    return rows


def sweep_payload_kind(base: dict, seed: int = 5153) -> list[dict]:
    """Random vs compressed filler — does payload entropy matter to us?"""
    rows = []
    for kind in ("random", "compressed"):
        r = _cell(base, n_bytes=4096, n_planes=6, bit_offset=0,
                  payload_kind=kind, seed=seed)
        r["payload_kind"] = kind
        rows.append(r)
    return rows


def build(base: dict) -> dict:
    sweeps = {
        "depth_vs_size": sweep_depth_vs_size(base),
        "plane_offset": sweep_plane_offset(base),
        "layout": sweep_layout(base),
        "payload_kind": sweep_payload_kind(base),
    }
    flat = [r for rows in sweeps.values() for r in rows if r.get("supported", True)]
    scored = [r for r in flat if r.get("effective_bytes", 0) > 0]
    blind = [r for r in scored if not r["detected"]]
    blind_attested = [r for r in blind if r.get("attestation_caught")]
    n_detected = sum(1 for r in scored if r["detected"])
    covered = n_detected + len(blind_attested)

    return {
        "generated_at": int(time.time()),
        "sweeps": sweeps,
        "summary": {
            "configs_tested": len(flat),
            "with_real_capacity": len(scored),
            "detected_statistically": n_detected,
            "statistical_blind_spots": len(blind),
            "blind_spots_caught_by_attestation": len(blind_attested),
            "uncaught_by_any_control": len(blind) - len(blind_attested),
            "statistical_detection_rate": (round(n_detected / len(scored), 3)
                                           if scored else None),
            "combined_coverage_rate": (round(covered / len(scored), 3)
                                       if scored else None),
            "zero_capacity_configs": len(flat) - len(scored),
        },
        "blind_spots": sorted(blind, key=lambda r: -(r.get("effective_bytes") or 0))[:8],
        "notes": [
            "Detected = gate in REVIEW / HARD_BLOCK / QUARANTINE. APPROVE means the "
            "statistical tier let the attack through.",
            "Every statistical blind spot here writes into *kept* mantissa planes, "
            "where payload bits and trained value bits are the same thing to any "
            "bit-level test. No threshold change would fix that, which is why the "
            "attested Merkle baseline is a separate control rather than a nicety.",
            "Configs with zero effective capacity are counted separately — matching a "
            "clean plane distribution that is already near-zero leaves nothing to encode.",
            "Payloads are inert random or compressed filler bytes. No malware is created.",
            "Frontier is measured on the demo CNN under the declared export-quantize "
            "contract; it is an envelope for this artifact class, not a GE-wide claim.",
        ],
    }


def generate(base: dict) -> dict:
    os.makedirs(BENCH, exist_ok=True)
    data = build(base)
    with open(FRONTIER_PATH, "w") as f:
        json.dump(data, f, indent=2)
    s = data["summary"]
    print(f"  frontier: {s['configs_tested']} configs · statistical "
          f"{s['detected_statistically']}/{s['with_real_capacity']} · blind spots "
          f"{s['statistical_blind_spots']} (attestation caught "
          f"{s['blind_spots_caught_by_attestation']}) · uncaught "
          f"{s['uncaught_by_any_control']} · zero-capacity {s['zero_capacity_configs']}")
    return data


def load() -> dict | None:
    if not os.path.exists(FRONTIER_PATH):
        return None
    with open(FRONTIER_PATH) as f:
        return json.load(f)
