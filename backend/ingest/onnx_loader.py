"""ONNX loader: extract initializers as tensors. Never runs the graph.

Uses the ONNX protobuf only — no ONNX Runtime, no custom-op execution.
"""
from __future__ import annotations

import numpy as np

from ir import ModelIR, TensorRecord


def _np_dtype_tag(arr: np.ndarray) -> str:
    if arr.dtype == np.float32:
        return "F32"
    if arr.dtype == np.float16:
        return "F16"
    if arr.dtype == np.float64:
        return "F64"
    if arr.dtype == np.int8:
        return "I8"
    if arr.dtype == np.int32:
        return "I32"
    if arr.dtype == np.int64:
        return "I64"
    if arr.dtype == np.uint8:
        return "U8"
    return str(arr.dtype)


def load_onnx(path: str) -> ModelIR:
    try:
        import onnx
        from onnx import numpy_helper
    except ImportError:
        return ModelIR(
            path=path, fmt="onnx", weights_loadable=False,
            load_note="onnx package not installed; cannot extract initializers.",
        )

    try:
        model = onnx.load(path)
    except Exception as e:
        return ModelIR(
            path=path, fmt="onnx", weights_loadable=False,
            load_note=f"Could not parse ONNX protobuf: {e}",
        )

    tensors: list[TensorRecord] = []
    for init in model.graph.initializer:
        try:
            arr = numpy_helper.to_array(init)
        except Exception:
            continue
        if arr.size == 0:
            continue
        tensors.append(TensorRecord(
            name=init.name or f"initializer_{len(tensors)}",
            dtype=_np_dtype_tag(arr),
            shape=tuple(arr.shape),
            values=np.ascontiguousarray(arr),
        ))

    meta = {
        "ir_version": int(getattr(model, "ir_version", 0) or 0),
        "producer": (model.producer_name or "") + " " + (model.producer_version or ""),
        "graph": model.graph.name or "graph",
        "declared_arch": "onnx-initializers",
    }
    if not tensors:
        return ModelIR(
            path=path, fmt="onnx", tensors=[], metadata=meta,
            weights_loadable=False,
            load_note="ONNX parsed but no initializers (weights not embedded in this file).",
        )
    return ModelIR(
        path=path, fmt="onnx", tensors=tensors, metadata=meta,
        weights_loadable=True,
        load_note="Extracted ONNX initializers from protobuf (graph not executed).",
    )
