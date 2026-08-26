"""Layer 2.2 — Multi-scale windowed randomness + localization (REAL).

Under an export-quantized contract, clean low-mantissa bits are structured
(near-constant). A stego payload forces a contiguous (or scattered) block of
near-maximal entropy — the classic 'randomness cliff'.

MAD-guard: if the tensor is already spatially uniform at high entropy, z-scores
are suppressed (avoids false flags on raw float32 LSBs).
"""
from __future__ import annotations

import numpy as np

from ir import ModelIR
from detectors import contract
from detectors.common import is_float_dtype, as_float32_bits

WINDOW_SIZES = (1024, 4096, 16384)
N_LOW_BITS = 6          # band width, and the fallback band for raw float32
MAX_BANDS = 4
PLATEAU_FRACTION = 0.8  # high entropy over this much of a tensor is its precision,
                        # not a payload: a cliff is a contrast, never a plateau


def _plane_bands(floor: int) -> list[tuple[int, int]]:
    """Overlapping bands covering the freed region.

    Bands must stay narrow. Concatenating every freed plane into one stream would
    dilute a 6-plane payload inside an 11-plane window and push its entropy back
    under threshold, so we sweep with 50% overlap instead and keep the worst band.
    """
    if floor < 2:
        return [(0, N_LOW_BITS)]
    bands, start = [], 0
    step = max(1, N_LOW_BITS // 2)
    while start < floor and len(bands) < MAX_BANDS:
        end = min(start + N_LOW_BITS, floor)
        if end - start >= 2:
            bands.append((start, end))
        if end >= floor:
            break
        start += step
    return bands or [(0, N_LOW_BITS)]


def _band_stream(values: np.ndarray, dtype_str: str, lo: int, hi: int) -> np.ndarray:
    bits, _ = as_float32_bits(values, dtype_str)
    cols = [((bits >> np.uint32(k)) & np.uint32(1)).astype(np.uint8) for k in range(lo, hi)]
    return np.stack(cols, axis=1).ravel() if cols else np.array([], dtype=np.uint8)


def _window_entropy(stream: np.ndarray, win: int) -> np.ndarray:
    n = (stream.size // win) * win
    if n < win:
        return np.array([])
    blocks = stream[:n].reshape(-1, win)
    p = np.clip(blocks.mean(axis=1), 1e-9, 1 - 1e-9)
    return -p * np.log2(p) - (1 - p) * np.log2(1 - p)


def run(ir: ModelIR) -> dict:
    if not ir.weights_loadable or not ir.tensors:
        return {"detector": "l2_window", "coverage": "Skipped (missing input)",
                "score": 0.0, "z": 0.0, "regions": [], "heatmap": [], "summary": "Weights not loaded."}

    regions = []
    heatmap_rows = []
    worst_z = 0.0
    float_tensors = [t for t in ir.tensors
                     if is_float_dtype(t.dtype) and t.values is not None and t.values.size >= 2048]

    bands_by_tensor: dict[str, list[tuple[int, int]]] = {}
    floors: dict[str, int] = {}

    # The freed region is a property of the export contract, inferred as a median
    # across tensors so a payload cannot move the very boundary used to find it.
    floor_by_dtype: dict[str, int] = {}
    for dt in {t.dtype for t in float_tensors}:
        info = (contract.infer_floor(ir, dt) if contract.supported_dtype(dt)
                else {"floor": 0})
        floor_by_dtype[dt] = int(info.get("floor", 0) or 0)

    for t in float_tensors:
        floor = floor_by_dtype.get(t.dtype, 0)
        bands = _plane_bands(floor)
        floors[t.name] = floor
        bands_by_tensor[t.name] = bands
        best_region = None

        for (lo, hi) in bands:
            stream = _band_stream(t.values, t.dtype, lo, hi)
            if stream.size == 0:
                continue
            for win in WINDOW_SIZES:
                H = _window_entropy(stream, win)
                if H.size < 4:
                    continue
                med = float(np.median(H))
                mad = float(np.median(np.abs(H - med)))
                if mad < 1e-4:
                    # Near-constant field (export-quantized clean): flag absolute
                    # high-entropy windows — the classic contiguous LSB cliff.
                    flagged = H > 0.90
                    if flagged.mean() > PLATEAU_FRACTION:
                        # Uniformly high across the tensor: this band holds the
                        # artifact's real precision, not an embedded block.
                        flagged = np.zeros_like(flagged)
                    z = np.where(flagged, 8.0 + (H - 0.90) * 10.0, 0.0)
                else:
                    z = (H - med) / (1.4826 * mad)
                    flagged = (H > max(0.85, med + 0.15)) & (z > 3.0)
                idx = np.where(flagged)[0]
                if idx.size:
                    splits = np.split(idx, np.where(np.diff(idx) != 1)[0] + 1)
                    n_planes = hi - lo
                    for grp in splits:
                        if grp.size >= 2:
                            run_z = float(z[grp].max())
                            start = int(grp[0] * win / n_planes)
                            end = int((grp[-1] + 1) * win / n_planes)
                            cand = {"tensor": t.name, "start": start, "end": end,
                                    "est_bytes": int(grp.size * win / 8), "scale": win,
                                    "planes": [lo, hi - 1],
                                    "zmax": round(run_z, 2),
                                    "entropy": round(float(H[grp].mean()), 3),
                                    "note": f"entropy cliff in mantissa planes b{lo}-b{hi - 1}"}
                            if best_region is None or run_z > best_region["zmax"]:
                                best_region = cand
                if win == WINDOW_SIZES[0] and (lo, hi) == bands[0]:
                    cells = H
                    if cells.size > 64:
                        cells = cells[: (cells.size // 64) * 64].reshape(64, -1).mean(axis=1)
                    heatmap_rows.append({"tensor": t.name,
                                         "cells": [round(float(x), 3) for x in cells]})
        if best_region:
            regions.append(best_region)
            worst_z = max(worst_z, best_region["zmax"])

    # scattered: whole-tensor mean band entropy outlier vs siblings, per band
    if len(float_tensors) >= 3:
        all_bands = sorted({b for t in float_tensors for b in bands_by_tensor.get(t.name, [])})
        for (lo, hi) in all_bands[:MAX_BANDS]:
            means = []
            for t in float_tensors:
                stream = _band_stream(t.values, t.dtype, lo, hi)
                if stream.size == 0:
                    continue
                H = _window_entropy(stream, 4096)
                if H.size:
                    means.append((t.name, float(H.mean())))
            if len(means) < 3:
                continue
            vals = np.array([m[1] for m in means])
            med = float(np.median(vals))
            mad = float(np.median(np.abs(vals - med))) + 1e-9
            if mad < 1e-4:
                continue
            for nm, v in means:
                rz = (v - med) / (1.4826 * mad)
                if rz > 4.0 and v > 0.9:
                    worst_z = max(worst_z, float(rz))
                    if not any(r["tensor"] == nm for r in regions):
                        regions.append({"tensor": nm, "start": 0, "end": -1,
                                        "est_bytes": -1, "scale": "whole-tensor",
                                        "planes": [lo, hi - 1],
                                        "zmax": round(float(rz), 2),
                                        "note": f"scattered high entropy in planes "
                                                f"b{lo}-b{hi - 1}"})

    score = float(min(1.0, worst_z / 8.0)) if worst_z else 0.0
    z = float(min(8.0, worst_z))
    summary = (f"{len(regions)} suspicious region(s); max z={worst_z:.1f}"
               if regions else "No randomness cliffs detected")
    scanned = sorted({tuple(b) for bs in bands_by_tensor.values() for b in bs})
    return {
        "detector": "l2_window",
        "coverage": "Executed" if float_tensors else "Not applicable",
        "score": score,
        "z": z,
        "regions": regions[:32],
        "heatmap": heatmap_rows[:48],
        "quantization_floor": floors,
        "scanned_bands": [f"b{lo}-b{hi - 1}" for lo, hi in scanned],
        "band_note": ("Bands are derived from each tensor's measured quantization "
                      "floor, not fixed. Planes above the floor hold genuine trained "
                      "value bits and are deliberately excluded from absolute-entropy "
                      "tests — see the attestation panel for that region."),
        "summary": summary,
    }
