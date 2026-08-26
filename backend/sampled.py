"""Sampled scan for artifacts too large to read end to end.

The full pipeline reads every byte, which is fine for the gallery and wrong for
a production catalogue. This mode reads the safetensors header, picks whole
output channels at random, and seeks directly to those byte ranges. The file is
never loaded in full.

Sampling whole channels rather than arbitrary byte windows matters: the
per-channel and cross-layer detectors depend on tensor shape semantics, so a
sampled channel has to remain a real channel.

Because the answer is now an estimate, it is reported as one. We run several
independent replicates and publish the spread and the gate agreement across
them alongside the sampling fraction. A single number without a fraction and an
interval would be dishonest.
"""
from __future__ import annotations

import json
import os
import struct
import time

import numpy as np

import coverage as coverage_mod
import policy as policy_mod
from detectors import (l1_static, l2_bitplane, l2_window, l2_randfeat,
                       l2_distdiv, l2_precision, l2_crosslayer, l2_deadspace,
                       l2_contract, l4_fusion)
from ir import ModelIR, TensorRecord, sha256_file

_ST_ITEMSIZE = {"F64": 8, "F32": 4, "F16": 2, "BF16": 2, "I64": 8, "I32": 4,
                "I16": 2, "I8": 1, "U8": 1, "BOOL": 1}
_ST_NUMPY = {"F64": np.float64, "F32": np.float32, "F16": np.float16,
             "I64": np.int64, "I32": np.int32, "I16": np.int16, "I8": np.int8,
             "U8": np.uint8, "BOOL": np.bool_}

SMALL_TENSOR_ELEMS = 4096  # read these whole; sampling them buys nothing


# ----------------------------- header-only access -----------------------------

def read_header(path: str) -> tuple[dict, dict, int]:
    with open(path, "rb") as f:
        header_len = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(header_len).decode("utf-8"))
    metadata = header.pop("__metadata__", {}) if isinstance(header, dict) else {}
    return header, metadata, 8 + header_len


def _decode(dtype_str: str, buf: bytes, shape: tuple) -> np.ndarray:
    if dtype_str == "BF16":
        u16 = np.frombuffer(buf, dtype=np.uint16)
        return (u16.astype(np.uint32) << 16).view(np.float32).reshape(shape)
    return np.frombuffer(buf, dtype=_ST_NUMPY.get(dtype_str, np.uint8)).reshape(shape)


def _read_channels(f, data_start: int, info: dict, channels: np.ndarray) -> np.ndarray:
    """Seek-and-read whole output channels, preserving trailing dimensions."""
    dtype_str = info["dtype"]
    shape = tuple(info["shape"])
    itemsize = _ST_ITEMSIZE.get(dtype_str, 1)
    begin = data_start + info["data_offsets"][0]
    row_elems = int(np.prod(shape[1:])) if len(shape) > 1 else 1
    row_bytes = row_elems * itemsize

    chunks = []
    for c in sorted(int(x) for x in channels):
        f.seek(begin + c * row_bytes)
        chunks.append(f.read(row_bytes))
    buf = b"".join(chunks)
    out_shape = (len(chunks),) + shape[1:] if len(shape) > 1 else (len(chunks),)
    return _decode(dtype_str, buf, out_shape)


