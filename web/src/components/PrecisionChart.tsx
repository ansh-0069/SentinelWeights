import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { chartTheme } from "../chartTheme";

export default function PrecisionChart({ detectors }: { detectors: any }) {
  const d = detectors?.l2_precision;
  const curve = d?.curve || [];
  if (!curve.length)
    return <p className="text-[13px] text-ink-400">Precision probe not applicable for this artifact.</p>;
  const data = curve.map((c: any) => ({ k: `k=${c.k}`, change: c.rel_change * 100 }));
  return (
    <div>
      <p className="text-[13px] text-ink-600 mb-2 leading-relaxed">
        Functional output change (%) as the lowest <span className="font-mono text-[12px]">k</span> mantissa bits are cleared.
        A flat curve with high tolerable-k = spare dead-space capacity.
        Tolerated k ≈ <span className="font-mono text-[12px]">{d.tolerated_k}</span>.
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
          <XAxis dataKey="k" tick={{ fontSize: 10, fill: chartTheme.tick }} />
          <YAxis tick={{ fontSize: 10, fill: chartTheme.tick }} />
          <Tooltip
            contentStyle={chartTheme.tooltip}
            formatter={(v: any) => [`${Number(v).toFixed(4)}%`, "output change"]}
          />
          <Bar dataKey="change" fill={chartTheme.accent} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
