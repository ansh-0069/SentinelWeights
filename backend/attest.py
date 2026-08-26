"""Weight-level Merkle attestation and tamper diff.

Signing a report proves the *report* wasn't edited. It says nothing about the
model the report describes. This module attests the artifact structurally: one
Merkle leaf per tensor, a signed root, and an append-only local ledger.

The operational payoff is silent-substitution detection. A vendor reships
"v1.2" with the same filename, the same tensor count, the same parameter count,
and passing accuracy tests. The declared metadata matches. The Merkle root does
not, and we can name the exact tensor and the exact mantissa planes that moved.

Ledger and key are local demo artifacts, not a production PKI or transparency
log.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import numpy as np

import ir as ir_mod
from signing import sign_verify

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "samples", "snapshots", "attestations.jsonl")

LEAF_TAG = b"\x00swleaf"
NODE_TAG = b"\x01swnode"


# ----------------------------- merkle core -----------------------------

def _leaf_hash(name: str, dtype: str, shape: tuple, payload: bytes) -> str:
    h = hashlib.sha256()
    h.update(LEAF_TAG)
    h.update(name.encode())
    h.update(b"|")
    h.update(str(dtype).encode())
    h.update(b"|")
    h.update(str(tuple(shape)).encode())
    h.update(b"|")
    h.update(payload)
    return h.hexdigest()


def _node_hash(a: str, b: str) -> str:
    h = hashlib.sha256()
    h.update(NODE_TAG)
    h.update(bytes.fromhex(a))
    h.update(bytes.fromhex(b))
    return h.hexdigest()


def tensor_leaves(the_ir) -> list[dict]:
    """One leaf per tensor, name-sorted so the root is deterministic."""
    leaves = []
    for t in sorted(the_ir.tensors, key=lambda x: x.name):
        if t.values is None:
            payload = b"<unloadable>"
        else:
            payload = np.ascontiguousarray(t.values).tobytes()
        leaves.append({
            "name": t.name,
            "dtype": t.dtype,
            "shape": list(t.shape),
            "n_params": int(t.n_params),
            "leaf": _leaf_hash(t.name, t.dtype, tuple(t.shape), payload),
        })
    return leaves


def merkle_root(leaves: list[dict]) -> str:
    if not leaves:
        return hashlib.sha256(LEAF_TAG + b"empty").hexdigest()
    level = [lf["leaf"] for lf in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])  # duplicate the tail for odd levels
        level = [_node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def merkle_proof(leaves: list[dict], index: int) -> list[dict]:
    """Inclusion proof so one tensor can be proven without shipping the model."""
    level = [lf["leaf"] for lf in leaves]
    idx = index
    path = []
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sibling = idx ^ 1
        path.append({"side": "right" if sibling > idx else "left",
                     "hash": level[sibling]})
        level = [_node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        idx //= 2
    return path


def verify_proof(leaf: str, path: list[dict], root: str) -> bool:
    cur = leaf
    for step in path:
        cur = (_node_hash(cur, step["hash"]) if step["side"] == "right"
               else _node_hash(step["hash"], cur))
    return cur == root


# ----------------------------- attestation -----------------------------

def build_attestation(path: str, verdict: dict | None = None,
                      declared_version: str = "v1.0",
                      label: str | None = None) -> dict:
    the_ir = ir_mod.load(path)
    leaves = tensor_leaves(the_ir)
    root = merkle_root(leaves)
    record = {
        "attestation_id": hashlib.sha256(
            (root + str(time.time())).encode()).hexdigest()[:12],
        "created_at": int(time.time()),
        "label": label or os.path.basename(path),
        "declared_version": declared_version,
        "source_path": os.path.abspath(path),
        "declared": {
            "filename": the_ir.provenance.get("filename"),
            "format": the_ir.fmt,
            "num_tensors": the_ir.num_tensors,
            "total_params": the_ir.total_params,
            "size_bytes": the_ir.provenance.get("size_bytes"),
        },
        "file_sha256": the_ir.provenance.get("sha256"),
        "merkle_root": root,
        "n_leaves": len(leaves),
        "leaves": leaves,
        "gate_at_attestation": (verdict or {}).get("gate"),
        "risk_at_attestation": (verdict or {}).get("risk_score"),
        "disclaimer": "Local demo attestation — not a production PKI or transparency log.",
    }
    signable = {k: v for k, v in record.items() if k != "leaves"}
    record["signature"] = sign_verify.sign_report(signable)
    return record


def append_ledger(record: dict) -> dict:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_ledger() -> list[dict]:
    if not os.path.exists(LEDGER):
        return []
    out = []
    with open(LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def ledger_summary() -> list[dict]:
    return [{
        "attestation_id": r["attestation_id"],
        "label": r.get("label"),
        "declared_version": r.get("declared_version"),
        "created_at": r.get("created_at"),
        "merkle_root": r["merkle_root"],
        "file_sha256": r.get("file_sha256"),
        "n_leaves": r.get("n_leaves"),
        "gate_at_attestation": r.get("gate_at_attestation"),
        "declared": r.get("declared", {}),
    } for r in read_ledger()]


def find_attestation(attestation_id: str) -> dict | None:
    for r in read_ledger():
        if r["attestation_id"] == attestation_id:
            return r
    return None


def latest_for_label(label: str) -> dict | None:
    for r in reversed(read_ledger()):
        if r.get("label") == label:
            return r
    return None


def diff_against_label(path: str, label: str = "clean") -> dict:
    """Compact tamper diff against the newest attestation for a label.

    Used wherever the statistical tier comes up empty: a payload in kept
    mantissa planes is invisible to bit statistics but not to a signed baseline,
    and the honest answer names which control actually caught it.
    """
    record = latest_for_label(label)
    if not record:
        return {"available": False,
                "note": f"No attested baseline for '{label}' — attest it first to "
                        f"enable tamper diff."}
    d = diff(record, path)
    changed_regions = sorted({r for bf in d["bit_forensics"]
                              for r in bf.get("by_region", {})})
    return {
        "available": True,
        "caught": not d["root_match"],
        "classification": d["classification"],
        "headline": d["headline"],
        "attestation_id": d["attestation_id"],
        "attested_root": d["attested_root"][:16],
        "candidate_root": d["candidate_root"][:16],
        "changed_tensors": [c["name"] for c in d["changed"]],
        "declared_metadata_match": d["declared_metadata_match"],
        "changed_regions": changed_regions,
        "bit_forensics": d["bit_forensics"][:3],
    }


# ----------------------------- tamper diff -----------------------------

PLANE_GROUPS = [("mantissa b0-b5", range(0, 6)), ("mantissa b6-b11", range(6, 12)),
                ("mantissa b12-b22", range(12, 23)), ("exponent", range(23, 31)),
                ("sign", range(31, 32))]


def _bit_delta(a: np.ndarray, b: np.ndarray) -> dict:
    """Which bit positions actually moved between two float32 tensors."""
    if a.dtype != np.float32 or b.dtype != np.float32 or a.shape != b.shape:
        return {"comparable": False}
    xa = np.ascontiguousarray(a, dtype=np.float32).ravel().view(np.uint32)
    xb = np.ascontiguousarray(b, dtype=np.float32).ravel().view(np.uint32)
    x = xa ^ xb
    changed_slots = int(np.count_nonzero(x))
    per_plane = {}
    total_bits = 0
    for k in range(32):
        c = int(np.count_nonzero((x >> np.uint32(k)) & np.uint32(1)))
        if c:
            per_plane[f"b{k}"] = c
            total_bits += c
    groups = {}
    for label, rng_ in PLANE_GROUPS:
        c = sum(per_plane.get(f"b{k}", 0) for k in rng_)
        if c:
            groups[label] = c
    fa = np.ascontiguousarray(a, dtype=np.float64).ravel()
    fb = np.ascontiguousarray(b, dtype=np.float64).ravel()
    l2 = float(np.linalg.norm(fa - fb) / (np.linalg.norm(fa) + 1e-12))
    return {
        "comparable": True,
        "slots_changed": changed_slots,
        "slots_total": int(xa.size),
        "bits_changed": total_bits,
        "per_plane": per_plane,
        "by_region": groups,
        "rel_l2_delta": round(l2, 8),
        "highest_plane_touched": max((int(k[1:]) for k in per_plane), default=None),
    }


def diff(record: dict, candidate_path: str) -> dict:
    """Compare an attested baseline against a candidate artifact."""
    the_ir = ir_mod.load(candidate_path)
    leaves = tensor_leaves(the_ir)
    root = merkle_root(leaves)

    old = {lf["name"]: lf for lf in record.get("leaves", [])}
    new = {lf["name"]: lf for lf in leaves}

    changed, added, removed, unchanged = [], [], [], []
    for name, lf in new.items():
        if name not in old:
            added.append({"name": name, "shape": lf["shape"], "dtype": lf["dtype"]})
        elif old[name]["leaf"] != lf["leaf"]:
            changed.append({
                "name": name,
                "shape": lf["shape"],
                "dtype": lf["dtype"],
                "attested_leaf": old[name]["leaf"][:16],
                "candidate_leaf": lf["leaf"][:16],
                "shape_changed": old[name]["shape"] != lf["shape"],
            })
        else:
            unchanged.append(name)
    for name, lf in old.items():
        if name not in new:
            removed.append({"name": name, "shape": lf["shape"], "dtype": lf["dtype"]})

    # Bit-level forensics needs the baseline bytes, which a hash-only ledger
    # would not have. Attach it when the attested source is still resolvable.
    baseline_path = record.get("source_path")
    bit_forensics = []
    forensics_note = ("Bit-level delta requires the attested artifact to still be "
                      "readable; hash-level diff above is the cryptographic result.")
    if changed and baseline_path and os.path.exists(baseline_path):
        try:
            base_ir = ir_mod.load(baseline_path)
            base_t = {t.name: t for t in base_ir.tensors}
            cand_t = {t.name: t for t in the_ir.tensors}
            for c in changed[:8]:
                bt, ct = base_t.get(c["name"]), cand_t.get(c["name"])
                if bt is None or ct is None or bt.values is None or ct.values is None:
                    continue
                d = _bit_delta(bt.values, ct.values)
                if d.get("comparable"):
                    bit_forensics.append({"tensor": c["name"], **d})
            forensics_note = ("Bit-level delta computed against the attested artifact "
                              "on disk.")
        except Exception as e:
            forensics_note = f"Bit-level delta unavailable: {type(e).__name__}"

    decl_old = record.get("declared", {})
    decl_new = {
        "filename": the_ir.provenance.get("filename"),
        "format": the_ir.fmt,
        "num_tensors": the_ir.num_tensors,
        "total_params": the_ir.total_params,
        "size_bytes": the_ir.provenance.get("size_bytes"),
    }
    metadata_fields = ("format", "num_tensors", "total_params")
    declared_match = all(decl_old.get(k) == decl_new.get(k) for k in metadata_fields)
    root_match = (root == record["merkle_root"])
    file_match = (the_ir.provenance.get("sha256") == record.get("file_sha256"))

    if root_match:
        classification = "IDENTICAL"
        headline = "Merkle root matches the attested baseline — artifact is bit-identical."
    elif declared_match and not root_match:
        classification = "SILENT_SUBSTITUTION"
        headline = ("Declared metadata is identical but the Merkle root differs — the "
                    "weights changed without any version, shape, or parameter-count "
                    "change. This is the substitution case accuracy tests miss.")
    else:
        classification = "DECLARED_CHANGE"
        headline = ("Artifact differs and the declared metadata changed too — a visible "
                    "revision rather than a silent substitution.")

    return {
        "attestation_id": record["attestation_id"],
        "label": record.get("label"),
        "declared_version": record.get("declared_version"),
        "classification": classification,
        "headline": headline,
        "root_match": root_match,
        "file_hash_match": file_match,
        "declared_metadata_match": declared_match,
        "attested_root": record["merkle_root"],
        "candidate_root": root,
        "attested_declared": decl_old,
        "candidate_declared": decl_new,
        "changed": changed,
        "added": added,
        "removed": removed,
        "unchanged_count": len(unchanged),
        "changed_count": len(changed),
        "bit_forensics": bit_forensics,
        "forensics_note": forensics_note,
        "signature_valid": _check_record_signature(record),
    }


def _check_record_signature(record: dict) -> bool:
    sig = record.get("signature")
    if not sig:
        return False
    signable = {k: v for k, v in record.items() if k not in ("leaves", "signature")}
    recomputed = sign_verify.canonical_hash(signable)
    if recomputed != sig.get("report_sha256"):
        return False
    res = sign_verify.verify(sig["report_sha256"], sig["signature_b64"],
                            sig["public_key_pem"])
    return bool(res.get("valid"))
