import {
  ResponsiveContainer, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid, Area, ComposedChart,
} from "recharts";
import { chartTheme } from "../chartTheme";

export default function EntropyProfileChart({ detectors }: { detectors: any }) {
  const profiles = detectors?.l2_bitplane?.profiles || [];
  if (!profiles.length)
    return <p className="text-[13px] text-ink-400">No bit-plane profile (weights not loaded).</p>;
  const p = profiles[0];
  const data = p.observed.map((h: number, i: number) => ({
    bit: `b${i}`,
    observed: h,
    baseline: p.baseline[i],
    excess: Math.max(0, h - p.baseline[i]),
  }));

  return (
    <div>
      <p className="text-[13px] text-ink-600 mb-2 leading-relaxed">
        Tensor <span className="font-mono text-[12px]">{p.tensor}</span> — observed mantissa-bit entropy
        vs. architecture/dtype baseline. Excess in mid bits is the entropy cliff.
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
          <XAxis dataKey="bit" tick={{ fontSize: 9, fill: chartTheme.tick }} interval={0} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: chartTheme.tick }} />
          <Tooltip contentStyle={chartTheme.tooltip} />
          <Legend wrapperStyle={{ fontSize: 11, color: "#5C564E" }} />
          <Area dataKey="excess" fill="#B4231833" stroke="none" name="excess" />
          <Line dataKey="baseline" stroke={chartTheme.muted} strokeDasharray="4 3" dot={false} name="clean baseline" />
          <Line dataKey="observed" stroke={chartTheme.accent} strokeWidth={2} dot={false} name="observed" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