def build_sampled_ir(path: str, fraction: float, rng) -> tuple[ModelIR, dict]:
    header, metadata, data_start = read_header(path)
    tensors: list[TensorRecord] = []
    total_elems = 0
    read_elems = 0

    with open(path, "rb") as f:
        for name, info in header.items():
            shape = tuple(info["shape"])
            n_elems = int(np.prod(shape)) if shape else 0
            total_elems += n_elems
            if n_elems == 0:
                continue

            if n_elems <= SMALL_TENSOR_ELEMS or len(shape) < 2:
                itemsize = _ST_ITEMSIZE.get(info["dtype"], 1)
                f.seek(data_start + info["data_offsets"][0])
                vals = _decode(info["dtype"], f.read(n_elems * itemsize), shape)
                read_elems += n_elems
            else:
                n_out = shape[0]
                k = int(max(2, round(n_out * fraction)))
                k = min(k, n_out)
                chans = rng.choice(n_out, size=k, replace=False)
                vals = _read_channels(f, data_start, info, chans)
                read_elems += int(vals.size)

            tensors.append(TensorRecord(name=name, dtype=info["dtype"],
                                        shape=tuple(vals.shape), values=vals))

    ir = ModelIR(path=path, fmt="safetensors", tensors=tensors,
                 metadata=dict(metadata), weights_loadable=True,
                 load_note="Sampled read — whole output channels only; file never "
                           "loaded in full.")
    ir.provenance = {"filename": os.path.basename(path),
                     "size_bytes": os.path.getsize(path)}
    stats = {"total_params": total_elems, "sampled_params": read_elems,
             "sampling_fraction": (read_elems / total_elems) if total_elems else None,
             "num_tensors": len(header)}
    return ir, stats


def _names_only_ir(path: str) -> ModelIR:
    """Header-derived IR for the static/metadata pass — reads no weight bytes."""
    header, metadata, _ = read_header(path)
    tensors = [TensorRecord(name=n, dtype=i["dtype"], shape=tuple(i["shape"]),
                            values=None,
                            n_params=int(np.prod(i["shape"])) if i["shape"] else 0)
               for n, i in header.items()]
    ir = ModelIR(path=path, fmt="safetensors", tensors=tensors,
                 metadata=dict(metadata), weights_loadable=True,
                 load_note="Header-only pass for static forensics.")
    ir.provenance = {"filename": os.path.basename(path),
                     "size_bytes": os.path.getsize(path)}
    return ir


# ----------------------------- the sampled scan -----------------------------

def _replicate(path: str, fraction: float, l1_res: dict, rng) -> dict:
    the_ir, stats = build_sampled_ir(path, fraction, rng)
    results = {"l1_static": l1_res}
    for key, mod in (("l2_bitplane", l2_bitplane), ("l2_window", l2_window),
                     ("l2_randfeat", l2_randfeat), ("l2_distdiv", l2_distdiv),
                     ("l2_precision", l2_precision), ("l2_crosslayer", l2_crosslayer),
                     ("l2_deadspace", l2_deadspace), ("l2_contract", l2_contract)):
        results[key] = mod.run(the_ir)
    results["l3_backdoor"] = {"detector": "l3_backdoor", "coverage": "Not applicable",
                              "score": 0.0, "z": 0.0,
                              "summary": "Behavioral probe not run in sampled mode."}
    fusion = l4_fusion.fuse(results, l1_res)
    decision = policy_mod.decide(fusion["risk_score"], l1_res, True, "safetensors")
    return {"risk_score": decision["risk_score"], "gate": decision["gate"],
            "band": decision["band"], "stats": stats, "results": results,
            "fusion": fusion}


