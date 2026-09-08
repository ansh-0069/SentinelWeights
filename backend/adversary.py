"""Adversary Lab — the evaluator authors the attack, we scan it live.

Defensive only. Payloads are inert pseudo-random bytes or compressed filler
text; nothing here builds malware. The module writes bits into float mantissas
so we can measure our own detector envelope instead of asserting it.

Three attacker knobs matter, and they trade off against each other:

  capacity      how many payload bytes fit
  detectability how loudly our L2 detectors respond
  fidelity      how close the tampered model stays to the original

`entropy_matched` is the interesting case. An attacker who has read our
methodology can draw payload bits from the clean model's own per-plane
marginals, which flattens the bit-plane entropy signal. Under a declared
export-quantize contract the freed low planes are near-zero, so matching them
means encoding at ~H(p) bits per slot -- the capacity collapses toward zero.
To recover capacity the attacker must move up into the *kept* planes, which
costs fidelity and lights up the precision / cross-layer detectors instead.
That trade is the honest result this module exists to demonstrate.
"""
from __future__ import annotations

import os
import tempfile
import zlib

import numpy as np

from detectors.common import binary_entropy

MAX_PLANE = 22  # fp32 mantissa is b0..b22


# ----------------------------- payload sources -----------------------------

def make_payload(n_bytes: int, kind: str = "random", seed: int = 42) -> bytes:
    """Inert payload bytes. 'compressed' is deliberately lower-entropy."""
    rng = np.random.default_rng(seed)
    if kind == "compressed":
        filler = (b"INERT DEMO PAYLOAD - sentinelweights adversary lab. " * 512)
        blob = zlib.compress(filler, 9)
        while len(blob) < n_bytes:
            blob += zlib.compress(filler + bytes(rng.integers(0, 255, 64, dtype=np.uint8)), 9)
        return blob[:n_bytes]
    return rng.integers(0, 256, size=n_bytes, dtype=np.uint8).tobytes()


# ----------------------------- bit helpers -----------------------------

def _float_tensor_names(state: dict) -> list[str]:
    names = [k for k, v in state.items()
             if isinstance(v, np.ndarray) and v.dtype == np.float32 and v.size > 64]
    return sorted(names, key=lambda k: -state[k].size)


def plane_probs(values: np.ndarray, planes: list[int]) -> list[float]:
    """Measured P(bit==1) at each requested mantissa plane."""
    bits = values.astype(np.float32).ravel().view(np.uint32)
    if bits.size == 0:
        return [0.0] * len(planes)
    return [float(((bits >> np.uint32(k)) & np.uint32(1)).mean()) for k in planes]


def bits_per_slot(values: np.ndarray, planes: list[int], entropy_matched: bool) -> float:
    """Payload bits carryable per touched weight.

    Naive embedding overwrites each plane outright, so every plane carries a
    full bit. A distribution-matched attacker is limited to the entropy the
    clean model already exhibits at that plane.
    """
    if not entropy_matched:
        return float(len(planes))
    return float(sum(binary_entropy(p) for p in plane_probs(values, planes)))


def _slot_indices(n_slots: int, needed: int, layout: str, shape: tuple,
                  start_frac: float, rng) -> np.ndarray:
    needed = int(min(needed, n_slots))
    if needed <= 0:
        return np.array([], dtype=np.int64)
    if layout == "scattered":
        return rng.choice(n_slots, size=needed, replace=False)
    if layout == "per_channel" and len(shape) >= 2:
        # A few slots at the head of every output channel -- low per-window
        # density, which is precisely what a naive single-window scan misses.
        n_out = shape[0]
        per = max(1, int(np.ceil(needed / n_out)))
        row = int(np.prod(shape[1:]))
        idx = np.concatenate([np.arange(c * row, min(c * row + per, n_slots))
                              for c in range(n_out)])
        return idx[:needed]
    start = int(start_frac * n_slots)
    if start + needed > n_slots:
        start = max(0, n_slots - needed)
    return np.arange(start, start + needed)


# ----------------------------- the forge -----------------------------

