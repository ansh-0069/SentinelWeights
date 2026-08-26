"""safetensors loader: pure-data format, no code execution.

We parse the header JSON + memory-mapped tensor bytes directly, which means we
never run any deserialization VM. This is the format we recommend attackers'
targets be converted to.
"""
from __future__ import annotations

import json
import struct

import numpy as np

from ir import ModelIR, TensorRecord

# safetensors dtype -> numpy dtype
_ST_DTYPES = {
    "F64": np.float64, "F32": np.float32, "F16": np.float16,
    "BF16": None,  # handled specially (numpy has no bf16)
    "I64": np.int64, "I32": np.int32, "I16": np.int16, "I8": np.int8,
    "U8": np.uint8, "BOOL": np.bool_,
}


def load_safetensors(path: str) -> ModelIR:
    with open(path, "rb") as f:
        header_len = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(header_len).decode("utf-8"))
        data = f.read()

    metadata = header.pop("__metadata__", {}) if isinstance(header, dict) else {}
    tensors: list[TensorRecord] = []

    for name, info in header.items():
        dtype_str = info["dtype"]
        shape = tuple(info["shape"])
        begin, end = info["data_offsets"]
        buf = data[begin:end]
        values = _decode(dtype_str, buf, shape)
        tensors.append(TensorRecord(name=name, dtype=dtype_str, shape=shape, values=values))

    ir = ModelIR(path=path, fmt="safetensors", tensors=tensors,
                 metadata=dict(metadata), weights_loadable=True,
                 load_note="Parsed as pure-data safetensors (no code execution).")
    return ir


def _decode(dtype_str: str, buf: bytes, shape: tuple[int, ...]) -> np.ndarray:
    if dtype_str == "BF16":
        # bf16 = top 16 bits of fp32; widen to fp32 for analysis
        u16 = np.frombuffer(buf, dtype=np.uint16)
        u32 = u16.astype(np.uint32) << 16
        return u32.view(np.float32).reshape(shape)
    np_dtype = _ST_DTYPES.get(dtype_str)
    if np_dtype is None:
        np_dtype = np.uint8
    return np.frombuffer(buf, dtype=np_dtype).reshape(shape)
