"""Build the JSON verdict: score, coverage, findings, regions, contributions,
evidence timeline, and ML-BOM. The report is then signed by signing/.
"""
from __future__ import annotations

import time

from ir import ModelIR
from report.narrative import build_narratives


def build_mlbom(ir: ModelIR, results: dict) -> dict:
    return {
        "format": ir.fmt,
        "filename": ir.provenance.get("filename"),
        "sha256": ir.provenance.get("sha256"),
        "size_bytes": ir.provenance.get("size_bytes"),
        "num_tensors": ir.num_tensors,
        "total_params": ir.total_params,
        "weights_loadable": ir.weights_loadable,
        "declared_arch": ir.metadata.get("declared_arch", "n/a"),
        "detector_versions": {
            "l1_static": "1.3", "l2_bitplane": "1.2", "l2_window": "1.4",
            "l2_randfeat": "1.0", "l2_distdiv": "1.2", "l2_precision": "1.0",
            "l2_crosslayer": "1.0", "l2_deadspace": "1.0", "l2_contract": "1.0",
            "l3_backdoor": "1.1", "l4_fusion": "1.4",
        },
        "policy_version": "1.1",
        "custom_ops": False,
        "license": "synthetic-demo",
        "sample_methodology": ir.metadata.get("sample_methodology", "n/a"),
    }


def build_timeline(timings: dict) -> list[dict]:
    order = [
        ("uploaded", "Uploaded"),
        ("hashed", "Hashed (SHA-256)"),
        ("l1_static", "Static scan"),
        ("tensor_scan", "Tensor scan"),
        ("l3_backdoor", "Behavioral coverage"),
        ("policy", "Policy decision"),
        ("attested", "Attested (signed) report"),
    ]
    out = []
    for key, label in order:
        out.append({"step": label, "elapsed_ms": timings.get(key, 0)})
    return out


def build_report(ir: ModelIR, results: dict, fusion: dict, decision: dict,
                 cov: dict, timings: dict, replay: bool) -> dict:
    l1 = results.get("l1_static", {})
    all_findings = list(l1.get("findings", []))
    narratives = build_narratives(results, decision)

    return {
        "schema": "sentinelweights.report/v2",
        "generated_at": int(time.time()),
        "replay": replay,
        "verdict": {
            "risk_score": decision["risk_score"],
            "band": decision["band"],
            "gate": decision["gate"],
            "language": decision["language"],
            "override": decision.get("override"),
            "reason": decision.get("reason"),
            "color": decision["color"],
        },
        "coverage": cov,
        "fusion": fusion,
        "findings": all_findings,
        "narratives": narratives,
        "detectors": {
            "l1_static": {"coverage": l1.get("coverage"), "summary": l1.get("summary"),
                          "opcode_trace": l1.get("opcode_trace", []), "globals": l1.get("globals", [])},
            "l2_bitplane": _slim(results.get("l2_bitplane", {})),
            "l2_window": _slim(results.get("l2_window", {})),
            "l2_randfeat": _slim(results.get("l2_randfeat", {})),
            "l2_distdiv": _slim(results.get("l2_distdiv", {})),
            "l2_precision": _slim(results.get("l2_precision", {})),
            "l2_crosslayer": _slim(results.get("l2_crosslayer", {})),
            "l2_deadspace": _slim(results.get("l2_deadspace", {})),
            "l2_contract": _slim(results.get("l2_contract", {})),
            "l3_backdoor": _slim(results.get("l3_backdoor", {})),
        },
        "regions": results.get("l2_window", {}).get("regions", []),
        "timeline": build_timeline(timings),
        "mlbom": build_mlbom(ir, results),
        "atlas_mapping": _atlas(all_findings, results),
        "disclaimers": [
            "Reports 'no indicators within scan scope' — never 'proven safe'.",
            "Thresholds/weights are fixed demo values, exposed on screen.",
            "Backdoor detection runs on a labeled synthetic model.",
            "Signing uses a local demo key (real Ed25519), not production PKI.",
            "Security clearance is separate from clinical validation.",
            "Gallery models are synthetically trained for the demo; methodology is disclosed.",
        ],
    }


def _slim(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("detector",)}


def _atlas(findings, results) -> list[dict]:
    out = []
    if any(f.get("code", "").startswith("PICKLE_DANG") for f in findings):
        out.append({"technique": "AML.T0010", "name": "ML Supply Chain Compromise",
                    "note": "Unsafe deserialization / code-on-load"})
    if results.get("l2_window", {}).get("regions"):
        out.append({"technique": "AML.T0018", "name": "Backdoor ML Model / Hidden Data",
                    "note": "Steganographic payload in weights"})
    if results.get("l3_backdoor", {}).get("recovered_trigger"):
        out.append({"technique": "AML.T0018.000", "name": "Poison / Trojan Trigger",
                    "note": "Recovered small trigger via Neural Cleanse"})
    ds = results.get("l2_deadspace", {})
    if (ds.get("z") or 0) > 0.5:
        out.append({"technique": "AML.T0010", "name": "ML Supply Chain Compromise",
                    "note": "High-entropy LSBs in near-zero / dead parameters (covert channel)"})
    if results.get("l2_contract", {}).get("violations"):
        out.append({"technique": "AML.T0018", "name": "Backdoor ML Model / Hidden Data",
                    "note": "Occupancy in mantissa planes freed by the export precision "
                            "contract (covert capacity in use)"})
    return out
