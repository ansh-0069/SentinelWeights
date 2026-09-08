r"""Tests for the Adversary Lab, attestation, lineage, contract detector, and
sampled scan.

Run from backend/:  ..\.venv\Scripts\python.exe -m pytest tests/ -q
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ablation
import adversary
import attest
import coverage as coverage_mod
import ir as ir_mod
import lineage
import sampled
from detectors import contract, l2_contract, l4_fusion
from report.narrative import build_narratives
from samples.make_samples import export_quantize, train_clean_cnn

VAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "samples", "vault")
BENCH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "bench", "results")


@pytest.fixture(scope="module")
def clean_state():
    return export_quantize(train_clean_cnn(seed=321, steps=120), n_keep_mantissa=12)


@pytest.fixture(scope="module")
def clean_file(tmp_path_factory, clean_state):
    from safetensors.numpy import save_file
    p = tmp_path_factory.mktemp("adv") / "clean.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in clean_state.items()}, str(p))
    return str(p)


# --------------------------- precision contract ---------------------------

def test_contract_floor_matches_export(clean_state, clean_file):
    """A 12-bit export frees planes b0-b10, so the inferred floor must be 11."""
    the_ir = ir_mod.load(clean_file)
    info = contract.infer_floor(the_ir, "F32")
    assert info["available"]
    assert info["floor"] == 11, info["median_plane_probs"][:13]
    assert info["anomalous_planes"] == []


def test_contract_floor_tracks_a_different_export(tmp_path, clean_state):
    """Export at 14 kept bits and the floor must move, not false-alarm."""
    from safetensors.numpy import save_file
    raw = train_clean_cnn(seed=321, steps=120)
    st = export_quantize(raw, n_keep_mantissa=14)
    p = tmp_path / "keep14.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in st.items()}, str(p))
    the_ir = ir_mod.load(str(p))
    assert contract.infer_floor(the_ir, "F32")["floor"] == 9
    assert l2_contract.run(the_ir)["z"] == 0.0


def test_clean_export_has_no_contract_violation(clean_file):
    r = l2_contract.run(ir_mod.load(clean_file))
    assert r["z"] == 0.0
    assert r["violations"] == []


def test_full_precision_model_has_no_contract(tmp_path):
    """Raw float32 has no freed region, so the detector must abstain."""
    from safetensors.numpy import save_file
    st = train_clean_cnn(seed=99, steps=80)
    p = tmp_path / "raw.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in st.items()}, str(p))
    r = l2_contract.run(ir_mod.load(str(p)))
    assert r["coverage"] == "Not applicable"
    assert r["z"] == 0.0


def test_fp16_cast_is_not_a_violation(tmp_path, clean_state):
    """fp16 value bits sit near P=0.38; that must not read as freed space."""
    from safetensors.numpy import save_file
    st = {k: (v.astype(np.float16) if v.dtype == np.float32 else v)
          for k, v in clean_state.items()}
    p = tmp_path / "fp16.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in st.items()}, str(p))
    r = l2_contract.run(ir_mod.load(str(p)))
    assert r["z"] == 0.0, r.get("summary")


# --------------------------- adversary lab ---------------------------

def test_forge_in_freed_planes_is_blocked(clean_state):
    """Any occupancy of freed planes must block, wherever inside them it sits."""
    for offset in (0, 4, 8):
        res = adversary.forge_and_scan(clean_state, n_bytes=4096, n_planes=3,
                                       bit_offset=offset, tensor="conv3.weight")
        assert res["supported"]
        assert res["attack"]["effective_bytes"] > 0
        assert res["verdict"]["gate"] == "HARD_BLOCK", (
            f"offset {offset} evaded: {res['verdict']}")


def test_forge_survives_all_layouts(clean_state):
    for layout in ("contiguous", "scattered", "per_channel"):
        res = adversary.forge_and_scan(clean_state, n_bytes=4096, n_planes=6,
                                       layout=layout, tensor="conv3.weight")
        assert res["verdict"]["gate"] in ("HARD_BLOCK", "REVIEW"), layout


def test_entropy_matched_low_planes_have_no_capacity(clean_state):
    """Matching a freed plane distribution of ~zero means encoding ~zero bits."""
    res = adversary.forge_and_scan(clean_state, n_bytes=4096, n_planes=4,
                                   bit_offset=0, entropy_matched=True,
                                   tensor="conv3.weight")
    assert res["attack"]["effective_bytes"] == 0
    assert "defeats itself" in res["interpretation"]


def test_kept_plane_evasion_is_reported_honestly(clean_state):
    """We must not claim to catch what bit statistics cannot see."""
    res = adversary.forge_and_scan(clean_state, n_bytes=4096, n_planes=4,
                                   bit_offset=14, tensor="conv3.weight")
    assert res["attack"]["effective_bytes"] > 0
    assert res["evaded"] is True
    assert res["detector_z"]["l2_contract"] == 0.0
    assert "missed" in res["interpretation"].lower()


def test_payload_preserves_behaviour(clean_state):
    res = adversary.forge_and_scan(clean_state, n_bytes=2048, n_planes=6,
                                   tensor="conv3.weight")
    assert res["fidelity"]["output_agreement_pct"] >= 95.0


def test_forge_never_writes_outside_requested_planes(clean_state):
    tampered, meta = adversary.forge(clean_state, n_bytes=1024, n_planes=4,
                                     bit_offset=6, tensor="conv3.weight")
    a = clean_state["conv3.weight"].ravel().view(np.uint32)
    b = tampered["conv3.weight"].ravel().view(np.uint32)
    diff_bits = np.bitwise_or.reduce(a ^ b)
    allowed = np.uint32(sum(1 << k for k in meta["planes"]))
    assert diff_bits & ~allowed == 0, f"wrote outside planes {meta['planes']}"


def test_payload_kind_changes_the_bytes_actually_embedded(clean_state):
    """The payload selector must affect model bits, not only response metadata."""
    random_state, random_meta = adversary.forge(
        clean_state, n_bytes=512, n_planes=4, tensor="conv3.weight",
        payload_kind="random", seed=17,
    )
    compressed_state, compressed_meta = adversary.forge(
        clean_state, n_bytes=512, n_planes=4, tensor="conv3.weight",
        payload_kind="compressed", seed=17,
    )
    assert random_meta["effective_bytes"] == compressed_meta["effective_bytes"] == 512
    assert not np.array_equal(random_state["conv3.weight"], compressed_state["conv3.weight"])


def test_capacity_preview_matches_single_tensor_forge(clean_state):
    estimate = adversary.preview(
        clean_state, n_bytes=4096, n_planes=6, tensor="conv3.weight",
    )
    _, actual = adversary.forge(
        clean_state, n_bytes=4096, n_planes=6, tensor="conv3.weight",
    )
    assert estimate["effective_bytes"] == actual["effective_bytes"]
    assert estimate["planes"] == actual["planes"]


def test_contract_detector_is_visible_in_coverage_and_narrative():
    summary = coverage_mod.summarize({"l2_contract": {"coverage": "Executed"}})
    contract_badge = next(b for b in summary["badges"] if b["detector"] == "l2_contract")
    assert contract_badge["state"] == "Executed"
    narratives = build_narratives({
        "l2_contract": {"violations": [{
            "tensor": "conv3.weight", "occupancy_pct": 4.1,
            "freed_planes": "b0-b10", "est_bytes": 4096,
        }]},
    }, {"gate": "HARD_BLOCK"})
    contract_story = next(n for n in narratives if "contract" in n["title"].lower())
    assert contract_story["evidence_codes"] == ["l2_contract"]


# --------------------------- merkle attestation ---------------------------

def test_merkle_root_is_deterministic_and_order_independent(clean_file):
    the_ir = ir_mod.load(clean_file)
    leaves = attest.tensor_leaves(the_ir)
    root_a = attest.merkle_root(leaves)
    shuffled = list(reversed(leaves))
    # tensor_leaves sorts by name, so a re-sort of a shuffled list must agree
    root_b = attest.merkle_root(sorted(shuffled, key=lambda lf: lf["name"]))
    assert root_a == root_b
    assert len(root_a) == 64


def test_merkle_proof_verifies_and_rejects(clean_file):
    the_ir = ir_mod.load(clean_file)
    leaves = attest.tensor_leaves(the_ir)
    root = attest.merkle_root(leaves)
    for i in range(len(leaves)):
        path = attest.merkle_proof(leaves, i)
        assert attest.verify_proof(leaves[i]["leaf"], path, root)
    bad = "0" * 64
    assert not attest.verify_proof(bad, attest.merkle_proof(leaves, 0), root)


def test_silent_substitution_is_classified(tmp_path, clean_state, clean_file):
    """Same tensor count, same params, same declared version, different weights."""
    from safetensors.numpy import save_file
    record = attest.build_attestation(clean_file, declared_version="v1.2",
                                      label="test-clean")
    tampered, _ = adversary.forge(clean_state, n_bytes=4096, n_planes=6,
                                  tensor="conv3.weight")
    cand = tmp_path / "clean.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in tampered.items()}, str(cand))

    d = attest.diff(record, str(cand))
    assert d["root_match"] is False
    assert d["declared_metadata_match"] is True
    assert d["classification"] == "SILENT_SUBSTITUTION"
    assert d["changed_count"] == 1
    assert d["changed"][0]["name"] == "conv3.weight"
    assert d["signature_valid"] is True


def test_diff_localizes_changed_mantissa_planes(tmp_path, clean_state, clean_file):
    from safetensors.numpy import save_file
    record = attest.build_attestation(clean_file, label="test-clean")
    tampered, meta = adversary.forge(clean_state, n_bytes=4096, n_planes=4,
                                     bit_offset=0, tensor="conv3.weight")
    cand = tmp_path / "cand.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in tampered.items()}, str(cand))
    d = attest.diff(record, str(cand))
    assert d["bit_forensics"], d["forensics_note"]
    bf = d["bit_forensics"][0]
    assert set(bf["by_region"]) == {"mantissa b0-b5"}
    assert "exponent" not in bf["by_region"]
    assert "sign" not in bf["by_region"]


def test_identical_artifact_matches_root(clean_file):
    record = attest.build_attestation(clean_file, label="test-clean")
    d = attest.diff(record, clean_file)
    assert d["root_match"] is True
    assert d["classification"] == "IDENTICAL"
    assert d["changed_count"] == 0


def test_attestation_catches_kept_plane_evasion(tmp_path, clean_state, clean_file):
    """The case statistics cannot see must still be caught by the baseline."""
    from safetensors.numpy import save_file
    record = attest.build_attestation(clean_file, label="test-clean")
    tampered, _ = adversary.forge(clean_state, n_bytes=4096, n_planes=4,
                                  bit_offset=14, tensor="conv3.weight")
    cand = tmp_path / "cand.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in tampered.items()}, str(cand))
    d = attest.diff(record, str(cand))
    assert d["root_match"] is False
    assert d["classification"] == "SILENT_SUBSTITUTION"


# --------------------------- lineage ---------------------------

def test_lineage_finds_derived_stego_sibling():
    if not os.path.exists(os.path.join(VAULT, "stego_contiguous.safetensors")):
        pytest.skip("gallery not generated")
    data = lineage.build()
    edge = next((e for e in data["edges"]
                 if {e["a"], e["b"]} == {"clean", "stego_contiguous"}), None)
    assert edge is not None
    assert edge["relation"] == "derived"
    assert edge["differing_tensors"] == ["conv3.weight"]
    assert edge["n_identical"] >= 6


def test_lineage_separates_unrelated_public_fixture():
    if not os.path.exists(os.path.join(VAULT, "public_clean.safetensors")):
        pytest.skip("gallery not generated")
    data = lineage.build()
    pair = next((e for e in data["edges"]
                 if {e["a"], e["b"]} == {"clean", "public_clean"}), None)
    assert pair is None, "public fixture must share no tensors with our CNN"


# --------------------------- ablation ---------------------------

def test_ablation_reports_both_columns():
    path = os.path.join(BENCH, "ablation.json")
    if not os.path.exists(path):
        pytest.skip("ablation not generated")
    with open(path) as f:
        data = json.load(f)
    loo = data["leave_one_out"]
    assert loo["available"]
    assert loo["corpus"]["attacks"] > 0 and loo["corpus"]["clean"] > 0
    for row in loo["rows"]:
        assert "delta_auc" in row and "auc_solo" in row
    stego = next(r for r in loo["rows"] if r["detector_group"] == "stego_group")
    assert stego["load_bearing"] is True
    assert stego["auc_solo"] > 0.7


def test_ablation_keeps_the_sign_of_removal_cost():
    """A group the stack ranks better without must never read as contributing nothing."""
    loo = ablation.leave_one_out(ablation._frontier_records() + [
        {"label": 0, "features": {k: 0.0 for k in l4_fusion.FEATURE_ORDER},
         "static_review": 0.0},
    ])
    if not loo.get("available"):
        pytest.skip("no stored feature vectors")
    for row in loo["rows"]:
        cost = round(loo["full_auc"] - row["auc_without"], 4)
        assert row["delta_auc"] == cost
        assert row["removal_improves_auc"] == (cost < -0.01
                                               and row["delta_tp"] >= 0)
        # These three verdicts must stay mutually exclusive, or the panel would
        # label the same row two different ways.
        assert sum([row["load_bearing"], row["removal_improves_auc"]]) <= 1


def test_alternative_controls_are_executed_not_assumed():
    data = ablation.alternative_controls()
    cov = data["coverage"]
    assert cov["sentinelweights"]["caught"] == cov["sentinelweights"]["of"]
    # An accuracy regression must NOT catch a fidelity-preserving stego payload.
    stego = next((r for r in data["rows"] if r["sample"] == "stego_contiguous"), None)
    if stego:
        assert stego["controls"]["accuracy_regression"]["catches"] is False
        assert stego["controls"]["byte_signature_scan"]["catches"] is False
    # We must credit the controls that genuinely work on the pickle.
    pick = next((r for r in data["rows"] if r["sample"] == "pickle_fixture"), None)
    if pick:
        assert pick["controls"]["byte_signature_scan"]["catches"] is True
        assert pick["controls"]["format_policy_reject_pickle"]["catches"] is True


# --------------------------- sampled scan ---------------------------

def test_sampled_scan_reads_only_a_fraction(tmp_path, clean_state):
    from safetensors.numpy import save_file
    p = tmp_path / "big.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in clean_state.items()}, str(p))
    res = sampled.scan(str(p), fraction=0.25, replicates=3, seed=0)
    assert res["supported"]
    assert 0 < res["sampling"]["achieved_fraction"] < 1.0
    assert res["estimate"]["gate"] == "APPROVE"
    assert len(res["estimate"]["per_replicate"]) == 3
    assert res["estimate"]["ci95"][0] <= res["estimate"]["risk_score_mean"]


def test_sampled_scan_finds_a_large_payload(tmp_path, clean_state):
    from safetensors.numpy import save_file
    tampered, _ = adversary.forge(clean_state, n_bytes=16384, n_planes=6,
                                  layout="scattered", tensor="fc1.weight")
    p = tmp_path / "big_stego.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in tampered.items()}, str(p))
    res = sampled.scan(str(p), fraction=0.3, replicates=3, seed=0)
    assert res["estimate"]["gate"] in ("HARD_BLOCK", "REVIEW")


def test_sampled_header_read_does_not_load_weights(tmp_path, clean_state):
    from safetensors.numpy import save_file
    p = tmp_path / "hdr.safetensors"
    save_file({k: np.ascontiguousarray(v) for k, v in clean_state.items()}, str(p))
    ir_hdr = sampled._names_only_ir(str(p))
    assert ir_hdr.num_tensors == len(clean_state)
    assert all(t.values is None for t in ir_hdr.tensors)
    assert ir_hdr.total_params == sum(v.size for v in clean_state.values())


# --------------------------- fusion plumbing ---------------------------

def test_contract_joins_the_stego_group_without_double_counting():
    """Grouped max: contract must lift a quiet verdict but not stack on a loud one."""
    base = {k: 0.0 for k in l4_fusion.FEATURE_ORDER}
    quiet = l4_fusion.score_from_features({**base, "contract_z": 8.0})
    loud_window = l4_fusion.score_from_features({**base, "window_z": 8.0})
    both = l4_fusion.score_from_features({**base, "window_z": 8.0, "contract_z": 8.0})
    assert quiet > 51.0
    assert both == pytest.approx(loud_window)


def test_score_from_features_matches_live_fusion():
    """The ablation harness must not drift from the shipped scorer."""
    results = {"l2_bitplane": {"z": 1.0}, "l2_window": {"z": 2.0},
               "l2_randfeat": {"z": 0.5}, "l2_distdiv": {"z": 0.25},
               "l2_crosslayer": {"z": 1.5}, "l2_precision": {"z": 0.75},
               "l2_deadspace": {"z": 0.1}, "l2_contract": {"z": 3.0},
               "l3_backdoor": {"z": 0.0}}
    live = l4_fusion.fuse(results, {"findings": []})
    feats = l4_fusion.build_feature_vector(results)
    assert l4_fusion.score_from_features(feats, 0.0) == pytest.approx(
        live["risk_score"], abs=0.05)


# --------------------------- holdout ---------------------------

def test_holdout_is_sealed_and_generalizes():
    path = os.path.join(BENCH, "holdout.json")
    if not os.path.exists(path):
        pytest.skip("holdout not generated")
    with open(path) as f:
        data = json.load(f)
    assert data["sealed"] is True
    assert data["used_for_calibration"] is False
    m = data["metrics"]
    assert m["fpr"] is not None and m["fpr"] <= 0.1, data["false_alarms"]
    assert m["tpr"] is not None and m["tpr"] >= 0.8, data["misses"]


def test_frontier_blind_spots_are_covered_by_attestation():
    path = os.path.join(BENCH, "frontier.json")
    if not os.path.exists(path):
        pytest.skip("frontier not generated")
    with open(path) as f:
        data = json.load(f)
    s = data["summary"]
    assert s["uncaught_by_any_control"] == 0, data["blind_spots"]
    for b in data["blind_spots"]:
        assert b["attestation_caught"] is True
