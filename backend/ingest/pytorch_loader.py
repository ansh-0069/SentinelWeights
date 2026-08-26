"""PyTorch .pt loader with STATIC-FIRST handling (proto.demo2 §5.1).

Policy:
  * We NEVER call torch.load / pickle.load on untrusted input.
  * We locate the pickle byte-stream(s) inside the artifact (a .pt is usually a
    zip containing `data.pkl`; legacy .pt is a bare pickle) and hand them to the
    Layer-1 static scanner.
  * Statistical scanning of weights proceeds ONLY when a trusted converted
    `<name>.safetensors` companion exists. Otherwise weights are not loaded and
    the file is quarantined as Unsupported/Skipped.
"""
from __future__ import annotations

import io
import os
import zipfile

from ir import ModelIR


def _extract_pickle_streams(path: str) -> list[tuple[str, bytes]]:
    """Return list of (entry_name, pickle_bytes) without executing anything."""
    streams: list[tuple[str, bytes]] = []
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] == b"PK":  # zip-based .pt
        try:
            with zipfile.ZipFile(path) as zf:
                for entry in zf.namelist():
                    if entry.endswith(".pkl") or entry.endswith("data.pkl"):
                        streams.append((entry, zf.read(entry)))
        except zipfile.BadZipFile:
            pass
    else:  # legacy bare pickle
        with open(path, "rb") as f:
            streams.append((os.path.basename(path), f.read()))
    return streams


def _list_archive_entries(path: str) -> list[dict]:
    entries: list[dict] = []
    with open(path, "rb") as f:
        head = f.read(2)
    if head == b"PK":
        try:
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    entries.append({
                        "name": info.filename,
                        "size": info.file_size,
                        "compressed": info.compress_size,
                    })
        except zipfile.BadZipFile:
            pass
    return entries


def load_pt_static_first(path: str) -> ModelIR:
    streams = _extract_pickle_streams(path)
    archive_entries = _list_archive_entries(path)

    tensors = []
    weights_loadable = False
    note = "Static-first: pickle streams staged for Layer-1 inspection; weights not loaded."

    # Trusted converted companion?
    companion = os.path.splitext(path)[0] + ".safetensors"
    if os.path.exists(companion):
        from ingest.safetensors_loader import load_safetensors
        st = load_safetensors(companion)
        tensors = st.tensors
        weights_loadable = True
        note = "Weights loaded from trusted safetensors companion (never via torch.load)."

    ir = ModelIR(
        path=path, fmt="pt", tensors=tensors, weights_loadable=weights_loadable,
        load_note=note,
        metadata={"_pickle_streams": streams, "archive_entries": archive_entries,
                  "companion_safetensors": os.path.basename(companion) if os.path.exists(companion) else None},
    )
    with open(path, "rb") as f:
        ir.raw_bytes = f.read()
    return ir
