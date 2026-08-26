import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";
import type { Region } from "../types";
import { chartTheme } from "../chartTheme";

export default function LayerRiskBars({ detectors }: { detectors: any }) {
  const perLayer = detectors?.l2_distdiv?.per_layer || [];
  const regions: Region[] = detectors?.l2_window?.regions || [];
  const flagged = new Set(regions.map((r) => r.tensor));
  const bitplane = detectors?.l2_bitplane?.profiles || [];
  const bpMap: Record<string, number> = {};
  bitplane.forEach((p: any) => (bpMap[p.tensor] = p.excess_mid));

  if (!perLayer.length)
    return <p className="text-[13px] text-ink-400">No per-layer statistics (weights not loaded).</p>;

  const data = perLayer
    .map((l: any) => {
      const bp = bpMap[l.tensor] || 0;
      const risk = Math.min(100, Math.round((l.incompressibility * 60 + Math.min(1, bp / 2.5) * 40) + (flagged.has(l.tensor) ? 30 : 0)));
      return { tensor: l.tensor.replace(".weight", ""), risk: Math.min(100, risk), flagged: flagged.has(l.tensor) };
    })
    .sort((a: any, b: any) => b.risk - a.risk)
    .slice(0, 12);

  return (
    <div>
      <p className="text-[13px] text-ink-600 mb-2">Per-tensor suspicion (localized). Red = a flagged region.</p>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 24)}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 12, left: 40, bottom: 0 }}>
          <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 9, fill: chartTheme.tick }} />
          <YAxis type="category" dataKey="tensor" tick={{ fontSize: 9, fill: chartTheme.tick }} width={70} />
          <Tooltip contentStyle={chartTheme.tooltip} />
          <Bar dataKey="risk" radius={[0, 3, 3, 0]}>
            {data.map((d: any, i: number) => (
              <Cell key={i} fill={d.flagged ? chartTheme.danger : d.risk > 40 ? "#C2410C" : chartTheme.accent} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
