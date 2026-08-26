import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell, ReferenceLine } from "recharts";
import { chartTheme } from "../chartTheme";

export default function TriggerViewer({ detectors }: { detectors: any }) {
  const l3 = detectors?.l3_backdoor;
  if (!l3 || l3.coverage === "Not applicable")
    return (
      <p className="text-[13px] text-ink-400 leading-relaxed">
        Behavioral hunt not run on this artifact. Requires the synthetic probe model; large-model
        results would be cached and labeled, never a live “pass.”
      </p>
    );

  const per = l3.per_class || [];
  const trig = l3.recovered_trigger;
  const dim = l3.img_dim || 8;
  const data = per.map((c: any) => ({ cls: c.class, ai: c.anomaly_index, flagged: c.flagged }));

  return (
    <div className="space-y-3">
      <div className="inline-flex text-[11px] px-2.5 py-1 rounded-full bg-paper border border-paper-line text-ink-600">
        Synthetic / MNIST-scale — not a clinical diagnostic
      </div>
      <div className="flex gap-4 items-start flex-wrap">
        {trig && (
          <div>
            <div className="text-[12px] text-ink-400 mb-1">Recovered trigger (class {trig.class})</div>
            <div
              className="grid gap-[2px] p-1.5 bg-paper border border-paper-line rounded-xl"
              style={{ gridTemplateColumns: `repeat(${dim}, 14px)` }}
            >
              {trig.mask.map((v: number, i: number) => (
                <div
                  key={i}
                  className="w-[14px] h-[14px] rounded-[2px]"
                  style={{ background: `rgba(180,35,24,${Math.min(1, Math.max(0.08, v * 3))})`, border: "1px solid #E6E0D6" }}
                  title={v.toFixed(2)}
                />
              ))}
            </div>
            <div className="text-[12px] text-ink-400 mt-1">Small, sparse corner patch → backdoor-consistent</div>
          </div>
        )}
        <div className="flex-1 min-w-[240px]">
          <div className="text-[12px] text-ink-400 mb-1">Per-class trigger anomaly index (MAD). Flag &gt; 2.</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
              <XAxis dataKey="cls" tick={{ fontSize: 10, fill: chartTheme.tick }} />
              <YAxis tick={{ fontSize: 10, fill: chartTheme.tick }} />
              <Tooltip contentStyle={chartTheme.tooltip} />
              <ReferenceLine y={2} stroke="#C2410C" strokeDasharray="4 3" />
              <Bar dataKey="ai" radius={[3, 3, 0, 0]}>
                {data.map((d: any, i: number) => (
                  <Cell key={i} fill={d.flagged ? chartTheme.danger : "#D9D2C6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <p className="text-[13px] text-ink-600 leading-relaxed">{l3.summary} — treated as suspicion-elevating, not proof.</p>
      {l3.input_discrepancy && (
        <div className="rounded-xl border border-paper-line bg-paper p-3 text-[13px] text-ink space-y-1">
          <div className="text-ink">Train-like vs adversarial (patched) inputs</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-ink-600">
            <span>Clean acc {l3.input_discrepancy.clean_acc}</span>
            <span>Triggered acc {l3.input_discrepancy.triggered_acc}</span>
            <span>ASR {l3.input_discrepancy.attack_success_rate}</span>
            <span>Drop {l3.input_discrepancy.accuracy_drop}</span>
          </div>
          <p className="text-[12px] text-ink-400">{l3.input_discrepancy.note}</p>
        </div>
      )}
    </div>
  );
}
