"""Sealed holdout — evaluated on a recipe we did not calibrate against.

Everything in `bench/benchmark.json` shares a recipe with the gallery: fp32,
export-quantized to 12 mantissa bits, uniform-random payload written into
`conv3.weight` across 6 low planes. Thresholds and empirical baselines were
fitted in that world, so measuring there is partly self-congratulation.

This module changes the parts an attacker or a vendor would plausibly change,
and none of it feeds threshold selection or baseline fitting:

  export contract   14 kept mantissa bits as well as 12
  dtype             float16 as well as float32
  structure         channel-pruned variants (different shapes)
  target tensor     conv1.weight and fc1.weight, never conv3.weight
  bit depth         3 / 5 / 7 planes, with a non-zero plane offset
  layout            per-channel and scattered
  payload entropy   zlib-compressed filler instead of uniform random

Reported separately and labelled. Where it degrades, we say so.
"""
from __future__ import annotations

import json
import os

import numpy as np

import adversary

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(HERE, "bench", "results")
HOLDOUT_PATH = os.path.join(BENCH, "holdout.json")

POLICY_THR = 51.0
BLOCKING = ("HARD_BLOCK", "REVIEW", "QUARANTINE")

RECIPE_DELTAS = {
    "export_mantissa_bits": {"calibrated": [12], "holdout": [12, 14, "fp16/6"]},
    "dtype": {"calibrated": ["float32"], "holdout": ["float32", "float16"]},
    "structure": {"calibrated": ["full"], "holdout": ["full", "channel_pruned"]},
    "target_tensor": {"calibrated": ["conv3.weight"],
                      "holdout": ["conv2.weight", "fc1.weight"]},
    "bit_planes": {"calibrated": [6], "holdout": [3, 5, 7]},
    "plane_offset": {"calibrated": [0], "holdout": [0, 2]},
    "layout": {"calibrated": ["contiguous", "scattered"],
               "holdout": ["scattered", "per_channel"]},
    "payload_entropy": {"calibrated": ["uniform_random"], "holdout": ["zlib_compressed"]},
    "seeds": {"calibrated": "0-3999", "holdout": "7000+"},
}

# Below this a config never had room for a meaningful payload, so scoring it as a
# miss would flatter or damage the result for the wrong reason.
MIN_EFFECTIVE_BYTES = 256


# ----------------------------- unseen clean variants -----------------------------

def _prune_channels(state: dict, keep_frac: float = 0.75) -> dict:
    """Structured channel pruning — legitimate, and a genuine false-positive risk."""
    out = {}
    for k, v in state.items():
        if isinstance(v, np.ndarray) and v.ndim >= 2 and v.shape[0] > 4:
            keep = max(2, int(v.shape[0] * keep_frac))
            out[k] = np.ascontiguousarray(v[:keep])
        else:
            out[k] = v.copy() if isinstance(v, np.ndarray) else v
    return out


def _to_fp16(state: dict) -> dict:
    return {k: (v.astype(np.float16) if isinstance(v, np.ndarray) and v.dtype == np.float32
                else v) for k, v in state.items()}


def _export_quantize_fp16(state: dict, n_keep_mantissa: int = 6) -> dict:
    """An fp16 export contract, so the freed-region logic is tested on a dtype
    whose baseline was never fitted."""
    out = {}
    n_clear = 10 - n_keep_mantissa
    mask = np.uint16(~((1 << n_clear) - 1) & 0xFFFF)
    for k, v in state.items():
        if isinstance(v, np.ndarray) and v.dtype == np.float16:
            bits = v.ravel().view(np.uint16).copy() & mask
            out[k] = bits.view(np.float16).reshape(v.shape)
        else:
            out[k] = v.copy() if isinstance(v, np.ndarray) else v
    return out


# ----------------------------- fp16 embedding -----------------------------