def scan(path: str, fraction: float = 0.05, replicates: int = 8,
         seed: int = 0) -> dict:
    if not path.endswith(".safetensors"):
        return {"supported": False,
                "reason": "Sampled mode implements selective reads for safetensors only."}

    t0 = time.perf_counter()
    l1_ir = _names_only_ir(path)
    l1_res = l1_static.run(l1_ir)
    l1_ms = int((time.perf_counter() - t0) * 1000)

    reps = []
    for r in range(max(2, replicates)):
        rng = np.random.default_rng(seed + r)
        t = time.perf_counter()
        rep = _replicate(path, fraction, l1_res, rng)
        rep["ms"] = int((time.perf_counter() - t) * 1000)
        reps.append(rep)

    scores = np.array([r["risk_score"] for r in reps], dtype=float)
    gates = [r["gate"] for r in reps]
    modal_gate = max(set(gates), key=gates.count)
    agreement = gates.count(modal_gate) / len(gates)

    last = reps[-1]
    cov = coverage_mod.summarize(last["results"])
    lo, hi = np.percentile(scores, [2.5, 97.5])
    size_mb = os.path.getsize(path) / (1024 * 1024)
    read_mb = size_mb * (last["stats"]["sampling_fraction"] or 0)
    total_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "supported": True,
        "mode": "sampled",
        "file": {"filename": os.path.basename(path),
                 "size_mb": round(size_mb, 2),
                 "num_tensors": last["stats"]["num_tensors"],
                 "total_params": last["stats"]["total_params"]},
        "sampling": {
            "requested_fraction": fraction,
            "achieved_fraction": round(last["stats"]["sampling_fraction"] or 0, 5),
            "sampled_params": last["stats"]["sampled_params"],
            "bytes_read_mb": round(read_mb, 2),
            "replicates": len(reps),
            "unit": "whole output channels",
        },
        "estimate": {
            "risk_score_mean": round(float(scores.mean()), 1),
            "risk_score_min": round(float(scores.min()), 1),
            "risk_score_max": round(float(scores.max()), 1),
            "risk_score_std": round(float(scores.std(ddof=1)) if len(scores) > 1 else 0.0, 2),
            "ci95": [round(float(lo), 1), round(float(hi), 1)],
            "gate": modal_gate,
            "gate_agreement": round(agreement, 3),
            "gate_stable": agreement == 1.0,
            "per_replicate": [{"risk_score": r["risk_score"], "gate": r["gate"],
                               "ms": r["ms"]} for r in reps],
        },
        "coverage": cov,
        "timing": {"static_ms": l1_ms, "total_ms": total_ms,
                   "mean_replicate_ms": int(np.mean([r["ms"] for r in reps]))},
        "caveats": [
            "This is an estimate over sampled channels, not a full read. The interval "
            "and the sampling fraction are part of the result.",
            "Behavioral (Tier 3) coverage is Not applicable in sampled mode.",
            f"Gate agreed across {gates.count(modal_gate)}/{len(gates)} independent "
            f"replicates." + ("" if agreement == 1.0 else
                              " Disagreement means this artifact sits near a band edge "
                              "and needs a full scan before any release decision."),
            "A localized payload confined to unsampled channels can be missed; raise "
            "the fraction for release gating and use sampled mode for triage.",
        ],
    }


# ----------------------------- large demo fixture -----------------------------

def make_large_fixture(path: str, target_mb: int = 96, embed_payload: bool = False,
                       seed: int = 0) -> dict:
    """Build a large safetensors artifact locally so scale claims are testable."""
    from safetensors.numpy import save_file
    from samples.make_samples import export_quantize, train_clean_cnn

    rng = np.random.default_rng(seed)
    base = train_clean_cnn(seed=seed, steps=120)
    stem = base["conv3.weight"]  # (64, 32, 3, 3)

    target_bytes = target_mb * 1024 * 1024
    block_elems = 512 * 256
    n_blocks = max(1, target_bytes // (block_elems * 4))

    state: dict[str, np.ndarray] = {}
    flat = stem.ravel().astype(np.float32)
    for i in range(int(n_blocks)):
        tile = np.resize(flat, block_elems).reshape(512, 256)
        tile = tile * (1.0 + rng.standard_normal((512, 1)).astype(np.float32) * 0.03)
        state[f"blocks.{i}.weight"] = np.ascontiguousarray(tile)
    state["classifier.weight"] = np.ascontiguousarray(base["fc2.weight"])
    state["classifier.bias"] = np.ascontiguousarray(base["fc2.bias"])

    state = export_quantize(state, n_keep_mantissa=12)

    payload_note = "no payload"
    if embed_payload:
        import adversary
        target = f"blocks.{int(n_blocks) // 2}.weight"
        state, meta = adversary.forge(state, n_bytes=16384, n_planes=6, bit_offset=0,
                                     layout="contiguous", tensor=target, seed=seed + 1)
        payload_note = (f"{meta['effective_bytes']} B in {target} "
                        f"(1 of {int(n_blocks)} blocks)")

    save_file({k: np.ascontiguousarray(v) for k, v in state.items()}, path)
    return {"path": path, "size_mb": round(os.path.getsize(path) / (1024 * 1024), 2),
            "num_tensors": len(state), "payload": payload_note}
