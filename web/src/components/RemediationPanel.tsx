import { useState } from "react";
import { remediate } from "../api";
import { bandColor } from "./ui";

export default function RemediationPanel({ scanId }: { scanId: string }) {
  const [res, setRes] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      setRes(await remediate(scanId));
    } finally {
      setLoading(false);
    }
  }

  const Score = ({ v, label }: { v: any; label: string }) => (
    <div className="rounded-xl p-3 border border-paper-line bg-paper text-center">
      <div className="text-[11px] text-ink-400">{label}</div>
      <div className="display text-[28px] leading-none mt-1" style={{ color: bandColor[v.color] }}>
        {v.risk_score}
      </div>
      <div className="text-[11px] mt-1" style={{ color: bandColor[v.color] }}>{v.gate.replace(/_/g, " ")}</div>
    </div>
  );

  return (
    <div className="space-y-3">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        LSB sanitization for stego, or safetensors conversion for a malicious pickle (never executed).
        May alter behavior. A human keeps release approval.
      </p>
      <button
        onClick={run}
        disabled={loading}
        className="px-4 py-2 rounded-full bg-ink text-paper-card text-[13px] disabled:opacity-50"
      >
        {loading ? "Working…" : "Remediate and rescan"}
      </button>
      {res && !res.supported && (
        <p className="text-[13px] text-ink-400">{res.message}</p>
      )}
      {res && res.supported && (
        <div>
          <div className="grid grid-cols-2 gap-3">
            <Score v={res.before} label="Before" />
            <Score v={res.after} label={res.kind === "format_conversion" ? "After (safetensors)" : "After (sanitized)"} />
          </div>
          <p className="text-[12px] text-ink-400 mt-2">{res.note}</p>
        </div>
      )}
    </div>
  );
}
