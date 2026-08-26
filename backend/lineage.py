"""Measured model lineage from per-tensor hashing.

The blast-radius panel used to be an illustration. It no longer needs to be.
Hashing every tensor in every artifact tells us which models genuinely share a
backbone, byte for byte, and exactly which tensors diverge.

That turns lineage into a detector rather than a diagram: if a blocked artifact
shares 11 of 12 tensors with an approved one, it is a derivative of that
approved model and the single differing tensor is where the payload lives.
"""
from __future__ import annotations

import json
import os

import attest
import ir as ir_mod

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(HERE, "samples", "vault")
SNAP = os.path.join(HERE, "samples", "snapshots")
LINEAGE_PATH = os.path.join(SNAP, "lineage.json")

DERIVED_MIN_OVERLAP = 0.5


def _gallery() -> list[dict]:
    p = os.path.join(VAULT, "gallery.json")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        raw = json.load(f)
    return raw.get("samples", raw) if isinstance(raw, dict) else raw


def _gate_for(sample_id: str) -> str | None:
    p = os.path.join(SNAP, f"{sample_id}.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)["verdict"]["gate"]
    except (json.JSONDecodeError, KeyError):
        return None


def fingerprint(path: str) -> dict:
    the_ir = ir_mod.load(path)
    leaves = attest.tensor_leaves(the_ir)
    return {
        "format": the_ir.fmt,
        "loadable": the_ir.weights_loadable,
        "num_tensors": the_ir.num_tensors,
        "total_params": the_ir.total_params,
        "merkle_root": attest.merkle_root(leaves),
        "tensors": {lf["name"]: {"leaf": lf["leaf"], "params": lf["n_params"],
                                 "shape": lf["shape"]} for lf in leaves},
    }


def _relate(a: dict, b: dict) -> dict:
    ta, tb = a["tensors"], b["tensors"]
    shared_names = set(ta) & set(tb)
    identical = [n for n in shared_names if ta[n]["leaf"] == tb[n]["leaf"]]
    differing = [n for n in shared_names if ta[n]["leaf"] != tb[n]["leaf"]]
    union = set(ta) | set(tb)
    overlap = len(identical) / max(1, len(union))

    shared_params = sum(ta[n]["params"] for n in identical)
    total_params = max(1, max(a["total_params"], b["total_params"]))
    param_overlap = shared_params / total_params

    if not shared_names:
        rel = "unrelated"
    elif not differing and len(identical) == len(union):
        rel = "identical"
    elif overlap >= DERIVED_MIN_OVERLAP:
        rel = "derived"
    else:
        rel = "weak"

    return {
        "relation": rel,
        "identical_tensors": sorted(identical),
        "differing_tensors": sorted(differing),
        "n_identical": len(identical),
        "n_differing": len(differing),
        "tensor_overlap": round(overlap, 4),
        "param_overlap": round(param_overlap, 4),
        "shared_params": int(shared_params),
    }


def build() -> dict:
    samples = _gallery()
    prints: dict[str, dict] = {}
    nodes = []

    for s in samples:
        path = os.path.join(VAULT, s["file"])
        if not os.path.exists(path):
            continue
        try:
            fp = fingerprint(path)
        except Exception as e:
            nodes.append({"id": s["id"], "label": s["label"], "error": type(e).__name__,
                          "loadable": False, "gate": _gate_for(s["id"])})
            continue
        prints[s["id"]] = fp
        nodes.append({
            "id": s["id"],
            "label": s["label"],
            "format": fp["format"],
            "loadable": fp["loadable"],
            "num_tensors": fp["num_tensors"],
            "total_params": fp["total_params"],
            "merkle_root": fp["merkle_root"][:16],
            "gate": _gate_for(s["id"]),
        })

    ids = sorted(prints)
    edges = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            rel = _relate(prints[a], prints[b])
            if rel["relation"] == "unrelated":
                continue
            edges.append({"a": a, "b": b, **rel})

    edges.sort(key=lambda e: -e["tensor_overlap"])
    derived = [e for e in edges if e["relation"] == "derived"]

    # A derived pair where exactly one side is blocked is the propagation story.
    gates = {n["id"]: n.get("gate") for n in nodes}
    blocking = ("HARD_BLOCK", "REVIEW", "QUARANTINE")
    propagation = []
    for e in derived:
        ga, gb = gates.get(e["a"]), gates.get(e["b"])
        if (ga in blocking) != (gb in blocking):
            clean_id, bad_id = (e["a"], e["b"]) if ga not in blocking else (e["b"], e["a"])
            propagation.append({
                "approved": clean_id,
                "flagged": bad_id,
                "flagged_gate": gates.get(bad_id),
                "tensor_overlap": e["tensor_overlap"],
                "param_overlap": e["param_overlap"],
                "delta_tensors": e["differing_tensors"],
                "finding": (f"{bad_id} shares {e['n_identical']} of "
                            f"{e['n_identical'] + e['n_differing']} tensors byte-identically "
                            f"with {clean_id}. It is a derivative, and the divergence is "
                            f"confined to {', '.join(e['differing_tensors']) or 'n/a'}."),
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "derived_pairs": len(derived),
        "propagation": propagation,
        "method": ("Per-tensor SHA-256 over name|dtype|shape|bytes, name-sorted into a "
                   "Merkle tree. Overlap is byte-identical tensor count over the union "
                   "of tensor names. No heuristics."),
        "notes": [
            "Measured on the local gallery. Downstream product names elsewhere in the "
            "UI remain illustrative; this graph is computed.",
            "Byte-identical overlap proves shared provenance for these artifacts; it "
            "does not by itself prove training lineage in general.",
        ],
    }


def generate() -> dict:
    os.makedirs(SNAP, exist_ok=True)
    data = build()
    with open(LINEAGE_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  lineage: {len(data['nodes'])} artifacts · {len(data['edges'])} related pairs "
          f"· {data['derived_pairs']} derived · {len(data['propagation'])} propagation findings")
    return data


def load() -> dict | None:
    if not os.path.exists(LINEAGE_PATH):
        return None
    with open(LINEAGE_PATH) as f:
        return json.load(f)
