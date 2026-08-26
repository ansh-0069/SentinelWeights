"""Canonical Intermediate Representation (IR) for scanned model artifacts.

Every format loader maps a model file into a `ModelIR` so that all downstream
detectors are format-agnostic. This is the clean separation of concerns
described in sol_steg.md §5.2.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class TensorRecord:
    name: str
    dtype: str
    shape: tuple[int, ...]
    values: Optional[np.ndarray]  # None when weights could not be safely loaded
    n_params: int = 0

    def __post_init__(self) -> None:
        if self.values is not None and self.n_params == 0:
            self.n_params = int(self.values.size)


@dataclass
class ModelIR:
    path: str
    fmt: str  # "safetensors" | "pt" | "npz" | "onnx" | "unknown"
    tensors: list[TensorRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    # loadable = weights were extracted without unsafe execution
    weights_loadable: bool = False
    load_note: str = ""
    raw_bytes: Optional[bytes] = None

    @property
    def total_params(self) -> int:
        return sum(t.n_params for t in self.tensors)

    @property
    def num_tensors(self) -> int:
        return len(self.tensors)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".safetensors":
        return "safetensors"
    if ext == ".onnx":
        return "onnx"
    if ext in (".pt", ".pth", ".bin", ".pkl"):
        return "pt"
    if ext in (".npz", ".npy"):
        return "npz"
    return "unknown"


def load(path: str) -> ModelIR:
    """Dispatch to a format-specific loader. Never executes untrusted code."""
    fmt = detect_format(path)
    file_hash = sha256_file(path)
    prov = {"sha256": file_hash, "size_bytes": os.path.getsize(path), "filename": os.path.basename(path)}

    if fmt == "safetensors":
        from ingest.safetensors_loader import load_safetensors
        try:
            ir = load_safetensors(path)
        except Exception as exc:
            ir = ModelIR(
                path=path, fmt="safetensors", weights_loadable=False,
                load_note=f"Safetensors parse failed: {exc}",
            )
            try:
                with open(path, "rb") as f:
                    ir.raw_bytes = f.read(1 << 20)
            except Exception:
                pass
    elif fmt == "pt":
        from ingest.pytorch_loader import load_pt_static_first
        ir = load_pt_static_first(path)
    elif fmt == "npz":
        from ingest.npz_loader import load_npz
        ir = load_npz(path)
    elif fmt == "onnx":
        from ingest.onnx_loader import load_onnx
        ir = load_onnx(path)
    else:
        ir = ModelIR(path=path, fmt="unknown", weights_loadable=False,
                     load_note="Unrecognized format; cannot establish safety.")
        try:
            with open(path, "rb") as f:
                ir.raw_bytes = f.read(1 << 20)
        except Exception:
            pass

    ir.provenance.update(prov)
    return ir
