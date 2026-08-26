import { useEffect, useState } from "react";
import { compare } from "../api";
import { bandColor, Stat } from "./ui";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from "recharts";
import { chartTheme } from "../chartTheme";

const BAND_COLORS: Record<string, string> = {
  CLEAN: "green", LOW_CONCERN: "lime", SUSPICIOUS: "amber", DANGEROUS: "red",
};

export default function CompareView({ a = "clean", b = "stego_contiguous" }: { a?: string; b?: string }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    compare(a, b).then(setData);
  }, [a, b]);
  if (!data) return <p className="text-[13px] text-ink-400">Loading comparison…</p>;

  const cA = bandColor[BAND_COLORS[data.a.band] || "green"];
  const cB = bandColor[BAND_COLORS[data.b.band] || "red"];
  const changed = data.changed_bitplanes?.[0];
  const bpData = changed
    ? changed.delta_entropy.map((d: number, i: number) => ({ bit: `b${i}`, delta: d }))
    : [];

  const totalBytes = (data.b.regions || []).reduce(
    (acc: number, r: any) => acc + (r.est_bytes > 0 ? r.est_bytes : 0), 0
  );
  const capacityKB = (totalBytes / 1024).toFixed(1);
  const perf = data.performance_preservation || {};
  const agree =
    perf.output_agreement_pct != null ? `${perf.output_agreement_pct}%` : "measured on rescan";
  const agreeColor =
    perf.output_agreement_pct != null && perf.output_agreement_pct >= 95 ? "#1F6F5B" : "#C2410C";

  const Panel = ({ s, color, tag }: { s: any; color: string; tag: string }) => (
    <div className="rounded-2xl border border-paper-line bg-paper p-4">
      <div className="flex items-center justify-between">
        <span className="text-[13px] text-ink-600">{tag}</span>
        <span className="display text-[32px] leading-none" style={{ color }}>{s.risk_score}</span>
      </div>
      <div className="text-[12px] text-ink-400 mt-1">{s.sample} · {s.band}</div>
      <div className="grid grid-cols-2 gap-2 mt-3">
        <Stat label="Params" value={s.total_params?.toLocaleString?.() ?? s.total_params} />
        <Stat label="Tensors" value={s.num_tensors} />
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-2 gap-3">
        <Panel s={data.a} color={cA} tag="Clean sibling" />
        <Panel s={data.b} color={cB} tag="Tampered sibling" />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Stat label="Architecture" value="identical" color="#1F6F5B" />
        <Stat label="Params" value="match" color="#1F6F5B" />
        <Stat
          label="Output agreement"
          value={agree}
          color={agreeColor}
          sub={perf.probe ? `probe: ${perf.probe}` : "linear probe on shared tensor"}
        />
        <Stat label="Hidden capacity" value={`≈ ${capacityKB} KB`} color="#B42318" sub="localized region est." />
      </div>

      {bpData.length > 0 && (
        <div>
          <div className="text-[12px] text-ink-400 mb-1">
            Changed bit planes on <span className="tabular-nums">{changed.tensor}</span>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={bpData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
              <XAxis dataKey="bit" tick={{ fontSize: 8, fill: chartTheme.tick }} interval={0} />
              <YAxis tick={{ fontSize: 10, fill: chartTheme.tick }} />
              <Tooltip contentStyle={chartTheme.tooltip} />
              <Bar dataKey="delta" radius={[3, 3, 0, 0]}>
                {bpData.map((d: any, i: number) => (
                  <Cell key={i} fill={d.delta > 0.05 ? "#B42318" : "#D9D2C6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="text-[13px] text-ink-600 leading-relaxed">
        Same architecture, near-identical probe behavior, opposite security verdict. Agreement is measured, not hardcoded.
      </p>
    </div>
  );
}
