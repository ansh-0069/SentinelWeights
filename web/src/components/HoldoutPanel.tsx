import { useEffect, useState } from "react";
import * as api from "../api";
import { Pill, Stat, bandColor } from "./ui";

const DELTA_LABELS: Record<string, string> = {
  export_mantissa_bits: "Export contract",
  dtype: "Precision",
  structure: "Structure",
  target_tensor: "Target tensor",
  bit_planes: "Bit depth",
  plane_offset: "Plane offset",
  layout: "Layout",
  payload_entropy: "Payload entropy",
  seeds: "Seeds",
};

const fmt = (v: any) => (Array.isArray(v) ? v.join(", ") : String(v));

export default function HoldoutPanel() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.getHoldout().then(setData).catch((e) => setErr(String(e?.message || e)));
  }, []);

  if (err) return <p className="text-[13px] text-ink-400">Holdout not generated yet.</p>;
  if (!data) return <p className="text-[13px] text-ink-400">Loading holdout…</p>;

  const m = data.metrics;

  return (
    <div className="space-y-5">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        Every number in the benchmark comes from artifacts that share a recipe with the ones
        our thresholds were fitted on, which makes measuring there partly self-congratulation.
        This corpus changes what an attacker or a vendor would plausibly change, and none of
        it fed threshold selection, fusion weights, or baseline fitting.
      </p>

      <div className="grid sm:grid-cols-4 gap-3">
        <Stat
          label="True positive rate"
          value={m.tpr != null ? `${(m.tpr * 100).toFixed(0)}%` : "n/a"}
          sub={`${m.true_positives}/${m.attack_n} unseen attacks`}
          color={m.tpr === 1 ? bandColor.green : bandColor.amber}
        />
        <Stat
          label="False positive rate"
          value={m.fpr != null ? `${(m.fpr * 100).toFixed(0)}%` : "n/a"}
          sub={`${m.false_positives}/${m.clean_n} unseen clean variants`}
          color={m.fpr === 0 ? bandColor.green : bandColor.red}
        />
        <Stat label="Operating point" value={m.operating_point} sub="unchanged from production policy" />
        <Stat
          label="Excluded"
          value={m.excluded_negligible_capacity}
          sub={`configs under ${m.min_effective_bytes} B of real capacity`}
        />
      </div>

      <div>
        <div className="text-[12px] text-ink-600 mb-2">What changed from the calibrated recipe</div>
        <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
          {Object.entries(data.recipe_deltas).map(([k, v]: [string, any]) => (
            <div key={k} className="flex items-baseline gap-2 text-[12px]">
              <span className="text-ink-600 w-28 shrink-0">{DELTA_LABELS[k] || k}</span>
              <span className="text-ink-400 line-through decoration-ink-400/50">
                {fmt(v.calibrated)}
              </span>
              <span className="text-ink-400">→</span>
              <span className="text-ink">{fmt(v.holdout)}</span>
            </div>
          ))}
        </div>
      </div>

      {data.misses?.length > 0 && (
        <div className="rounded-xl border border-rust/25 bg-rust/[0.05] px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <Pill color={bandColor.red} filled>
              {data.misses.length} miss{data.misses.length > 1 ? "es" : ""}
            </Pill>
            <span className="text-[12px] text-ink-600">
              reported rather than tuned away
            </span>
          </div>
          <div className="space-y-1">
            {data.misses.map((r: any, i: number) => (
              <div key={i} className="text-[12px] text-ink-600 flex flex-wrap gap-x-2">
                <span className="mono text-ink">{r.tensor}</span>
                <span>{r.dtype}</span>
                <span>
                  {r.n_planes} planes at b{r.bit_offset}
                </span>
                <span>{r.layout}</span>
                <span>{r.effective_bytes} B</span>
                <span>risk {r.risk_score}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.false_alarms?.length > 0 && (
        <div className="rounded-xl border border-rust/25 bg-rust/[0.05] px-4 py-3">
          <div className="text-[12px] text-ink mb-1.5">
            False alarms on legitimate variants
          </div>
          <div className="space-y-1">
            {data.false_alarms.map((r: any, i: number) => (
              <div key={i} className="text-[12px] text-ink-600">
                {r.variant} (seed {r.seed}) · risk {r.risk_score} · {r.gate}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <div className="text-[12px] text-ink-600 mb-2">
            Unseen clean variants ({data.clean_rows.length})
          </div>
          <div className="space-y-1">
            {data.clean_rows.map((r: any, i: number) => (
              <div key={i} className="flex items-baseline justify-between gap-2 text-[12px]">
                <span className="text-ink-600">
                  {r.variant} <span className="text-ink-400">seed {r.seed}</span>
                </span>
                <span
                  className="tabular-nums"
                  style={{ color: r.flagged ? bandColor.red : bandColor.green }}
                >
                  {r.risk_score}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-[12px] text-ink-600 mb-2">
            Unseen attack recipes ({data.attack_rows.length})
          </div>
          <div className="space-y-1">
            {data.attack_rows.map((r: any, i: number) => (
              <div key={i} className="flex items-baseline justify-between gap-2 text-[12px]">
                <span className="text-ink-600">
                  {r.dtype === "float16" ? "fp16 " : ""}
                  {r.tensor.replace(".weight", "")} · {r.n_planes}p b{r.bit_offset} · {r.layout}
                </span>
                <span
                  className="tabular-nums"
                  style={{
                    color: r.flagged
                      ? bandColor.green
                      : r.effective_bytes < m.min_effective_bytes
                      ? "#8A8278"
                      : bandColor.red,
                  }}
                >
                  {r.risk_score}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <ul className="text-[11px] text-ink-400 space-y-1 leading-snug">
        {data.notes.map((n: string, i: number) => (
          <li key={i}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
