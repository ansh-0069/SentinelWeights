"""SentinelWeights prototype API (FastAPI, fully offline)."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field

import ablation
import adversary
import attest
import frontier
import holdout
import lineage
import orchestrator
import sampled
from detectors import l4_fusion
from ir import sha256_file, detect_format
from report import pdf as pdf_mod
from signing import sign_verify

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(HERE, "samples", "vault")
SNAP = os.path.join(HERE, "samples", "snapshots")
BENCH = os.path.join(HERE, "bench", "results")

app = FastAPI(title="SentinelWeights", version="2.0",
              description="Zero Trust for AI Models — prototype scanner")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCANS: dict[str, dict] = {}  # scan_id -> {path, filename, report, replay}


@app.on_event("startup")
def _startup():
    from detectors import baselines as bl
    bl.reload_empirical()
    l4_fusion.init_anomaly_head()


def _gallery():
    gpath = os.path.join(VAULT, "gallery.json")
    if os.path.exists(gpath):
        with open(gpath) as f:
            raw = json.load(f)
        if isinstance(raw, dict) and "samples" in raw:
            return raw["samples"], raw.get("methodology")
        return raw, None
    # fallback flat list
    glist = os.path.join(VAULT, "gallery_list.json")
    if os.path.exists(glist):
        with open(glist) as f:
            return json.load(f), None
    return [], None


@app.get("/samples")
def list_samples():
    gallery, methodology = _gallery()
    out = []
    for g in gallery:
        snap = os.path.join(SNAP, f"{g['id']}.json")
        verdict = None
        if os.path.exists(snap):
            with open(snap) as f:
                verdict = json.load(f).get("verdict")
        path = os.path.join(VAULT, g["file"])
        out.append({**g,
                    "exists": os.path.exists(path),
                    "size": os.path.getsize(path) if os.path.exists(path) else 0,
                    "format": detect_format(path) if os.path.exists(path) else "?",
                    "expected_verdict": verdict})
    return {"samples": out, "methodology": methodology}


@app.post("/scan")
async def create_scan(file: UploadFile | None = File(default=None), sample: str | None = None):
    scan_id = uuid.uuid4().hex[:12]
    if sample:
        gallery_list, _ = _gallery()
        gallery = {g["id"]: g for g in gallery_list}
        if sample not in gallery:
            raise HTTPException(404, f"Unknown sample '{sample}'")
        path = os.path.join(VAULT, gallery[sample]["file"])
        filename = gallery[sample]["file"]
        is_sample = True
    elif file is not None:
        suffix = os.path.splitext(file.filename or "upload.bin")[1] or ".bin"
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as f:
            f.write(await file.read())
        filename = file.filename or os.path.basename(path)
        is_sample = False
    else:
        raise HTTPException(400, "Provide a file or ?sample=<id>")

    SCANS[scan_id] = {"path": path, "filename": filename, "is_sample": is_sample,
                      "sample_id": sample, "report": None}
    return {"scan_id": scan_id, "filename": filename,
            "sha256": sha256_file(path), "size": os.path.getsize(path),
            "format": detect_format(path)}


@app.websocket("/ws/{scan_id}")
async def ws_scan(websocket: WebSocket, scan_id: str):
    await websocket.accept()
    entry = SCANS.get(scan_id)
    if not entry:
        await websocket.send_json({"stage": "error", "message": "unknown scan_id"})
        await websocket.close()
        return

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def progress(ev):
        loop.call_soon_threadsafe(queue.put_nowait, ev)

    def run():
        try:
            rep = orchestrator.scan(entry["path"], progress=progress)
        except Exception as e:  # fail-safe: try snapshot replay
            rep = _replay_snapshot(entry) or {"error": str(e)}
        loop.call_soon_threadsafe(queue.put_nowait, {"stage": "__done__", "report": rep})

    fut = loop.run_in_executor(None, run)
    try:
        while True:
            ev = await queue.get()
            if ev.get("stage") == "__done__":
                report = ev["report"]
                entry["report"] = report
                await websocket.send_json({"stage": "complete", "scan_id": scan_id,
                                           "report": report})
                break
            await websocket.send_json(ev)
    except WebSocketDisconnect:
        pass
    finally:
        await fut
        try:
            await websocket.close()
        except Exception:
            pass


def _replay_snapshot(entry):
    if entry.get("sample_id"):
        p = os.path.join(SNAP, f"{entry['sample_id']}.json")
        if os.path.exists(p):
            with open(p) as f:
                rep = json.load(f)
            rep["replay"] = True
            return rep
    return None


@app.get("/result/{scan_id}")
def get_result(scan_id: str):
    entry = SCANS.get(scan_id)
    if not entry:
        raise HTTPException(404, "unknown scan_id")
    if entry["report"] is None:
        entry["report"] = orchestrator.scan(entry["path"])
    return entry["report"]


def _report_for_sample(sample_id: str) -> dict:
    gallery_list, _ = _gallery()
    p = os.path.join(VAULT, {g["id"]: g["file"] for g in gallery_list}.get(sample_id, ""))
    if p and os.path.exists(p):
        return orchestrator.scan(p)
    snap = os.path.join(SNAP, f"{sample_id}.json")
    if os.path.exists(snap):
        with open(snap) as f:
            return json.load(f)
    raise HTTPException(404, f"no report for {sample_id}")


@app.get("/compare")
def compare(a: str = "clean", b: str = "stego_contiguous"):
    ra, rb = _report_for_sample(a), _report_for_sample(b)

    def summary(r, sid):
        bom = r["mlbom"]
        return {
            "sample": sid,
            "risk_score": r["verdict"]["risk_score"],
            "band": r["verdict"]["band"],
            "gate": r["verdict"]["gate"],
            "total_params": bom["total_params"],
            "num_tensors": bom["num_tensors"],
            "regions": r.get("regions", []),
            "bitplane": r["detectors"]["l2_bitplane"].get("profiles", [])[:1],
        }
    changed = _changed_bitplanes(ra, rb)
    perf = _load_perf_preservation(a, b)
    return {
        "a": summary(ra, a),
        "b": summary(rb, b),
        "changed_bitplanes": changed,
        "performance_preservation": perf,
    }


def _load_perf_preservation(a: str, b: str) -> dict:
    """Prefer precomputed measured probe; else compute live for known vault siblings."""
    pref = os.path.join(SNAP, "perf_preservation.json")
    if a == "clean" and b == "stego_contiguous" and os.path.exists(pref):
        with open(pref) as f:
            data = json.load(f)
        return data.get("clean_vs_stego_contiguous", data)
    # live compute if both are loadable safetensors in vault
    gallery_list, _ = _gallery()
    files = {g["id"]: g["file"] for g in gallery_list}
    if a not in files or b not in files:
        return {"output_agreement_pct": None, "note": "perf probe unavailable for this pair"}
    try:
        from samples.make_samples import probe_output_agreement
        import ir as ir_mod
        ira = ir_mod.load(os.path.join(VAULT, files[a]))
        irb = ir_mod.load(os.path.join(VAULT, files[b]))
        if not ira.weights_loadable or not irb.weights_loadable:
            return {"output_agreement_pct": None, "note": "weights not loadable"}
        ca = {t.name: t.values for t in ira.tensors if t.values is not None}
        cb = {t.name: t.values for t in irb.tensors if t.values is not None}
        return probe_output_agreement(ca, cb)
    except Exception as e:
        return {"output_agreement_pct": None, "note": str(e)}


def _changed_bitplanes(ra, rb):
    pa = {p["tensor"]: p for p in ra["detectors"]["l2_bitplane"].get("profiles", [])}
    pb = {p["tensor"]: p for p in rb["detectors"]["l2_bitplane"].get("profiles", [])}
    out = []
    for name in set(pa) & set(pb):
        oa, ob = pa[name]["observed"], pb[name]["observed"]
        diffs = [round(b_ - a_, 4) for a_, b_ in zip(oa, ob)]
        if max((abs(d) for d in diffs), default=0) > 0.02:
            out.append({"tensor": name, "delta_entropy": diffs})
    return out[:8]


@app.get("/benchmark")
def benchmark():
    p = os.path.join(BENCH, "benchmark.json")
    if not os.path.exists(p):
        raise HTTPException(404, "benchmark not generated; run make_samples")
    with open(p) as f:
        return json.load(f)


@app.post("/remediate/{scan_id}")
def remediate(scan_id: str):
    """Experimental: LSB sanitize (stego) or safetensors conversion teaching (pickle)."""
    entry = SCANS.get(scan_id)
    if not entry:
        raise HTTPException(404, "unknown scan_id")
    before = entry.get("report") or orchestrator.scan(entry["path"])
    entry["report"] = before
    fmt = (before.get("mlbom") or {}).get("format") or ""
    gate = before["verdict"].get("gate")

    # Pickle / unsafe-deser: never execute. Teaching moment = convert to safetensors.
    if gate == "HARD_BLOCK" and before["verdict"].get("override") == "L1_CRITICAL":
        companion = os.path.join(VAULT, "clean.safetensors")
        if not os.path.exists(companion):
            return {"supported": False,
                    "kind": "format_conversion",
                    "message": "No safetensors companion available for the conversion demo.",
                    "before": before["verdict"]}
        after = orchestrator.scan(companion)
        return {
            "supported": True,
            "kind": "format_conversion",
            "before": before["verdict"],
            "after": after["verdict"],
            "note": "We never deserialized the pickle. After = gallery clean.safetensors "
                    "(pure-data format). L1 execution surface is gone. This is a format-"
                    "conversion teaching moment, not a claim we recovered this pickle's weights. "
                    "Human keeps release approval.",
        }

    sanitized = _sanitize_low_bits(entry["path"])
    if sanitized is None:
        return {"supported": False,
                "kind": "lsb_sanitize",
                "message": "LSB sanitization applies to loadable float weight files only.",
                "before": before["verdict"]}
    after = orchestrator.scan(sanitized)
    return {
        "supported": True,
        "kind": "lsb_sanitize",
        "before": before["verdict"],
        "after": after["verdict"],
        "note": "Experimental — clearing low mantissa bits may alter behavior and requires "
                "revalidation; human keeps release approval.",
    }


def _sanitize_low_bits(path: str, n_low=8):
    import numpy as np
    from safetensors.numpy import save_file
    import ir as ir_mod
    the_ir = ir_mod.load(path)
    if not the_ir.weights_loadable or the_ir.fmt not in ("safetensors",):
        return None
    state = {}
    mask = np.uint32(~((1 << n_low) - 1) & 0xFFFFFFFF)
    for t in the_ir.tensors:
        v = t.values
        if v is not None and v.dtype == np.float32:
            bits = v.view(np.uint32).copy() & mask
            state[t.name] = np.ascontiguousarray(bits.view(np.float32))
        elif v is not None:
            state[t.name] = np.ascontiguousarray(v)
    out = os.path.join(tempfile.gettempdir(), "sanitized_" + os.path.basename(path))
    if not out.endswith(".safetensors"):
        out += ".safetensors"
    save_file(state, out)
    return out


@app.get("/report/{scan_id}.pdf")
def report_pdf(scan_id: str):
    entry = SCANS.get(scan_id)
    if not entry:
        raise HTTPException(404, "unknown scan_id")
    report = entry.get("report") or orchestrator.scan(entry["path"])
    entry["report"] = report
    signature = report.get("signature") or sign_verify.sign_report(report)
    data = pdf_mod.render_pdf(report, signature)
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=sentinel_{scan_id}.pdf"})


@app.post("/verify")
def verify(payload: dict):
    """Verify a report signature. Accepts either {report_sha256,signature_b64,public_key_pem}
    or {scan_id}."""
    if "scan_id" in payload:
        entry = SCANS.get(payload["scan_id"])
        if not entry or not entry.get("report"):
            raise HTTPException(404, "no report for scan_id")
        sig = entry["report"].get("signature")
        if not sig:
            raise HTTPException(400, "report not signed")
        # recompute the canonical hash of the report (minus its signature) to
        # confirm the content hasn't changed, then cryptographically verify.
        rep_no_sig = {k: v for k, v in entry["report"].items()
                      if k not in ("signature", "from_cache")}
        recomputed = sign_verify.canonical_hash(rep_no_sig)
        integrity_ok = (recomputed == sig["report_sha256"])
        res = sign_verify.verify(sig["report_sha256"], sig["signature_b64"], sig["public_key_pem"])
        res["integrity_match"] = integrity_ok
        res["valid"] = bool(res["valid"] and integrity_ok)
        res["key_id"] = sig["key_id"]
        res["report_sha256"] = sig["report_sha256"]
        if not integrity_ok:
            res["message"] = "Content hash mismatch — report was modified after signing."
        return res
    return sign_verify.verify(payload["report_sha256"], payload["signature_b64"], payload["public_key_pem"])


@app.get("/health")
def health():
    return {"status": "ok", "anomaly_head": l4_fusion._ANOMALY_READY}


# ===================== Adversary Lab =====================

_BASE_STATE: dict | None = None


def _clean_base_state() -> dict:
    """The clean gallery model as an in-memory state dict — the forge substrate."""
    global _BASE_STATE
    if _BASE_STATE is None:
        import ir as ir_mod
        path = os.path.join(VAULT, "clean.safetensors")
        if not os.path.exists(path):
            raise HTTPException(404, "clean.safetensors missing; run make_samples")
        the_ir = ir_mod.load(path)
        _BASE_STATE = {t.name: t.values for t in the_ir.tensors if t.values is not None}
    return _BASE_STATE


class ForgeRequest(BaseModel):
    n_bytes: int = Field(4096, ge=0, le=1 << 20, description="Payload size in bytes")
    n_planes: int = Field(6, ge=1, le=8, description="Mantissa planes used")
    bit_offset: int = Field(0, ge=0, le=22, description="First mantissa plane written")
    layout: str = Field("contiguous", pattern="^(contiguous|scattered|per_channel)$")
    entropy_matched: bool = Field(False, description="Match the clean plane distribution")
    spread_tensors: int = Field(1, ge=1, le=6)
    tensor: str | None = None
    payload_kind: str = Field("random", pattern="^(random|compressed)$")
    seed: int = Field(42, ge=0, le=1 << 31)


@app.post("/forge")
def forge(req: ForgeRequest):
    """Author an attack, embed it into the clean model, scan it with the real pipeline.

    Defensive only: payloads are inert random or compressed filler bytes.
    """
    base = _clean_base_state()
    return adversary.forge_and_scan(base, artifact_hook=attest.diff_against_label,
                                    **req.model_dump())


@app.get("/frontier")
def get_frontier():
    data = frontier.load()
    if not data:
        raise HTTPException(404, "frontier not generated; run make_samples")
    return data


# ===================== Merkle attestation =====================

class AttestRequest(BaseModel):
    sample: str | None = None
    scan_id: str | None = None
    declared_version: str = "v1.0"
    label: str | None = None


def _resolve_artifact(sample: str | None, scan_id: str | None) -> tuple[str, str]:
    if sample:
        gallery_list, _ = _gallery()
        files = {g["id"]: g["file"] for g in gallery_list}
        if sample not in files:
            raise HTTPException(404, f"unknown sample '{sample}'")
        return os.path.join(VAULT, files[sample]), sample
    if scan_id:
        entry = SCANS.get(scan_id)
        if not entry:
            raise HTTPException(404, "unknown scan_id")
        return entry["path"], entry["filename"]
    raise HTTPException(400, "provide 'sample' or 'scan_id'")


@app.post("/attest")
def create_attestation(req: AttestRequest):
    """Attest an artifact: Merkle root over per-tensor hashes, signed, ledgered."""
    path, label = _resolve_artifact(req.sample, req.scan_id)
    if not os.path.exists(path):
        raise HTTPException(404, "artifact not found")
    verdict = None
    if req.scan_id and SCANS.get(req.scan_id, {}).get("report"):
        verdict = SCANS[req.scan_id]["report"]["verdict"]
    elif req.sample:
        snap = os.path.join(SNAP, f"{req.sample}.json")
        if os.path.exists(snap):
            with open(snap) as f:
                verdict = json.load(f).get("verdict")
    record = attest.build_attestation(path, verdict=verdict,
                                      declared_version=req.declared_version,
                                      label=req.label or label)
    attest.append_ledger(record)
    return {**{k: v for k, v in record.items() if k != "leaves"},
            "leaf_preview": [{"name": lf["name"], "leaf": lf["leaf"][:16],
                              "n_params": lf["n_params"]}
                             for lf in record["leaves"][:12]],
            "n_leaves": record["n_leaves"]}


@app.get("/attestations")
def list_attestations():
    return {"attestations": attest.ledger_summary(), "ledger": attest.LEDGER}


class DiffRequest(BaseModel):
    attestation_id: str
    sample: str | None = None
    scan_id: str | None = None


@app.post("/attest/diff")
def attest_diff(req: DiffRequest):
    """Compare a candidate artifact against an attested baseline."""
    record = attest.find_attestation(req.attestation_id)
    if not record:
        raise HTTPException(404, f"unknown attestation '{req.attestation_id}'")
    path, _ = _resolve_artifact(req.sample, req.scan_id)
    if not os.path.exists(path):
        raise HTTPException(404, "candidate artifact not found")
    return attest.diff(record, path)


@app.get("/attest/proof/{attestation_id}")
def attest_proof(attestation_id: str, tensor: str):
    """Merkle inclusion proof — prove one tensor without shipping the model."""
    record = attest.find_attestation(attestation_id)
    if not record:
        raise HTTPException(404, f"unknown attestation '{attestation_id}'")
    leaves = record["leaves"]
    idx = next((i for i, lf in enumerate(leaves) if lf["name"] == tensor), None)
    if idx is None:
        raise HTTPException(404, f"tensor '{tensor}' not in attestation")
    path = attest.merkle_proof(leaves, idx)
    return {
        "tensor": tensor,
        "leaf": leaves[idx]["leaf"],
        "proof": path,
        "proof_len": len(path),
        "merkle_root": record["merkle_root"],
        "verified": attest.verify_proof(leaves[idx]["leaf"], path, record["merkle_root"]),
        "note": (f"{len(path)} sibling hashes prove this tensor belongs to the signed "
                 f"root — the other {record['n_leaves'] - 1} tensors stay undisclosed."),
    }


# ===================== Lineage / ablation / holdout =====================

@app.get("/lineage")
def get_lineage():
    data = lineage.load()
    if not data:
        data = lineage.build()
    return data


@app.get("/ablation")
def get_ablation():
    data = ablation.load()
    if not data:
        raise HTTPException(404, "ablation not generated; run make_samples")
    return data


@app.get("/holdout")
def get_holdout():
    data = holdout.load()
    if not data:
        raise HTTPException(404, "holdout not generated; run make_samples")
    return data


# ===================== Sampled scan (scale) =====================

class SampledRequest(BaseModel):
    sample: str | None = None
    fraction: float = Field(0.05, gt=0.0, le=1.0)
    replicates: int = Field(6, ge=2, le=20)
    target_mb: int = Field(96, ge=8, le=1024,
                           description="Size of the generated large fixture")
    embed_payload: bool = True
    seed: int = 0


@app.post("/sampled_scan")
def sampled_scan(req: SampledRequest):
    """Triage a large artifact by reading only sampled channels.

    With no `sample`, generates a large local fixture, scans it, and removes it —
    so the scale claim is measured on this machine rather than asserted.
    """
    generated = None
    if req.sample:
        path, _ = _resolve_artifact(req.sample, None)
        if not os.path.exists(path):
            raise HTTPException(404, "artifact not found")
        cleanup = False
    else:
        fd, path = tempfile.mkstemp(prefix="sw_large_", suffix=".safetensors")
        os.close(fd)
        generated = sampled.make_large_fixture(path, target_mb=req.target_mb,
                                               embed_payload=req.embed_payload,
                                               seed=req.seed)
        cleanup = True
    try:
        result = sampled.scan(path, fraction=req.fraction,
                              replicates=req.replicates, seed=req.seed)
    finally:
        if cleanup:
            try:
                os.remove(path)
            except OSError:
                pass
    if generated:
        result["generated_fixture"] = generated
    return result
