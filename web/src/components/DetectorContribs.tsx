import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";
import { chartTheme } from "../chartTheme";

const LABELS: Record<string, string> = {
  static_review: "Static review findings",
  stego_group: "Stego group (grouped)",
  crosslayer: "Cross-layer coupling",
  precision: "Precision Δk",
  deadspace: "Dead-parameter covert channel",
  backdoor: "Backdoor (behavioral)",
};

export default function DetectorContribs({ fusion }: { fusion: any }) {
  if (!fusion) return null;
  const contribs = fusion.contributions || {};
  const data = Object.entries(contribs).map(([k, v]) => ({
    name: LABELS[k] || k,
    value: Number(v),
  }));
  const weights = fusion.weights || {};

  return (
    <div className="space-y-3">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        Transparent logistic fusion: <span className="font-mono text-[12px]">risk = 100·σ(b + Σ wᵢ·zᵢ)</span>, bias{" "}
        <span className="font-mono text-[12px]">b={fusion.bias}</span>. Correlated stego signals are grouped
        so the same anomaly isn’t triple-counted.
      </p>
      <ResponsiveContainer width="100%" height={150}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 8, fill: chartTheme.tick }} interval={0} />
          <YAxis tick={{ fontSize: 10, fill: chartTheme.tick }} />
          <Tooltip contentStyle={chartTheme.tooltip} />
          <Bar dataKey="value" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.value > 2 ? chartTheme.danger : d.value > 0.5 ? "#C2410C" : chartTheme.accent} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {Object.entries(weights).map(([k, v]) => (
          <div key={k} className="rounded-xl px-3 py-2 border border-paper-line bg-paper">
            <div className="text-[11px] text-ink-400">{LABELS[k] || k}</div>
            <div className="tabular-nums text-[13px] text-ink mt-0.5">w = {String(v)}</div>
          </div>
        ))}
      </div>
      {fusion.anomaly_head?.available && (
        <div className="rounded-xl border border-paper-line bg-paper p-3">
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-ink">Experimental anomaly head</span>
            <span className="tabular-nums text-[13px] text-ink-600">{fusion.anomaly_head.score}</span>
          </div>
          <p className="text-[12px] text-ink-400 mt-0.5">{fusion.anomaly_head.label}</p>
        </div>
      )}
    </div>
  );
}
