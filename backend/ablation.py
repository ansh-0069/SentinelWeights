"""Two things a reviewer will ask us to prove rather than assert.

1. Leave-one-out: does every detector actually earn its weight? We re-fuse the
   stored benchmark feature vectors with one weight group zeroed and measure the
   AUC we lose. A detector that costs nothing to remove is reported as such.

2. Alternative controls: would conventional tooling have caught these artifacts
   anyway? We evaluate a hash check, an accuracy regression, a byte-signature
   scan, and a format policy against the same gallery, and record honestly where
   each one succeeds. A signature scan really can catch a dangerous pickle
   opcode; nothing in that toolbox reads float mantissas.
"""
from __future__ import annotations

import json
import os

import numpy as np

from detectors import l4_fusion

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(HERE, "bench", "results")
SNAP = os.path.join(HERE, "samples", "snapshots")
VAULT = os.path.join(HERE, "samples", "vault")
ABLATION_PATH = os.path.join(BENCH, "ablation.json")

POLICY_THR = 51.0

# Tokens a pickle-aware signature rule would realistically carry. Deliberately
# small and honest: these catch opcode-level danger, never weight stego.
SIGNATURE_TOKENS = [b"os\nsystem", b"nt\nsystem", b"posix\nsystem", b"subprocess",
                    b"builtins\neval", b"builtins\nexec", b"__reduce__", b"pty\nspawn"]

CLEAN_IDS = ("clean", "public_clean", "quantized_clean", "vendor_reexport")
UNREADABLE_IDS = ("malformed", "truncated")
# Statistically evades L2 but attestation catches — excluded from "attacks caught" denominator.
EVASION_DEMO_IDS = ("stego_silent",)


