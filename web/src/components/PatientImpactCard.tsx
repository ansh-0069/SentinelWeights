import type { Report } from "../types";
import { bandColor } from "./ui";

export default function PatientImpactCard({ report }: { report: Report }) {
  const v = report.verdict;
  const c = bandColor[v.color];
  const riskLevel =
    v.band === "CLEAN" ? "Low" : v.band === "LOW_CONCERN" ? "Guarded" : v.band === "SUSPICIOUS" ? "Elevated" : "Critical";
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-xl p-3 border border-paper-line bg-paper">
          <div className="text-[11px] text-ink-400">Supply-chain risk</div>
          <div className="text-[16px]" style={{ color: c }}>{riskLevel}</div>
        </div>
        <div className="rounded-xl p-3 border border-paper-line bg-paper">
          <div className="text-[11px] text-ink-400">Release gate</div>
          <div className="text-[16px]" style={{ color: c }}>{v.gate.replace(/_/g, " ")}</div>
        </div>
      </div>
      <div className="rounded-xl p-3 border border-paper-line bg-paper">
        <div className="text-[11px] text-ink-400">Recommended action</div>
        <div className="text-[14px] text-ink mt-0.5">{v.reason}</div>
      </div>
      <p className="text-[12px] text-ink-400 leading-relaxed">
        Supply-chain framing only. A cybersecurity clearance does not imply clinical validation.
      </p>
    </div>
  );
}
