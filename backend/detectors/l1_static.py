"""Layer 1 — Unsafe-deserialization & artifact forensics (REAL, static only).

We statically disassemble pickle byte-streams with `pickletools.genops` and
model enough of the pickle VM to resolve STACK_GLOBAL / GLOBAL references and
REDUCE call targets. We NEVER execute the pickle.
"""
from __future__ import annotations

import io
import pickletools
import zipfile

from ir import ModelIR

# Tensor-reconstruction globals PyTorch/NumPy legitimately use.
ALLOWLIST = {
    "torch._utils._rebuild_tensor_v2",
    "torch._utils._rebuild_tensor",
    "torch._utils._rebuild_parameter",
    "torch.storage._load_from_bytes",
    "torch.FloatStorage", "torch.LongStorage", "torch.IntStorage",
    "torch.HalfStorage", "torch.DoubleStorage", "torch.ByteStorage",
    "collections.OrderedDict",
    "numpy.core.multiarray._reconstruct",
    "numpy.ndarray", "numpy.dtype",
    "_codecs.encode",
}

# Callables whose presence indicates code-execution intent.
DANGER_PREFIXES = (
    "os.", "posix.", "nt.", "subprocess.", "sys.",
    "builtins.eval", "builtins.exec", "builtins.__import__",
    "builtins.getattr", "builtins.compile", "builtins.open",
    "importlib.", "pty.", "socket.", "shutil.", "webbrowser.",
    "runpy.", "commands.", "pickle.loads",
)
DANGER_EXACT = {
    "os.system", "posix.system", "nt.system", "subprocess.Popen",
    "subprocess.call", "subprocess.run", "subprocess.check_output",
    "builtins.eval", "builtins.exec", "builtins.__import__",
    "pty.spawn", "shutil.rmtree",
}


def _is_danger(target: str) -> bool:
    if target in DANGER_EXACT:
        return True
    return any(target.startswith(p) for p in DANGER_PREFIXES)


def _scan_pickle_bytes(name: str, data: bytes) -> list[dict]:
    """Disassemble a single pickle stream; return findings."""
    findings: list[dict] = []
    globals_seen: list[str] = []
    opcode_trace: list[dict] = []
    stack_globals: list[str] = []

    try:
        for opcode, arg, pos in pickletools.genops(data):
            entry = {"op": opcode.name, "arg": _safe_arg(arg), "pos": pos}
            opcode_trace.append(entry)

            if opcode.name in ("GLOBAL", "INST"):
                # arg like "os system" or "os.system"
                target = str(arg).replace(" ", ".") if arg else ""
                globals_seen.append(target)
                stack_globals.append(target)
            elif opcode.name == "STACK_GLOBAL":
                # module + name were the two prior string pushes
                target = _resolve_stack_global(opcode_trace)
                if target:
                    globals_seen.append(target)
                    stack_globals.append(target)
            elif opcode.name in ("REDUCE", "OBJ", "NEWOBJ", "INST"):
                # a call is being made against the most recent global
                if stack_globals:
                    callee = stack_globals[-1]
                    if _is_danger(callee):
                        findings.append({
                            "severity": "CRITICAL",
                            "code": "PICKLE_DANGEROUS_REDUCE",
                            "message": f"pickle {opcode.name} targets dangerous callable '{callee}'",
                            "evidence": {"entry": name, "callee": callee, "pos": pos},
                        })
    except Exception as e:  # malformed pickle — treat as unable-to-establish-safety
        findings.append({
            "severity": "MEDIUM",
            "code": "PICKLE_PARSE_ERROR",
            "message": f"Could not fully disassemble pickle '{name}': {e}",
            "evidence": {"entry": name},
        })

    # classify each global
    for g in dict.fromkeys(globals_seen):
        if _is_danger(g):
            continue  # already reported at REDUCE
        if g not in ALLOWLIST and g:
            findings.append({
                "severity": "REVIEW",
                "code": "PICKLE_UNKNOWN_GLOBAL",
                "message": f"Non-allowlisted global referenced: '{g}' (needs review, not auto-malicious)",
                "evidence": {"entry": name, "global": g},
            })

    return findings, opcode_trace, globals_seen


