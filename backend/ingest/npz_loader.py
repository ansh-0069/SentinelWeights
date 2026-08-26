"""NumPy .npz/.npy loader. Object arrays are rejected outright (they can pickle)."""
from __future__ import annotations

import numpy as np

from ir import ModelIR, TensorRecord


def load_npz(path: str) -> ModelIR:
    tensors: list[TensorRecord] = []
    # allow_pickle=False is the critical safety control here.
    try:
        with np.load(path, allow_pickle=False) as npz:
            for name in npz.files:
                arr = npz[name]
                if arr.dtype == object:
                    return _rejected(path, "Object array detected; refusing to load (pickle risk).")
                tensors.append(TensorRecord(name=name, dtype=str(arr.dtype),
                                            shape=tuple(arr.shape), values=arr))
    except ValueError as e:
        if "allow_pickle" in str(e).lower() or "object" in str(e).lower():
            return _rejected(path, "File requires pickle to load (object arrays); refused.")
        raise
    return ModelIR(path=path, fmt="npz", tensors=tensors, weights_loadable=True,
                   load_note="Loaded with allow_pickle=False.")


def _rejected(path: str, note: str) -> ModelIR:
    return ModelIR(path=path, fmt="npz", tensors=[], weights_loadable=False, load_note=note)