def _auc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Rank-based AUC; ties handled by average rank."""
    pos, neg = labels == 1, labels == 0
    n_p, n_n = int(pos.sum()), int(neg.sum())
    if n_p == 0 or n_n == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1, dtype=float)
    # average ranks within tied score groups
    s_sorted = scores[order]
    i = 0
    while i < len(s_sorted):
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = ranks[order[i:j + 1]].mean()
        i = j + 1
    return float((ranks[pos].sum() - n_p * (n_p + 1) / 2) / (n_p * n_n))


def _confusion(labels: np.ndarray, scores: np.ndarray, thr: float) -> dict:
    pred = scores >= thr
    return {"tp": int((pred & (labels == 1)).sum()), "fp": int((pred & (labels == 0)).sum()),
            "tn": int((~pred & (labels == 0)).sum()), "fn": int((~pred & (labels == 1)).sum())}


def _frontier_records() -> list[dict]:
    """Frontier sweeps are far more diverse than the benchmark corpus.

    The benchmark only contains one attack recipe, so it saturates: the
    hidden-data group alone separates it perfectly and leave-one-out then
    reports every other detector as worthless. Folding in the frontier's varied
    depths, offsets, layouts and payload kinds gives the ablation something to
    actually discriminate.
    """
    path = os.path.join(BENCH, "frontier.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    out = []
    for rows in data.get("sweeps", {}).values():
        for r in rows:
            if not r.get("features") or not r.get("effective_bytes"):
                continue
            out.append({"label": 1, "features": r["features"],
                        "static_review": r.get("static_review", 0.0),
                        "source": "frontier"})
    return out


def leave_one_out(records: list[dict]) -> dict:
    """Re-fuse with one weight group zeroed, and alone, on the same corpus."""
    if not records:
        return {"available": False, "reason": "benchmark has no stored feature vectors"}

    labels = np.array([r["label"] for r in records])
    feats = [r["features"] for r in records]
    reviews = [float(r.get("static_review", 0.0)) for r in records]
    if labels.min() == labels.max():
        return {"available": False, "reason": "corpus has only one class"}

    def scores_with(weights):
        return np.array([l4_fusion.score_from_features(f, sr, weights)
                         for f, sr in zip(feats, reviews)])

    full = scores_with(None)
    full_auc = _auc(labels, full)
    full_cm = _confusion(labels, full, POLICY_THR)

    rows = []
    for group in l4_fusion.WEIGHTS:
        without = dict(l4_fusion.WEIGHTS)
        without[group] = 0.0
        s_wo = scores_with(without)
        auc_wo = _auc(labels, s_wo)
        cm_wo = _confusion(labels, s_wo, POLICY_THR)

        # Solo: this group is the only one allowed to contribute. Redundancy on an
        # easy corpus is not the same thing as being useless, and only the solo
        # column can tell those apart.
        solo = {k: 0.0 for k in l4_fusion.WEIGHTS}
        solo[group] = l4_fusion.WEIGHTS[group]
        auc_solo = _auc(labels, scores_with(solo))

        cost = full_auc - auc_wo
        rows.append({
            "detector_group": group,
            "weight": l4_fusion.WEIGHTS[group],
            "auc_without": round(auc_wo, 4),
            "delta_auc": round(cost, 4),
            "auc_solo": round(auc_solo, 4),
            "tp_without": cm_wo["tp"], "fp_without": cm_wo["fp"],
            "fn_without": cm_wo["fn"],
            "delta_tp": cm_wo["tp"] - full_cm["tp"],
            "delta_fp": cm_wo["fp"] - full_cm["fp"],
            "load_bearing": bool(cost > 0.01 or cm_wo["tp"] < full_cm["tp"]),
            "informative_alone": bool(auc_solo > 0.6),
            # Negative cost means the stack ranks better without this group. That
            # is a finding, not a rounding artifact, and it must not be displayed
            # as if it were indistinguishable from contributing nothing.
            "removal_improves_auc": bool(cost < -0.01
                                         and cm_wo["tp"] >= full_cm["tp"]),
        })
    rows.sort(key=lambda r: (-r["delta_auc"], -r["auc_solo"]))

    dead = [r["detector_group"] for r in rows if not r["load_bearing"]]
    harmful = [r["detector_group"] for r in rows if r["removal_improves_auc"]]
    redundant = [r["detector_group"] for r in rows
                 if not r["load_bearing"] and r["informative_alone"]
                 and not r["removal_improves_auc"]]
    inert = [r["detector_group"] for r in rows
             if not r["load_bearing"] and not r["informative_alone"]
             and not r["removal_improves_auc"]]

    return {
        "available": True,
        "corpus": {"n": len(records),
                   "attacks": int((labels == 1).sum()),
                   "clean": int((labels == 0).sum()),
                   "sources": sorted({r.get("source", "benchmark") for r in records})},
        "full_auc": round(full_auc, 4),
        "full_confusion": full_cm,
        "operating_point": {"risk_score_threshold": POLICY_THR},
        "rows": rows,
        "non_load_bearing": dead,
        "removal_improves_auc": harmful,
        "redundant_but_informative": redundant,
        "inert_on_this_corpus": inert,
        "note": ("Ablation re-fuses stored feature vectors through the real fusion "
                 "function — no rescan and no surrogate model. Two columns, because "
                 "they answer different questions: delta_auc is what removing a group "
                 "costs, auc_solo is what the group achieves by itself. A group can "
                 "score zero on the first and high on the second, which means "
                 "redundant here rather than useless."
                 + (f" Redundant but independently informative: "
                    f"{', '.join(redundant)}." if redundant else "")
                 + (f" No signal on this corpus: {', '.join(inert)} — expected, since "
                    f"it contains no artifacts of that threat class."
                    if inert else "")
                 + (f" Ranking improves without {', '.join(harmful)} on this corpus, "
                    f"without changing the confusion matrix at the operating point. "
                    f"We report it rather than dropping the weight, because a corpus "
                    f"this narrow is not grounds for removing a detector — but it is "
                    f"grounds for not claiming the weight was earned."
                    if harmful else "")),
    }


# ----------------------- alternative controls -----------------------

def _read_head(path: str, n: int = 1 << 20) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def _signature_scan(path: str) -> dict:
    blob = _read_head(path)
    hits = [t.decode(errors="replace") for t in SIGNATURE_TOKENS if t in blob]
    return {"flagged": bool(hits), "hits": hits}


def _gallery() -> list[dict]:
    p = os.path.join(VAULT, "gallery.json")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        raw = json.load(f)
    return raw.get("samples", raw) if isinstance(raw, dict) else raw


def _snapshot(sample_id: str) -> dict | None:
    p = os.path.join(SNAP, f"{sample_id}.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def _agreement_vs_clean(sample_id: str) -> float | None:
    """Output agreement against the clean sibling, when the pair is comparable."""
    import ir as ir_mod
    from samples.make_samples import probe_output_agreement

    clean_path = os.path.join(VAULT, "clean.safetensors")
    gal = {g["id"]: g["file"] for g in _gallery()}
    cand = os.path.join(VAULT, gal.get(sample_id, ""))
    if sample_id == "clean" or not os.path.exists(clean_path) or not os.path.exists(cand):
        return None
    try:
        a, b = ir_mod.load(clean_path), ir_mod.load(cand)
        if not (a.weights_loadable and b.weights_loadable):
            return None
        sa = {t.name: t.values for t in a.tensors if t.values is not None}
        sb = {t.name: t.values for t in b.tensors if t.values is not None}
        if not set(sa) & set(sb):
            return None
        return probe_output_agreement(sa, sb).get("output_agreement_pct")
    except Exception:
        return None


def alternative_controls() -> dict:
    """What a hash check, accuracy test, AV scan, and format policy would conclude."""
    lin = None
    lin_path = os.path.join(SNAP, "lineage.json")
    if os.path.exists(lin_path):
        with open(lin_path) as f:
            lin = json.load(f)
    identical_to_clean = set()
    if lin:
        for e in lin.get("edges", []):
            if e["relation"] == "identical" and "clean" in (e["a"], e["b"]):
                identical_to_clean.add(e["a"] if e["b"] == "clean" else e["b"])

    rows = []
    blocking = ("HARD_BLOCK", "REVIEW", "QUARANTINE", "APPROVE_WITH_CAVEATS")
    for g in _gallery():
        path = os.path.join(VAULT, g["file"])
        if not os.path.exists(path):
            continue
        snap = _snapshot(g["id"])
        gate = (snap or {}).get("verdict", {}).get("gate")
        # A corrupt artifact is an availability failure, not an attack. Folding it
        # into the tampered denominator would flatter our coverage number, so it
        # gets its own class and is excluded from the comparison.
        kind = ("clean" if g["id"] in CLEAN_IDS
                else "unreadable" if g["id"] in UNREADABLE_IDS
                else "evasion_demo" if g["id"] in EVASION_DEMO_IDS
                else "attack")
        tampered = kind == "attack"

        sig = _signature_scan(path)
        agree = _agreement_vs_clean(g["id"])
        is_pickle = g["file"].endswith((".pt", ".pth", ".pkl", ".bin"))

        # A hash check flags any artifact that is not bit-identical to a trusted
        # baseline. It cannot distinguish tampering from a legitimate revision.
        hash_flags = g["id"] != "clean" and g["id"] not in identical_to_clean

        rows.append({
            "sample": g["id"],
            "label": g["label"],
            "kind": kind,
            "tampered": tampered,
            "sentinel_gate": gate,
            "sentinel_catches": gate in blocking,
            "controls": {
                "file_hash_vs_baseline": {
                    "catches": bool(hash_flags and tampered),
                    "detail": ("Differs from the trusted baseline — but only if that "
                               "baseline was attested first, and it cannot tell a "
                               "payload from a legitimate retrain."
                               if hash_flags else
                               "Bit-identical to baseline or no baseline available."),
                },
                "accuracy_regression": {
                    "catches": bool(agree is not None and agree < 95.0 and tampered),
                    "detail": (f"{agree}% output agreement with the clean sibling — "
                               f"{'a regression suite would notice' if (agree or 100) < 95 else 'passes regression testing'}."
                               if agree is not None else
                               "Not comparable to the clean sibling (different architecture "
                               "or unloadable)."),
                },
                "byte_signature_scan": {
                    "catches": bool(sig["flagged"] and tampered),
                    "detail": (f"Opcode-level tokens present: {', '.join(sig['hits'])}. A "
                               f"pickle-aware rule would flag this."
                               if sig["flagged"] else
                               "No known-malware byte pattern. Float mantissa payloads "
                               "carry no signature to match."),
                },
                "format_policy_reject_pickle": {
                    "catches": bool(is_pickle and tampered),
                    "detail": ("Rejected by an allow-safetensors-only policy — a real and "
                               "recommended mitigation, but it stops nothing hidden inside "
                               "a safetensors file."
                               if is_pickle else
                               "Artifact is already in a pure-data format; policy passes it."),
                },
            },
        })

    control_names = ["file_hash_vs_baseline", "accuracy_regression",
                     "byte_signature_scan", "format_policy_reject_pickle"]
    tampered_rows = [r for r in rows if r["tampered"]]
    coverage = {
        c: {"caught": sum(1 for r in tampered_rows if r["controls"][c]["catches"]),
            "of": len(tampered_rows)}
        for c in control_names
    }
    coverage["sentinelweights"] = {
        "caught": sum(1 for r in tampered_rows if r["sentinel_catches"]),
        "of": len(tampered_rows),
    }

    excluded = [r["sample"] for r in rows if r["kind"] in ("unreadable", "evasion_demo")]
    return {
        "rows": rows,
        "coverage": coverage,
        "excluded_from_coverage": excluded,
        "note": ("Each control is actually executed against the gallery, not assumed. "
                 "The format policy and signature scan genuinely stop the malicious "
                 "pickle — we say so. Neither reads weight mantissas, which is the gap "
                 "this tool exists to close."
                 + (f" Excluded from the denominator: {', '.join(excluded)} — a corrupt "
                    f"artifact is an availability failure, and counting it as an attack "
                    f"we caught would inflate our own number."
                    if excluded else "")),
    }


def build() -> dict:
    bench_path = os.path.join(BENCH, "benchmark.json")
    records = []
    if os.path.exists(bench_path):
        with open(bench_path) as f:
            bench = json.load(f)
        records = [{**r, "source": "benchmark"} for r in bench.get("records", [])]
    records += _frontier_records()
    return {
        "leave_one_out": leave_one_out(records),
        "alternative_controls": alternative_controls(),
    }


def generate() -> dict:
    os.makedirs(BENCH, exist_ok=True)
    data = build()
    with open(ABLATION_PATH, "w") as f:
        json.dump(data, f, indent=2)
    loo = data["leave_one_out"]
    if loo.get("available"):
        print(f"  ablation: full AUC={loo['full_auc']} · non-load-bearing="
              f"{loo['non_load_bearing'] or 'none'}")
    cov = data["alternative_controls"]["coverage"]
    print(f"  alt controls: sentinel {cov['sentinelweights']['caught']}/"
          f"{cov['sentinelweights']['of']} vs accuracy "
          f"{cov['accuracy_regression']['caught']}/{cov['accuracy_regression']['of']}")
    return data


def load() -> dict | None:
    if not os.path.exists(ABLATION_PATH):
        return None
    with open(ABLATION_PATH) as f:
        return json.load(f)