def _resolve_stack_global(trace: list[dict]) -> str:
    # STACK_GLOBAL consumes two SHORT_BINUNICODE/BINUNICODE strings: module, name
    strs = [t["arg"] for t in trace[-6:] if t["op"].endswith("UNICODE") or t["op"] in ("STRING", "SHORT_BINUNICODE", "BINUNICODE")]
    if len(strs) >= 2:
        return f"{strs[-2]}.{strs[-1]}"
    return ""


def _safe_arg(arg) -> str:
    try:
        s = str(arg)
        return s[:120]
    except Exception:
        return "<unrepr>"


def _scan_archive(ir: ModelIR) -> list[dict]:
    findings: list[dict] = []
    entries = ir.metadata.get("archive_entries") or []
    for e in entries:
        nm = e.get("name", "")
        if ".." in nm or nm.startswith("/") or nm.startswith("\\"):
            findings.append({"severity": "CRITICAL", "code": "PATH_TRAVERSAL",
                             "message": f"Archive entry with path traversal: {nm}",
                             "evidence": e})
        if nm.lower().endswith((".exe", ".dll", ".sh", ".bat", ".so", ".dylib")):
            findings.append({"severity": "HIGH", "code": "EXECUTABLE_IN_ARCHIVE",
                             "message": f"Executable file inside model archive: {nm}",
                             "evidence": e})
        comp = e.get("compressed", 1) or 1
        if e.get("size", 0) > 0 and e["size"] / comp > 200:
            findings.append({"severity": "HIGH", "code": "DECOMPRESSION_BOMB",
                             "message": f"Suspicious compression ratio {e['size']/comp:.0f}x in {nm}",
                             "evidence": e})
    return findings


def _scan_metadata(ir: ModelIR) -> list[dict]:
    findings: list[dict] = []
    for t in ir.tensors:
        if len(t.name) > 512:
            findings.append({"severity": "REVIEW", "code": "OVERSIZED_TENSOR_NAME",
                             "message": f"Tensor name unusually long ({len(t.name)} chars)",
                             "evidence": {"name": t.name[:80] + "..."}})
    for k, v in (ir.metadata or {}).items():
        if isinstance(v, str) and len(v) > 4096:
            findings.append({"severity": "REVIEW", "code": "LARGE_METADATA_BLOB",
                             "message": f"Metadata field '{k}' carries a large blob ({len(v)} chars)",
                             "evidence": {"field": k}})
    return findings


def run(ir: ModelIR) -> dict:
    findings: list[dict] = []
    opcode_trace: list[dict] = []
    globals_all: list[str] = []

    streams = ir.metadata.get("_pickle_streams") or []
    for name, data in streams:
        f, trace, gseen = _scan_pickle_bytes(name, data)
        findings.extend(f)
        if not opcode_trace:  # keep first stream's trace for the viewer
            opcode_trace = trace
        globals_all.extend(gseen)

    findings.extend(_scan_archive(ir))
    findings.extend(_scan_metadata(ir))

    severities = [f["severity"] for f in findings]
    critical = "CRITICAL" in severities
    review = "REVIEW" in severities or "MEDIUM" in severities or "HIGH" in severities

    # L1 always executes SOME applicable check (archive + metadata + format).
    # The pickle sub-scan is simply N/A for pure-data formats.
    coverage = "Executed"
    if critical:
        summary = "CRITICAL unsafe-deserialization / artifact finding"
    elif not streams and ir.fmt in ("safetensors", "npz"):
        summary = "Archive/metadata scanned; no serialized-code surface (pure-data format)"
    else:
        summary = "No dangerous callables detected in static scan"

    return {
        "detector": "l1_static",
        "coverage": coverage,
        "critical": critical,
        "findings": findings,
        "opcode_trace": opcode_trace[:400],
        "globals": list(dict.fromkeys(globals_all)),
        "summary": summary,
    }