def _embed_fp16(state: dict, tensor: str, n_bytes: int, n_planes: int,
                bit_offset: int, layout: str, seed: int) -> tuple[dict, dict]:
    """Direct uint16 mantissa embedding — fp16 has only 10 mantissa bits."""
    rng = np.random.default_rng(seed)
    out = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in state.items()}
    if tensor not in out or out[tensor].dtype != np.float16:
        return out, {"supported": False, "reason": f"{tensor} is not float16"}

    host = out[tensor]
    bits = host.ravel().view(np.uint16).copy()
    planes = [p for p in range(bit_offset, bit_offset + n_planes) if p <= 9]
    if not planes:
        return out, {"supported": False, "reason": "no fp16 mantissa planes in range"}

    needed = int(np.ceil(n_bytes * 8 / len(planes)))
    n_slots = bits.size
    if layout == "scattered":
        idx = rng.choice(n_slots, size=min(needed, n_slots), replace=False)
    elif layout == "per_channel" and host.ndim >= 2:
        row = int(np.prod(host.shape[1:]))
        per = max(1, int(np.ceil(needed / host.shape[0])))
        idx = np.concatenate([np.arange(c * row, min(c * row + per, n_slots))
                              for c in range(host.shape[0])])[:needed]
    else:
        idx = np.arange(0, min(needed, n_slots))

    mask = np.uint16(0xFFFF)
    for p in planes:
        mask &= np.uint16(~(1 << p) & 0xFFFF)
    span = int((1 << len(planes)) - 1)
    low = (rng.integers(0, span + 1, size=idx.size).astype(np.uint16)) << np.uint16(planes[0])
    bits[idx] = (bits[idx] & mask) | low
    out[tensor] = bits.view(np.float16).reshape(host.shape)
    return out, {"supported": True, "effective_bytes": int(idx.size * len(planes) // 8),
                 "planes": planes, "slots_touched": int(idx.size)}


# ----------------------------- evaluation -----------------------------

def _evaluate(state: dict, tag: str) -> dict:
    rep = adversary.scan_state(state, tag=tag)
    v = rep["verdict"]
    return {"risk_score": v["risk_score"], "gate": v["gate"],
            "flagged": v["gate"] in BLOCKING}


def build(n_clean_per_variant: int = 3) -> dict:
    from samples.make_samples import train_clean_cnn, export_quantize

    clean_rows, attack_rows = [], []

    # ---- unseen clean variants (false-positive pressure) ----
    for i in range(n_clean_per_variant):
        raw = train_clean_cnn(seed=7000 + i, steps=320)
        for n_keep in (12, 14):
            st = export_quantize(raw, n_keep_mantissa=n_keep)
            r = _evaluate(st, "hold_clean")
            clean_rows.append({"variant": f"fp32_keep{n_keep}", "seed": 7000 + i,
                               "dtype": "float32", "export_mantissa_bits": n_keep,
                               "structure": "full", **r})

        st12 = export_quantize(raw, n_keep_mantissa=12)
        fp16_full = _to_fp16(st12)
        r = _evaluate(fp16_full, "hold_clean_fp16")
        clean_rows.append({"variant": "fp16_full_precision", "seed": 7000 + i,
                           "dtype": "float16", "export_mantissa_bits": 10,
                           "structure": "full", **r})

        r = _evaluate(_export_quantize_fp16(fp16_full, 6), "hold_clean_fp16q")
        clean_rows.append({"variant": "fp16_keep6", "seed": 7000 + i,
                           "dtype": "float16", "export_mantissa_bits": 6,
                           "structure": "full", **r})

        r = _evaluate(_prune_channels(st12, 0.75), "hold_clean_pruned")
        clean_rows.append({"variant": "fp32_channel_pruned", "seed": 7000 + i,
                           "dtype": "float32", "export_mantissa_bits": 12,
                           "structure": "channel_pruned", **r})

    # ---- unseen attack recipes ----
    base_raw = train_clean_cnn(seed=7100, steps=320)
    base = export_quantize(base_raw, n_keep_mantissa=12)

    for tensor in ("conv2.weight", "fc1.weight"):
        for n_planes in (3, 5, 7):
            for layout in ("scattered", "per_channel"):
                offset = 2 if n_planes <= 5 else 0
                res = adversary.forge_and_scan(
                    base, n_bytes=3072, n_planes=n_planes, bit_offset=offset,
                    layout=layout, tensor=tensor, payload_kind="compressed",
                    seed=7200 + n_planes)
                if not res.get("supported"):
                    continue
                v = res["verdict"]
                attack_rows.append({
                    "dtype": "float32", "tensor": tensor, "n_planes": n_planes,
                    "bit_offset": offset, "layout": layout,
                    "payload": "zlib_compressed",
                    "effective_bytes": res["attack"]["effective_bytes"],
                    "risk_score": v["risk_score"], "gate": v["gate"],
                    "flagged": v["gate"] in BLOCKING,
                    "output_agreement_pct": res["fidelity"].get("output_agreement_pct"),
                    "loudest_detector": res["loudest_detector"],
                })

    # fp16 attacks under an fp16 export contract — a dtype whose baseline was
    # never fitted, embedded in planes that contract actually frees.
    base16 = _export_quantize_fp16(_to_fp16(base), 6)
    for tensor in ("conv2.weight", "fc1.weight"):
        for n_planes in (3, 4):
            st, meta = _embed_fp16(base16, tensor, 2048, n_planes, 0, "scattered", 7300)
            if not meta.get("supported"):
                continue
            r = _evaluate(st, "hold_atk_fp16")
            attack_rows.append({
                "dtype": "float16", "tensor": tensor, "n_planes": n_planes,
                "bit_offset": 0, "layout": "scattered", "payload": "uniform_random",
                "effective_bytes": meta["effective_bytes"], **r,
                "output_agreement_pct": None, "loudest_detector": None,
            })

    negligible = [r for r in attack_rows
                  if r.get("effective_bytes", 0) < MIN_EFFECTIVE_BYTES]
    scored_attacks = [r for r in attack_rows
                      if r.get("effective_bytes", 0) >= MIN_EFFECTIVE_BYTES]

    n_clean = len(clean_rows)
    n_atk = len(scored_attacks)
    fp = sum(1 for r in clean_rows if r["flagged"])
    tp = sum(1 for r in scored_attacks if r["flagged"])

    missed = [r for r in scored_attacks if not r["flagged"]]
    false_alarms = [r for r in clean_rows if r["flagged"]]

    return {
        "sealed": True,
        "used_for_calibration": False,
        "recipe_deltas": RECIPE_DELTAS,
        "clean_rows": clean_rows,
        "attack_rows": attack_rows,
        "negligible_capacity": negligible,
        "metrics": {
            "clean_n": n_clean, "attack_n": n_atk,
            "true_positives": tp, "false_negatives": n_atk - tp,
            "false_positives": fp, "true_negatives": n_clean - fp,
            "tpr": round(tp / n_atk, 3) if n_atk else None,
            "fpr": round(fp / n_clean, 3) if n_clean else None,
            "operating_point": f"risk_score >= {POLICY_THR:.0f}",
            "excluded_negligible_capacity": len(negligible),
            "min_effective_bytes": MIN_EFFECTIVE_BYTES,
        },
        "misses": missed,
        "false_alarms": false_alarms,
        "notes": [
            "No holdout artifact contributed to threshold selection, fusion weights, "
            "or empirical bit-plane baseline fitting.",
            "Architecture family is held constant; only the export contract, dtype, "
            "structure, target tensor, bit depth, layout, and payload entropy vary. "
            "Cross-architecture generalization is untested and we do not claim it.",
            "float16 attacks are embedded directly in uint16 mantissa planes; the "
            "empirical baseline for F16 is derived from the F32 fit, so this is the "
            "weakest-supported column and is reported rather than hidden.",
        ],
    }


def generate(n_clean_per_variant: int = 3) -> dict:
    os.makedirs(BENCH, exist_ok=True)
    data = build(n_clean_per_variant)
    with open(HOLDOUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    m = data["metrics"]
    print(f"  holdout (unseen recipe): TPR={m['tpr']} ({m['true_positives']}/{m['attack_n']}) "
          f"· FPR={m['fpr']} ({m['false_positives']}/{m['clean_n']})")
    return data


def load() -> dict | None:
    if not os.path.exists(HOLDOUT_PATH):
        return None
    with open(HOLDOUT_PATH) as f:
        return json.load(f)
