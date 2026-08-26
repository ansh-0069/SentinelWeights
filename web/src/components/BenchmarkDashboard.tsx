import { useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ScatterChart, Scatter, ZAxis,
} from "recharts";
import { Stat } from "./ui";
import { chartTheme } from "../chartTheme";

export default function BenchmarkDashboard({ bench }: { bench: any }) {
  const defaultThr = bench?.operating_point?.score_threshold ?? 0.51;
  const [thr, setThr] = useState(defaultThr);
  const scores: number[] = bench?.scores || [];
  const labels: number[] = bench?.labels || [];

  const cm = useMemo(() => {
    let tp = 0, fp = 0, tn = 0, fn = 0;
    scores.forEach((s, i) => {
      const pred = s >= thr ? 1 : 0;
      if (pred === 1 && labels[i] === 1) tp++;
      else if (pred === 1 && labels[i] === 0) fp++;
      else if (pred === 0 && labels[i] === 0) tn++;
      else fn++;
    });
    return { tp, fp, tn, fn };
  }, [thr, scores, labels]);

  if (!bench) return <p className="text-[13px] text-ink-400">Benchmark not loaded.</p>;

  const roc = (bench.roc?.fpr || []).map((f: number, i: number) => ({ fpr: f, tpr: bench.roc.tpr[i] }));
  const latency = (bench.latency_vs_params || []).map((d: any) => ({ x: d.params, y: d.ms }));
  const pol = bench.confusion_at_policy;
  const nClean = bench.corpus?.clean ?? 0;
  const fprPol = pol && nClean ? (pol.fp / nClean) : null;

  return (
    <div className="space-y-4">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        Full pipeline (fusion + policy). Operating point is Model Risk Score ≥ 51
        (REVIEW band), not a raw detector cut at 0.15.
        {bench.roc?.note ? ` ${bench.roc.note}.` : ""}
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Stat label="ROC AUC" value={bench.roc.auc} color="#1F6F5B" />
        <Stat label="Corpus" value={`${bench.corpus.clean}+${bench.corpus.tampered}`} sub="clean+tampered" />
        <Stat label="Latency mean" value={`${bench.latency_ms.mean} ms`} sub={`p95 ${bench.latency_ms.p95} ms`} />
        <Stat label="Per-attack det." value={Object.entries(bench.per_attack_detection || {}).map(([k, v]) => `${k[0]}:${v}`).join(" ")} />
      </div>
      {pol && (
        <div className="rounded-xl border border-paper-line bg-paper p-3 text-[13px] text-ink">
          Policy point (t=0.51): TP {pol.tp} · FP {pol.fp} · TN {pol.tn} · FN {pol.fn}
          {fprPol != null && <span className="text-ink-400"> · clean FPR {(fprPol * 100).toFixed(0)}%</span>}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <div className="text-[12px] text-ink-400 mb-1">ROC curve (full-pipeline TPR vs FPR)</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={roc} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
              <XAxis dataKey="fpr" type="number" domain={[0, 1]} tick={{ fontSize: 9, fill: chartTheme.tick }} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 9, fill: chartTheme.tick }} />
              <Tooltip contentStyle={chartTheme.tooltip} />
              <Line dataKey="tpr" stroke={chartTheme.accent} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div>
          <div className="text-[12px] text-ink-400 mb-1">Scan latency vs. model size (params)</div>
          <ResponsiveContainer width="100%" height={200}>
            <ScatterChart margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
              <XAxis dataKey="x" name="params" tick={{ fontSize: 9, fill: chartTheme.tick }} />
              <YAxis dataKey="y" name="ms" tick={{ fontSize: 9, fill: chartTheme.tick }} />
              <ZAxis range={[40, 40]} />
              <Tooltip contentStyle={chartTheme.tooltip} />
              <Scatter data={latency} fill={chartTheme.accent} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-paper-line bg-paper p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[13px] text-ink">
            Threshold on full-pipeline score — default is the policy band (0.51)
          </span>
          <span className="tabular-nums text-[13px] text-ink-600">t = {thr.toFixed(2)}</span>
        </div>
        <input
          type="range" min={0} max={1} step={0.01} value={thr}
          onChange={(e) => setThr(Number(e.target.value))}
          className="w-full accent-forest"
        />
        <div className="grid grid-cols-4 gap-2 mt-3">
          <Stat label="True Pos" value={cm.tp} color="#1F6F5B" />
          <Stat label="False Pos" value={cm.fp} color="#B42318" />
          <Stat label="True Neg" value={cm.tn} color="#1F6F5B" />
          <Stat label="False Neg" value={cm.fn} color="#C2410C" />
        </div>
      </div>
      {bench["confusion_at_0.15"]?.note && (
        <p className="text-[12px] text-ink-400">{bench["confusion_at_0.15"].note}</p>
      )}
      <p className="text-[12px] text-ink-400">{bench.corpus?.method}</p>
    </div>
  );
}
