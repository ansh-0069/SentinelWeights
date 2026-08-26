r"""Critical correctness tests for SentinelWeights detectors & policy.

Run from backend/:  ..\.venv\Scripts\python.exe -m pytest tests/ -q
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detectors import l1_static, l2_bitplane, l2_window, l2_crosslayer, l2_deadspace, l4_fusion
from detectors.l1_static import _scan_pickle_bytes
from policy import decide
import ir as ir_mod
from samples.make_samples import (
    train_clean_cnn, export_quantize, embed_payload, build_pickle_fixture,
    probe_output_agreement, VAULT,
)


@pytest.fixture(scope="module")
def clean_state():
    return train_clean_cnn(seed=42, steps=120)


@pytest.fixture(scope="module")
def quantized_clean(clean_state):
    return export_quantize(clean_state, n_keep_mantissa=12)


@pytest.fixture(scope="module")
def clean_path(tmp_path_factory, quantized_clean):
    from safetensors.numpy import save_file
    p = tmp_path_factory.mktemp("m") / "clean.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in quantized_clean.items()}, str(p))
    return str(p)


@pytest.fixture(scope="module")
def stego_path(tmp_path_factory, quantized_clean):
    from safetensors.numpy import save_file
    stego = embed_payload(quantized_clean, "conv3.weight", 0.2, 4096, scattered=False, seed=7)
    p = tmp_path_factory.mktemp("m") / "stego.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in stego.items()}, str(p))
    return str(p)


def test_pickle_fixture_is_critical_without_execution():
    data = build_pickle_fixture()
    findings, trace, globals_ = _scan_pickle_bytes("fixture", data)
    assert any(f["severity"] == "CRITICAL" for f in findings)
    # Windows pickles os.system as nt.system; POSIX as posix.system / os.system
    blob = " ".join(
        str(f.get("evidence", {})) + " " + f.get("message", "") for f in findings
    ) + " " + " ".join(globals_)
    assert any(x in blob for x in ("os.system", "nt.system", "posix.system"))


def test_l1_on_pickle_file(tmp_path):
    p = tmp_path / "evil.pt"
    p.write_bytes(build_pickle_fixture())
    the_ir = ir_mod.load(str(p))
    r = l1_static.run(the_ir)
    assert r["critical"] is True
    decision = decide(0.0, r, the_ir.weights_loadable, the_ir.fmt)
    assert decision["gate"] == "HARD_BLOCK"
    assert decision["risk_score"] == 100


def test_clean_vs_stego_separable(clean_path, stego_path):
    rc = ir_mod.load(clean_path)
    rs = ir_mod.load(stego_path)
    wc = max(l2_window.run(rc)["score"], l2_bitplane.run(rc)["score"], l2_crosslayer.run(rc)["score"])
    ws = max(l2_window.run(rs)["score"], l2_bitplane.run(rs)["score"], l2_crosslayer.run(rs)["score"])
    assert ws > wc, f"stego score {ws} should exceed clean {wc}"
    assert ws >= 0.1, "stego should raise meaningful suspicion"


def test_malformed_quarantines(tmp_path):
    p = tmp_path / "broken.bin"
    p.write_bytes(b"\x00\x01not_a_model")
    the_ir = ir_mod.load(str(p))
    r = l1_static.run(the_ir)
    decision = decide(10.0, r, the_ir.weights_loadable, the_ir.fmt)
    assert decision["gate"] == "QUARANTINE"


def test_perf_preservation_near_identical(clean_state):
    q = export_quantize(clean_state, n_keep_mantissa=12)
    stego = embed_payload(q, "conv3.weight", 0.25, 2048, seed=3)
    perf = probe_output_agreement(q, stego)
    assert perf["output_agreement_pct"] is not None
    assert perf["output_agreement_pct"] >= 95.0


def test_fusion_exposes_weights():
    results = {
        "l2_bitplane": {"z": 0}, "l2_window": {"z": 0}, "l2_randfeat": {"z": 0},
        "l2_distdiv": {"z": 0}, "l2_crosslayer": {"z": 0}, "l2_precision": {"z": 0},
        "l2_deadspace": {"z": 0},
        "l3_backdoor": {"z": 0},
    }
    out = l4_fusion.fuse(results, {"findings": []})
    assert "weights" in out and "crosslayer" in out["weights"]
    assert out["risk_score"] < 30


def test_gallery_expected_gates_if_present():
    """Regression: if snapshots exist, enforce gate contract."""
    snap = os.path.join(os.path.dirname(__file__), "..", "samples", "snapshots")
    expected = {
        "clean": "APPROVE",
        "public_clean": "APPROVE",
        "quantized_clean": "APPROVE",
        "vendor_reexport": "APPROVE",
        "stego_silent": "APPROVE",
        "borderline_backdoor": "APPROVE_WITH_CAVEATS",
        "backdoor_toycnn": "REVIEW",
        "stego_contiguous": "HARD_BLOCK",
        "stego_scattered": "HARD_BLOCK",
        "pickle_fixture": "HARD_BLOCK",
        "zip_slip": "HARD_BLOCK",
        "truncated": "QUARANTINE",
        "malformed": "QUARANTINE",
    }
    import json
    for sid, gate in expected.items():
        path = os.path.join(snap, f"{sid}.json")
        if not os.path.exists(path):
            pytest.skip("snapshots not generated yet")
        with open(path) as f:
            rep = json.load(f)
        got = rep["verdict"]["gate"]
        if isinstance(gate, tuple):
            assert got in gate, f"{sid}: {got} not in {gate}"
        else:
            assert got == gate, f"{sid}: {got} != {gate}"


def test_fusion_exposes_deadspace_weight():
    out = l4_fusion.fuse({
        "l2_bitplane": {"z": 0}, "l2_window": {"z": 0}, "l2_randfeat": {"z": 0},
        "l2_distdiv": {"z": 0}, "l2_crosslayer": {"z": 0}, "l2_precision": {"z": 0},
        "l2_deadspace": {"z": 0}, "l3_backdoor": {"z": 0},
    }, {"findings": []})
    assert "deadspace" in out["weights"]


def test_deadspace_does_not_flip_export_quantized_clean(clean_path):
    the_ir = ir_mod.load(clean_path)
    r = l2_deadspace.run(the_ir)
    assert r["z"] <= 1.5
    assert r["score"] < 0.8


def test_full_pipeline_bench_fpr_not_majority():
    path = os.path.join(os.path.dirname(__file__), "..", "bench", "results", "benchmark.json")
    if not os.path.exists(path):
        pytest.skip("benchmark not generated yet")
    import json
    with open(path) as f:
        bench = json.load(f)
    pol = bench.get("confusion_at_policy")
    n = int(bench.get("corpus", {}).get("clean") or 0)
    if not pol or n < 4:
        pytest.skip("full-pipeline bench missing")
    assert pol["fp"] / n < 0.5, f"clean FPR {pol['fp']}/{n} is a majority"


def test_cli_approve_exit_zero():
    clean = os.path.join(os.path.dirname(__file__), "..", "samples", "vault", "clean.safetensors")
    if not os.path.exists(clean):
        pytest.skip("gallery not generated")
    from cli import cmd_scan
    import orchestrator
    orchestrator._CACHE.clear()
    assert cmd_scan(clean, "REVIEW") == 0


def test_cli_pickle_exit_block():
    evil = os.path.join(os.path.dirname(__file__), "..", "samples", "vault", "pickle_fixture.pt")
    if not os.path.exists(evil):
        pytest.skip("gallery not generated")
    from cli import cmd_scan
    import orchestrator
    orchestrator._CACHE.clear()
    assert cmd_scan(evil, "REVIEW") == 3


def test_onnx_loader_if_present():
    path = os.path.join(os.path.dirname(__file__), "..", "samples", "vault", "public_clean.onnx")
    if not os.path.exists(path):
        pytest.skip("onnx fixture not generated")
    the_ir = ir_mod.load(path)
    assert the_ir.fmt == "onnx"
    assert the_ir.weights_loadable is True
    import orchestrator
    orchestrator._CACHE.clear()
    rep = orchestrator.scan(path)
    assert rep["verdict"]["gate"] in ("APPROVE", "APPROVE_WITH_CAVEATS", "REVIEW")
    # Must not hard-block a tiny public ONNX
    assert rep["verdict"]["gate"] != "HARD_BLOCK"

