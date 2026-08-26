"""Layer 4 — Transparent risk fusion + experimental anomaly head.

Fusion: risk = 100 * sigmoid(b + Σ w_i z_i), with correlated stego signals
GROUPED so the same anomaly isn't triple-counted. The weight table is exposed.
"""
from __future__ import annotations

import json
import os

import numpy as np

_ANOMALY_MODEL = None
_ANOMALY_READY = False

# Exposed, fixed demo weights (would be learned at GE scale).
BIAS = -4.2
WEIGHTS = {
    "static_review": 0.6,     # non-critical L1 review findings
    "stego_group": 1.35,      # bitplane + window + randfeat + distdiv + contract (grouped, max)
    "crosslayer": 0.7,        # PDF-required layer-coupling signal (orthogonal to stego_group)
    "precision": 0.5,
    "deadspace": 0.35,        # supporting: high-entropy LSBs in near-zero weights
    "backdoor": 0.80,         # L3 trigger recovery — primary path for functional backdoors
}

FEATURE_ORDER = ["bitplane_z", "window_z", "randfeat_z", "distdiv_z",
                 "crosslayer_z", "precision_z", "deadspace_z", "contract_z",
                 "backdoor_z"]


def _sigmoid(u):
    return 1.0 / (1.0 + np.exp(-u))


def build_feature_vector(results: dict) -> dict:
    def z(name):
        return float(results.get(name, {}).get("z", 0.0) or 0.0)
    return {
        "bitplane_z": z("l2_bitplane"),
        "window_z": z("l2_window"),
        "randfeat_z": z("l2_randfeat"),
        "distdiv_z": z("l2_distdiv"),
        "crosslayer_z": z("l2_crosslayer"),
        "precision_z": z("l2_precision"),
        "deadspace_z": z("l2_deadspace"),
        "contract_z": z("l2_contract"),
        "backdoor_z": z("l3_backdoor"),
    }


def static_review_level(l1_result: dict) -> float:
    n_review = sum(1 for f in l1_result.get("findings", [])
                   if f.get("severity") in ("REVIEW", "MEDIUM", "HIGH"))
    return min(3.0, float(n_review))


def decompose(feats: dict, static_review: float = 0.0,
              weights: dict | None = None) -> dict:
    """Grouping + weighted contributions. Single source of fusion truth.

    Ablation and the live pipeline both route through here so an experiment can
    never silently diverge from the shipped scoring.
    """
    W = WEIGHTS if weights is None else weights

    # Group correlated hidden-data signals and take their max, so one payload
    # cannot be counted five times. l2_contract joins the group rather than
    # earning its own weight: it measures the same phenomenon the entropy tests
    # do, just with a count instead of a threshold.
    stego_group = max(feats["bitplane_z"], feats["window_z"],
                      feats["randfeat_z"], feats["distdiv_z"],
                      feats.get("contract_z", 0.0))
    # When Neural-Cleanse recovers a trigger, L3 owns the narrative — do not let
    # incidental LSB noise on tiny synthetic nets push HARD_BLOCK alone.
    if feats["backdoor_z"] >= 4.0:
        stego_group = min(stego_group, 0.5)

    contributions = {
        "static_review": W["static_review"] * static_review,
        "stego_group": W["stego_group"] * stego_group,
        "crosslayer": W["crosslayer"] * feats["crosslayer_z"],
        "precision": W["precision"] * feats["precision_z"],
        "deadspace": W["deadspace"] * feats["deadspace_z"],
        "backdoor": W["backdoor"] * feats["backdoor_z"],
    }
    risk = float(100.0 * _sigmoid(BIAS + sum(contributions.values())))
    return {"risk_score": risk, "stego_group": stego_group,
            "static_review": static_review, "contributions": contributions}


def score_from_features(feats: dict, static_review: float = 0.0,
                        weights: dict | None = None) -> float:
    """Risk score for a stored feature vector — used by the ablation harness."""
    full = {k: float(feats.get(k, 0.0) or 0.0) for k in FEATURE_ORDER}
    return decompose(full, static_review, weights)["risk_score"]


def fuse(results: dict, l1_result: dict) -> dict:
    feats = build_feature_vector(results)
    static_review = static_review_level(l1_result)
    d = decompose(feats, static_review)

    return {
        "risk_score": round(d["risk_score"], 1),
        "features": feats,
        "grouped": {"stego_group": round(d["stego_group"], 3),
                    "static_review": static_review},
        "weights": WEIGHTS,
        "bias": BIAS,
        "contributions": {k: round(v, 3) for k, v in d["contributions"].items()},
        "anomaly_head": _anomaly_score(feats),
    }


# ---------------- experimental anomaly head ----------------

def _corpus_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "samples", "snapshots", "anomaly_corpus.json")


def init_anomaly_head():
    global _ANOMALY_MODEL, _ANOMALY_READY
    path = _corpus_path()
    if not os.path.exists(path):
        _ANOMALY_READY = False
        return
    try:
        from sklearn.ensemble import IsolationForest
        with open(path) as f:
            corpus = json.load(f)
        X = np.array([[row.get(k, 0.0) for k in FEATURE_ORDER] for row in corpus], dtype=float)
        model = IsolationForest(n_estimators=150, contamination=0.05, random_state=0)
        model.fit(X)
        _ANOMALY_MODEL = model
        _ANOMALY_READY = True
    except Exception:
        _ANOMALY_READY = False


def _anomaly_score(feats: dict) -> dict:
    if not _ANOMALY_READY or _ANOMALY_MODEL is None:
        return {"available": False, "score": 0.0,
                "label": "experimental head not initialized"}
    x = np.array([[feats[k] for k in FEATURE_ORDER]], dtype=float)
    raw = float(_ANOMALY_MODEL.decision_function(x)[0])  # higher = more normal
    is_outlier = bool(_ANOMALY_MODEL.predict(x)[0] == -1)
    # map to 0..100 novelty
    novelty = float(max(0.0, min(100.0, 50.0 - raw * 120.0)))
    return {"available": True, "score": round(novelty, 1),
            "outlier": is_outlier,
            "label": "experimental — side-channel; only lifts verdict if corroborated"}
