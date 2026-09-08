"""Deterministic policy overrides -> gate decision (proto.demo2 §5.5)."""
from __future__ import annotations

BANDS = [
    (0, 20, "CLEAN", "Auto-approve, sign, register", "green"),
    (20, 50, "LOW_CONCERN", "Approve with logged caveats", "lime"),
    (50, 80, "SUSPICIOUS", "Block; require human security review", "amber"),
    (80, 100, "DANGEROUS", "Hard block; quarantine; alert SOC", "red"),
]


def band_for(score: float) -> dict:
    # Scores are decimal values. Treat the documented integer boundaries as
    # half-open bands so values such as 20.1 and 50.1 cannot fall through to the
    # fail-safe DANGEROUS default.
    for index, (lo, hi, name, action, color) in enumerate(BANDS):
        lower_ok = score >= lo if index == 0 else score > lo
        if lower_ok and score <= hi:
            display_lo = lo if index == 0 else lo + 1
            return {"band": name, "action": action, "color": color,
                    "range": [display_lo, hi]}
    return {"band": "DANGEROUS", "action": "Hard block", "color": "red", "range": [81, 100]}


def decide(risk_score: float, l1_result: dict, ir_loadable: bool, ir_fmt: str) -> dict:
    """Apply overrides in priority order. Returns gate decision + reason."""
    reasons = []

    # 1) Unsafe-deserialization CRITICAL => hard block, override everything.
    if l1_result.get("critical"):
        return {
            "gate": "HARD_BLOCK",
            "risk_score": 100,
            "band": "DANGEROUS",
            "override": "L1_CRITICAL",
            "reason": "Confirmed unsafe-deserialization target (artifact-execution risk).",
            "language": "⛔ HARD BLOCK — unsafe deserialization target detected "
                        "(artifact-execution risk).",
            "color": "red",
        }

    # 2) Unsupported / unloadable => quarantine (fail-safe), never a green pass.
    if not ir_loadable:
        return {
            "gate": "QUARANTINE",
            "risk_score": max(risk_score, 55),
            "band": "SUSPICIOUS",
            "override": "UNLOADABLE",
            "reason": "Weights could not be extracted without unsafe execution; "
                      "safety not established.",
            "language": "🟠 QUARANTINE — unable to establish safety within scan scope.",
            "color": "amber",
        }

    # 3) Otherwise score-band driven.
    b = band_for(risk_score)
    gate = {
        "CLEAN": "APPROVE",
        "LOW_CONCERN": "APPROVE_WITH_CAVEATS",
        "SUSPICIOUS": "REVIEW",
        "DANGEROUS": "HARD_BLOCK",
    }[b["band"]]
    lang = {
        "APPROVE": "✅ APPROVE — no indicators detected within scan scope.",
        "APPROVE_WITH_CAVEATS": "🟡 APPROVE WITH CAVEATS — minor deviations logged.",
        "REVIEW": "🟠 REVIEW REQUIRED — statistical anomaly; human security review.",
        "HARD_BLOCK": "🔴 HARD BLOCK — strong tamper indicators (hidden-data risk).",
    }[gate]
    return {
        "gate": gate,
        "risk_score": round(risk_score, 1),
        "band": b["band"],
        "override": None,
        "reason": b["action"],
        "language": lang,
        "color": b["color"],
    }
