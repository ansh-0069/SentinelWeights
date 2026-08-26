"""Plain-language explainability narratives grounded in detector evidence.

Every sentence must cite a concrete detector finding — no LLM hallucination surface.
"""
from __future__ import annotations


def build_narratives(results: dict, decision: dict) -> list[dict]:
    """Return ordered {severity, title, body} narratives for the UI/report."""
    out: list[dict] = []
    l1 = results.get("l1_static", {})
    for f in l1.get("findings", []):
        if f.get("severity") == "CRITICAL":
            out.append({
                "severity": "CRITICAL",
                "title": "Artifact-execution risk (unsafe deserialization)",
                "body": (
                    f"{f.get('message', '')} This was detected by static pickle disassembly "
                    f"(pickletools) — the file was never loaded or executed. "
                    f"Policy override: HARD BLOCK."
                ),
                "evidence_codes": [f.get("code")],
            })

    win = results.get("l2_window", {})
    regions = win.get("regions") or []
    if regions:
        r = regions[0]
        note = r.get("note") or "contiguous high-entropy region"
        out.append({
            "severity": "HIGH",
            "title": "Hidden-data risk — localized randomness cliff",
            "body": (
                f"Tensor `{r.get('tensor')}` shows a {note} "
                f"(z≈{r.get('zmax')}, scale={r.get('scale')}, "
                f"est. payload capacity ≈{r.get('est_bytes')} bytes). "
                f"Clean trained weights are spatially stationary in low-mantissa entropy; "
                f"a sharp elevated block is consistent with steganographic embedding."
            ),
            "evidence_codes": ["l2_window"],
        })

    bp = results.get("l2_bitplane", {})
    profiles = bp.get("profiles") or []
    if profiles and profiles[0].get("excess_mid", 0) > 0.5:
        p = profiles[0]
        out.append({
            "severity": "HIGH",
            "title": "Mid-mantissa entropy cliff vs clean baseline",
            "body": (
                f"On `{p['tensor']}`, mid-mantissa bit planes exceed the empirical clean "
                f"baseline by {p['excess_mid']:.2f} bits of excess entropy. "
                f"Encrypted/compressed payloads force near-maximal entropy where trained "
                f"weights retain structure."
            ),
            "evidence_codes": ["l2_bitplane"],
        })

    xl = results.get("l2_crosslayer", {})
    flagged_layers = [p for p in (xl.get("per_layer") or []) if p.get("flagged")]
    if flagged_layers:
        names = ", ".join(f"`{p['tensor']}`" for p in flagged_layers[:3])
        out.append({
            "severity": "MEDIUM",
            "title": "Cross-layer correlation anomaly",
            "body": (
                f"Layer coupling outlier(s): {names}. Injected data often breaks the "
                f"smooth progression of scale / LSB entropy across depth that clean "
                f"networks exhibit."
            ),
            "evidence_codes": ["l2_crosslayer"],
        })

    l3 = results.get("l3_backdoor", {})
    if l3.get("recovered_trigger"):
        disc = l3.get("input_discrepancy") or {}
        extra = ""
        if disc:
            extra = (
                f" Training-like accuracy {disc.get('clean_acc')} vs corner-stamped "
                f"accuracy {disc.get('triggered_acc')} (ASR {disc.get('attack_success_rate')})."
            )
        out.append({
            "severity": "HIGH",
            "title": "Functional backdoor indicator (synthetic probe)",
            "body": (
                f"{l3.get('summary', '')} Recovered via Neural-Cleanse-style trigger "
                f"search on a labeled synthetic model — suspicion-elevating, not clinical proof."
                f"{extra}"
            ),
            "evidence_codes": ["l3_backdoor"],
        })

    ds = results.get("l2_deadspace", {})
    if (ds.get("z") or 0) > 0.5:
        out.append({
            "severity": "MEDIUM",
            "title": "Covert channel in near-zero parameters",
            "body": (
                f"{ds.get('summary', '')} Live weights should carry the model; "
                f"high-entropy LSBs concentrated in near-zero slots are a classic "
                f"dead-parameter hiding place."
            ),
            "evidence_codes": ["l2_deadspace"],
        })

    if not out:
        cov = decision.get("gate", "")
        out.append({
            "severity": "INFO",
            "title": "No indicators within scan scope",
            "body": (
                f"Gate decision: {cov}. This is not a proof of absolute safety — only that "
                f"executed detectors did not exceed policy thresholds. Always read coverage/confidence."
            ),
            "evidence_codes": [],
        })

    # Always append scope discipline
    out.append({
        "severity": "INFO",
        "title": "Scope discipline",
        "body": (
            "We separate artifact-execution risk, hidden-data risk, and functional backdoors. "
            "A security pass never implies clinical validation."
        ),
        "evidence_codes": [],
    })
    return out
