"""Runs the tiered scan funnel (Tier 0 -> Tier 4), records REAL elapsed_ms per
stage, emits progress, short-circuits on Layer-1 CRITICAL, tracks coverage.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

import ir as ir_mod
import coverage as coverage_mod
import policy as policy_mod
from detectors import (l1_static, l2_bitplane, l2_window, l2_randfeat,
                       l2_distdiv, l2_precision, l2_crosslayer, l2_deadspace,
                       l2_contract, l3_backdoor, l4_fusion)
from report import builder as report_builder
from signing import sign_verify

_CACHE: dict[str, dict] = {}  # sha256 -> report (Tier 0 content-addressed cache)

ProgressCB = Optional[Callable[[dict], None]]


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def scan(path: str, progress: ProgressCB = None, replay: bool = False,
         min_stage_ms: int = 250) -> dict:
    timings: dict[str, int] = {}
    t_start = time.perf_counter()

    def emit(stage, status, elapsed_ms, extra=None):
        if progress:
            payload = {"stage": stage, "status": status, "elapsed_ms": elapsed_ms}
            if extra:
                payload.update(extra)
            progress(payload)

    # ---------- Tier 0: ingest + hash cache ----------
    t0 = time.perf_counter()
    emit("tier0", "running", 0)
    the_ir = ir_mod.load(path)
    timings["uploaded"] = 0
    timings["hashed"] = _ms(t0)
    sha = the_ir.provenance.get("sha256")
    cached = sha in _CACHE
    e0 = _ms(t0)
    emit("tier0", "cache_hit" if cached else "done", e0,
         {"sha256": sha, "cached": cached})
    if cached and not replay:
        rep = dict(_CACHE[sha])
        rep["from_cache"] = True
        return rep

    results: dict[str, dict] = {}

    # ---------- Tier 1: static forensics ----------
    t1 = time.perf_counter()
    emit("tier1", "running", 0)
    results["l1_static"] = l1_static.run(the_ir)
    timings["l1_static"] = _ms(t1)
    e1 = _ms(t1)
    if results["l1_static"].get("critical"):
        emit("tier1", "critical", e1, {"summary": results["l1_static"]["summary"]})
        # short-circuit: later tiers Not applicable
        for det in ("l2_bitplane", "l2_window", "l2_randfeat", "l2_distdiv",
                    "l2_precision", "l2_crosslayer", "l2_deadspace", "l2_contract",
                    "l3_backdoor"):
            results[det] = {"detector": det, "coverage": "Not applicable",
                            "score": 0.0, "z": 0.0,
                            "summary": "Skipped — pipeline short-circuited at Tier 1 CRITICAL."}
        emit("tier2", "na", 0); emit("tier3", "na", 0)
        return _finalize(the_ir, results, timings, t_start, progress, emit, replay, short=True)
    emit("tier1", "done", e1, {"summary": results["l1_static"]["summary"]})

    # ---------- Tier 2: statistical steganalysis ----------
    t2 = time.perf_counter()
    emit("tier2", "running", 0)
    results["l2_bitplane"] = l2_bitplane.run(the_ir)
    results["l2_window"] = l2_window.run(the_ir)
    results["l2_randfeat"] = l2_randfeat.run(the_ir)
    results["l2_distdiv"] = l2_distdiv.run(the_ir)
    results["l2_precision"] = l2_precision.run(the_ir)
    results["l2_crosslayer"] = l2_crosslayer.run(the_ir)
    results["l2_deadspace"] = l2_deadspace.run(the_ir)
    results["l2_contract"] = l2_contract.run(the_ir)
    timings["tensor_scan"] = _ms(t2)
    e2 = _ms(t2)
    emit("tier2", "done", e2)

    # ---------- Tier 3: behavioral (toy) ----------
    t3 = time.perf_counter()
    emit("tier3", "running", 0)
    results["l3_backdoor"] = l3_backdoor.run(the_ir)
    timings["l3_backdoor"] = _ms(t3)
    e3 = _ms(t3)
    emit("tier3", "done", e3, {"summary": results["l3_backdoor"]["summary"]})

    return _finalize(the_ir, results, timings, t_start, progress, emit, replay)


def _finalize(the_ir, results, timings, t_start, progress, emit, replay, short=False):
    # ---------- Tier 4: fusion + policy ----------
    t4 = time.perf_counter()
    emit("tier4", "running", 0)
    fusion = l4_fusion.fuse(results, results["l1_static"])
    decision = policy_mod.decide(fusion["risk_score"], results["l1_static"],
                                 the_ir.weights_loadable, the_ir.fmt)
    timings["policy"] = _ms(t4)

    cov = coverage_mod.summarize(results)
    timings["attested"] = int((time.perf_counter() - t_start) * 1000)
    report = report_builder.build_report(the_ir, results, fusion, decision, cov,
                                          timings, replay)
    report["total_ms"] = timings["attested"]
    # sign the fully-built report (excluding the signature field itself)
    signature = sign_verify.sign_report(report)
    report["signature"] = signature

    emit("tier4", "done", _ms(t4),
         {"risk_score": decision["risk_score"], "gate": decision["gate"]})

    sha = the_ir.provenance.get("sha256")
    if sha:
        _CACHE[sha] = report
    return report


def get_cached(sha: str) -> dict | None:
    return _CACHE.get(sha)
