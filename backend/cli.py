"""CLI gate for SentinelWeights — Edison/Jenkins story without fake K8s.

From backend/:
  python -m cli scan path/to/model.safetensors --fail-on REVIEW
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import orchestrator  # noqa: E402


APPROVE_GATES = {"APPROVE", "APPROVE_WITH_CAVEATS"}
REVIEW_GATES = {"REVIEW"}
BLOCK_GATES = {"HARD_BLOCK", "QUARANTINE"}


def _exit_for(gate: str, fail_on: str) -> int:
    fail_on = fail_on.upper()
    if gate in BLOCK_GATES:
        return 3
    if gate in REVIEW_GATES:
        return 2 if fail_on == "REVIEW" else 0
    return 0


def cmd_scan(path: str, fail_on: str) -> int:
    if not os.path.isfile(path):
        print(json.dumps({"error": f"not a file: {path}"}), file=sys.stderr)
        return 1
    orchestrator._CACHE.clear()
    report = orchestrator.scan(path)
    v = report["verdict"]
    out = {
        "path": os.path.abspath(path),
        "gate": v["gate"],
        "risk_score": v["risk_score"],
        "band": v["band"],
        "language": v["language"],
        "sha256": report.get("mlbom", {}).get("sha256"),
        "format": report.get("mlbom", {}).get("format"),
        "coverage_pct": report.get("coverage", {}).get("confidence_pct"),
    }
    print(json.dumps(out, indent=2))
    return _exit_for(v["gate"], fail_on)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="sentinelweights",
                                description="Pre-deployment Model Risk Score gate")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("scan", help="Scan a model artifact and print JSON")
    sp.add_argument("path")
    sp.add_argument("--fail-on", default="REVIEW",
                    choices=["REVIEW", "HARD_BLOCK"],
                    help="CI fail threshold (default REVIEW)")
    args = p.parse_args(argv)
    if args.cmd == "scan":
        return cmd_scan(args.path, args.fail_on)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