def forge(base: dict[str, np.ndarray], *, n_bytes: int = 4096, n_planes: int = 6,
          bit_offset: int = 0, layout: str = "contiguous",
          entropy_matched: bool = False, spread_tensors: int = 1,
          tensor: str | None = None, payload_kind: str = "random",
          start_frac: float = 0.25, seed: int = 42) -> tuple[dict, dict]:
    """Embed an inert payload under the requested attack configuration.

    Returns (tampered_state, attack_meta). `attack_meta` reports the *effective*
    capacity, which is where entropy matching gets expensive.
    """
    rng = np.random.default_rng(seed)
    out = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in base.items()}

    bit_offset = int(max(0, min(MAX_PLANE, bit_offset)))
    n_planes = int(max(1, min(8, n_planes)))
    planes = [p for p in range(bit_offset, bit_offset + n_planes) if p <= MAX_PLANE]
    if not planes:
        planes = [0]

    candidates = _float_tensor_names(base)
    if tensor and tensor in candidates:
        targets = [tensor]
    else:
        targets = candidates[:max(1, int(spread_tensors))]
    if not targets:
        return out, {"supported": False,
                     "reason": "No float32 tensor large enough to host a payload."}

    payload = make_payload(int(n_bytes), payload_kind, seed)
    payload_stream = np.unpackbits(
        np.frombuffer(payload, dtype=np.uint8), bitorder="little"
    ).astype(np.uint32)
    payload_bits_needed = int(payload_stream.size)
    per_tensor_bits = payload_bits_needed / len(targets)
    payload_cursor = 0

    clear_mask = np.uint32(0xFFFFFFFF)
    for p in planes:
        clear_mask &= np.uint32(~(1 << p) & 0xFFFFFFFF)

    placed_bits = 0.0
    touched = 0
    plane_report: list[dict] = []

    for name in targets:
        host = out[name].astype(np.float32)
        bits = host.ravel().view(np.uint32).copy()
        rate = bits_per_slot(base[name], planes, entropy_matched)
        if rate <= 1e-9:
            plane_report.append({"tensor": name, "bits_per_slot": 0.0,
                                 "note": "clean planes carry no entropy — nothing to hide in"})
            continue
        needed = int(np.ceil(per_tensor_bits / rate))
        idx = _slot_indices(bits.size, needed, layout, tuple(host.shape), start_frac, rng)
        if idx.size == 0:
            continue

        if entropy_matched:
            probs = plane_probs(base[name], planes)
            new_low = np.zeros(idx.size, dtype=np.uint32)
            for p, pr in zip(planes, probs):
                draw = (rng.random(idx.size) < pr).astype(np.uint32)
                new_low |= draw << np.uint32(p)
        else:
            # Encode the requested inert payload itself, rather than merely
            # generating unrelated random plane values. One bit is written to
            # each selected plane of each touched weight.
            available = int(idx.size * len(planes))
            remaining = payload_stream[payload_cursor:payload_cursor + available]
            new_low = np.zeros(idx.size, dtype=np.uint32)
            if remaining.size:
                padded = np.zeros(available, dtype=np.uint32)
                padded[:remaining.size] = remaining
                matrix = padded.reshape(idx.size, len(planes))
                for column, plane in enumerate(planes):
                    new_low |= matrix[:, column] << np.uint32(plane)
            payload_cursor += int(remaining.size)

        bits[idx] = (bits[idx] & clear_mask) | new_low
        out[name] = bits.view(np.float32).reshape(host.shape)
        placed_bits += (idx.size * rate if entropy_matched else remaining.size)
        touched += int(idx.size)
        plane_report.append({"tensor": name, "slots": int(idx.size),
                             "bits_per_slot": round(rate, 3)})

    effective_bytes = int(min(n_bytes, placed_bits // 8))
    meta = {
        "supported": True,
        "requested_bytes": int(n_bytes),
        "effective_bytes": effective_bytes,
        "capacity_shortfall": int(n_bytes) - effective_bytes,
        "planes": planes,
        "bit_offset": bit_offset,
        "n_planes": len(planes),
        "layout": layout,
        "entropy_matched": bool(entropy_matched),
        "payload_kind": payload_kind,
        "targets": targets,
        "slots_touched": touched,
        "per_tensor": plane_report,
        "note": ("Distribution-matched embedding is limited to the entropy the clean "
                 "model already shows at those planes."
                 if entropy_matched else
                 "Naive embedding overwrites the planes outright — maximum capacity, "
                 "maximum entropy signature."),
    }
    return out, meta


def preview(base: dict[str, np.ndarray], *, n_bytes: int = 4096, n_planes: int = 6,
            bit_offset: int = 0, layout: str = "contiguous",
            entropy_matched: bool = False, spread_tensors: int = 1,
            tensor: str | None = None, payload_kind: str = "random",
            start_frac: float = 0.25, seed: int = 42) -> dict:
    """Estimate usable capacity without modifying or scanning the model."""
    del layout, payload_kind, start_frac, seed  # do not affect raw capacity
    bit_offset = int(max(0, min(MAX_PLANE, bit_offset)))
    n_planes = int(max(1, min(8, n_planes)))
    planes = [p for p in range(bit_offset, bit_offset + n_planes) if p <= MAX_PLANE]
    candidates = _float_tensor_names(base)
    targets = ([tensor] if tensor and tensor in candidates
               else candidates[:max(1, int(spread_tensors))])
    if not targets or not planes:
        return {"supported": False, "requested_bytes": int(n_bytes),
                "capacity_bytes": 0, "effective_bytes": 0, "targets": []}
    capacity_bits = sum(
        base[name].size * bits_per_slot(base[name], planes, entropy_matched)
        for name in targets
    )
    capacity_bytes = int(capacity_bits // 8)
    return {
        "supported": True,
        "requested_bytes": int(n_bytes),
        "capacity_bytes": capacity_bytes,
        "effective_bytes": min(int(n_bytes), capacity_bytes),
        "capacity_shortfall": max(0, int(n_bytes) - capacity_bytes),
        "targets": targets,
        "planes": planes,
        "precision_floor": 11,
        "note": ("Estimated from the clean model's measured per-plane entropy."
                 if entropy_matched else
                 "Each selected plane carries one payload bit per available weight."),
    }


# ----------------------------- forge + scan -----------------------------

def _write_temp(state: dict, tag: str = "forged") -> str:
    from safetensors.numpy import save_file
    fd, path = tempfile.mkstemp(prefix=f"sw_{tag}_", suffix=".safetensors")
    os.close(fd)
    save_file({k: np.ascontiguousarray(v) for k, v in state.items()
               if isinstance(v, np.ndarray)}, path)
    return path


DETECTOR_KEYS = ["l2_bitplane", "l2_window", "l2_randfeat", "l2_distdiv",
                 "l2_crosslayer", "l2_precision", "l2_deadspace", "l2_contract"]


def scan_path(path: str) -> dict:
    import orchestrator
    from ir import sha256_file
    orchestrator._CACHE.pop(sha256_file(path), None)
    return orchestrator.scan(path)


def scan_state(state: dict, tag: str = "forged") -> dict:
    """Run the real pipeline over an in-memory state dict."""
    path = _write_temp(state, tag)
    try:
        return scan_path(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def forge_and_scan(base: dict[str, np.ndarray], artifact_hook=None, **kw) -> dict:
    """Author an attack, scan it with the full pipeline, measure all three axes.

    `artifact_hook(path)` runs against the forged file before it is deleted, so
    a caller can compare it to an attested baseline without re-forging.
    """
    from samples.make_samples import probe_output_agreement

    tampered, meta = forge(base, **kw)
    if not meta.get("supported"):
        return {"attack": meta, "supported": False}

    path = _write_temp(tampered, "forge")
    try:
        report = scan_path(path)
        hook_result = artifact_hook(path) if artifact_hook else None
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    fidelity = probe_output_agreement(base, tampered)
    dets = {k: round(float(report["detectors"].get(k, {}).get("z") or 0.0), 3)
            for k in DETECTOR_KEYS}

    verdict = report["verdict"]
    evaded = verdict["gate"] in ("APPROVE", "APPROVE_WITH_CAVEATS")
    out = {
        "supported": True,
        "attack": meta,
        "verdict": verdict,
        "detector_z": dets,
        "loudest_detector": max(dets, key=dets.get) if dets else None,
        "fidelity": fidelity,
        "regions": report.get("regions", [])[:6],
        "contract": report["detectors"].get("l2_contract", {}).get("violations", [])[:4],
        "fusion": {"contributions": report["fusion"]["contributions"],
                   "risk_score": report["fusion"]["risk_score"]},
        "features": report["fusion"]["features"],
        "static_review": report["fusion"]["grouped"]["static_review"],
        "total_ms": report.get("total_ms"),
        "evaded": evaded,
    }
    if hook_result:
        out["attestation"] = hook_result
    out["interpretation"] = _interpret(meta, verdict, fidelity, dets, hook_result)
    return out


def _interpret(meta: dict, verdict: dict, fidelity: dict, dets: dict,
               attestation: dict | None = None) -> str:
    gate = verdict["gate"]
    agree = fidelity.get("output_agreement_pct")
    eff = meta["effective_bytes"]

    if eff == 0:
        return ("Zero effective capacity. Matching the clean model's own plane "
                "distribution under this export contract leaves no room to encode "
                "a payload — the attack defeats itself before we even scan.")

    loud = max(dets, key=dets.get) if dets else "none"
    if gate in ("APPROVE", "APPROVE_WITH_CAVEATS"):
        base = (f"Statistical detection missed this: {eff} B carried in mantissa planes "
                f"b{meta['bit_offset']}-b{meta['planes'][-1]} with "
                f"{agree}% output agreement. Those planes hold genuine trained value "
                f"bits, so no bit-level statistic can separate payload from weights — "
                f"we are not going to pretend otherwise.")
        if attestation and attestation.get("caught"):
            return (base + " The attested Merkle baseline caught it anyway: "
                    + attestation.get("headline", ""))
        return base + " This is a real blind spot in the statistical tier."

    if agree is not None and agree < 95:
        return (f"Blocked, and note the cost to the attacker: output agreement fell to "
                f"{agree}%, so ordinary regression testing would also notice. "
                f"Loudest detector: {loud}.")
    return (f"Blocked at {eff} B with {agree}% output agreement — behaviourally "
            f"near-identical, still caught. Loudest detector: {loud}.")
