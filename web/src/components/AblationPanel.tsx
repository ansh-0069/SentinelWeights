import { useEffect, useState } from "react";
import * as api from "../api";
import { Pill, Stat, bandColor } from "./ui";

const CONTROL_LABELS: Record<string, string> = {
  sentinelweights: "SentinelWeights",
  file_hash_vs_baseline: "File hash vs baseline",
  accuracy_regression: "Accuracy regression suite",
  byte_signature_scan: "Byte signature scan",
  format_policy_reject_pickle: "Format policy (safetensors only)",
};

function Bar({ caught, of, tone }: { caught: number; of: number; tone: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-paper-line overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${of ? (caught / of) * 100 : 0}%`, background: tone }}
        />
      </div>
      <span className="text-[12px] text-ink tabular-nums w-12 text-right">
        {caught}/{of}
      </span>
    </div>
  );
}

export default function AblationPanel() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.getAblation().then(setData).catch((e) => setErr(String(e?.message || e)));
  }, []);

  if (err) return <p className="text-[13px] text-ink-400">Ablation not generated yet.</p>;
  if (!data) return <p className="text-[13px] text-ink-400">Loading ablation…</p>;

  const loo = data.leave_one_out;
  const alt = data.alternative_controls;
  const cov = alt.coverage;

  return (
    <div className="space-y-7">
      <section className="space-y-4">
        <div>
          <h4 className="text-[14px] text-ink font-medium">Does every detector earn its weight?</h4>
          <p className="text-[13px] text-ink-600 leading-relaxed mt-1">
            We re-fuse the stored feature vectors through the real fusion function with one
            weight group zeroed, then again with that group as the only contributor. Two
            columns because they answer different questions, and a detector can score zero
            on the first while scoring high on the second — that means redundant here, not
            useless.
          </p>
        </div>

        {!loo.available ? (
          <p className="text-[13px] text-ink-400">{loo.reason}</p>
        ) : (
          <>
            <div className="grid sm:grid-cols-3 gap-3">
              <Stat label="Full-stack AUC" value={loo.full_auc} sub={`threshold ${loo.operating_point.risk_score_threshold}`} />
              <Stat
                label="Corpus"
                value={loo.corpus.n}
                sub={`${loo.corpus.attacks} attacks · ${loo.corpus.clean} clean · ${loo.corpus.sources.join(" + ")}`}
              />
              <Stat
                label="Confusion at threshold"
                value={`${loo.full_confusion.tp} TP · ${loo.full_confusion.fp} FP`}
                sub={`${loo.full_confusion.fn} FN · ${loo.full_confusion.tn} TN`}
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-ink-400 text-left">
                    <th className="font-normal py-1.5 pr-3">Detector group</th>
                    <th className="font-normal py-1.5 pr-3">Weight</th>
                    <th className="font-normal py-1.5 pr-3">AUC without</th>
                    <th className="font-normal py-1.5 pr-3">AUC change if removed</th>
                    <th className="font-normal py-1.5 pr-3">AUC alone</th>
                    <th className="font-normal py-1.5 pr-3">Δ TP / Δ FP</th>
                    <th className="font-normal py-1.5">Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {loo.rows.map((r: any) => (
                    <tr key={r.detector_group} className="border-t border-paper-line">
                      <td className="py-1.5 pr-3 text-ink">{r.detector_group.replace(/_/g, " ")}</td>
                      <td className="py-1.5 pr-3 text-ink-600 tabular-nums">{r.weight}</td>
                      <td className="py-1.5 pr-3 text-ink-600 tabular-nums">{r.auc_without}</td>
                      <td
                        className="py-1.5 pr-3 tabular-nums font-medium"
                        style={{
                          color:
                            r.delta_auc > 0.01
                              ? bandColor.red
                              : r.delta_auc < -0.01
                              ? bandColor.amber
                              : "#8A8278",
                        }}
                      >
                        {r.delta_auc > 0 ? "−" : r.delta_auc < 0 ? "+" : ""}
                        {Math.abs(r.delta_auc).toFixed(4)}
                      </td>
                      <td className="py-1.5 pr-3 tabular-nums text-ink-600">{r.auc_solo}</td>
                      <td className="py-1.5 pr-3 tabular-nums text-ink-600">
                        {r.delta_tp} / {r.delta_fp}
                      </td>
                      <td className="py-1.5">
                        {r.load_bearing ? (
                          <Pill color={bandColor.red}>load bearing</Pill>
                        ) : r.removal_improves_auc ? (
                          <Pill color={bandColor.amber}>ranking better without it</Pill>
                        ) : r.informative_alone ? (
                          <Pill color={bandColor.amber}>redundant here</Pill>
                        ) : (
                          <Pill color="#8A8278">no signal on this corpus</Pill>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-[11px] text-ink-400 leading-snug">{loo.note}</p>
          </>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h4 className="text-[14px] text-ink font-medium">
            Would existing tooling have caught this anyway?
          </h4>
          <p className="text-[13px] text-ink-600 leading-relaxed mt-1">
            The fair question, and the one worth losing on. Each control is actually
            executed against the gallery. Where a conventional control wins, we say so — the
            format policy and the signature scan really do stop the malicious pickle. Neither
            reads a float mantissa, which is the specific gap this tool exists to close.
          </p>
        </div>

        <div className="space-y-2.5">
          {Object.entries(cov).map(([k, v]: [string, any]) => (
            <div key={k}>
              <div className="flex items-baseline justify-between mb-1">
                <span
                  className="text-[12px]"
                  style={{ color: k === "sentinelweights" ? "#14110F" : "#57534E" }}
                >
                  {CONTROL_LABELS[k] || k}
                </span>
                <span className="text-[11px] text-ink-400">
                  {v.of ? Math.round((v.caught / v.of) * 100) : 0}% of tampered artifacts
                </span>
              </div>
              <Bar
                caught={v.caught}
                of={v.of}
                tone={k === "sentinelweights" ? bandColor.green : bandColor.amber}
              />
            </div>
          ))}
        </div>

        <div>
          <div className="text-[12px] text-ink-600 mb-2">Per-artifact detail</div>
          <div className="space-y-1">
            {alt.rows.map((r: any) => (
              <div key={r.sample} className="rounded-lg border border-paper-line">
                <button
                  onClick={() => setOpen(open === r.sample ? null : r.sample)}
                  className="w-full flex items-center justify-between gap-3 px-3 py-2 text-left"
                >
                  <span className="text-[12px] text-ink">{r.label}</span>
                  <span className="flex items-center gap-1.5 shrink-0">
                    {r.kind === "clean" && <Pill color="#8A8278">clean</Pill>}
                    {r.kind === "unreadable" && (
                      <Pill color="#8A8278">unreadable · not counted</Pill>
                    )}
                    {r.tampered && (
                      <Pill color={r.sentinel_catches ? bandColor.green : bandColor.red}>
                        {r.sentinel_catches ? "we catch it" : "we miss it"}
                      </Pill>
                    )}
                    <span className="text-[11px] text-ink-400">
                      {r.tampered
                        ? `${
                            Object.values(r.controls).filter((c: any) => c.catches).length
                          }/4 conventional`
                        : ""}
                    </span>
                  </span>
                </button>
                {open === r.sample && (
                  <div className="px-3 pb-2.5 space-y-1.5 border-t border-paper-line pt-2">
                    {Object.entries(r.controls).map(([k, c]: [string, any]) => (
                      <div key={k} className="flex gap-2">
                        <span
                          className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                          style={{ background: c.catches ? bandColor.green : "#D6CFC4" }}
                        />
                        <div>
                          <div className="text-[12px] text-ink">{CONTROL_LABELS[k] || k}</div>
                          <div className="text-[11px] text-ink-400 leading-snug">{c.detail}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <p className="text-[11px] text-ink-400 leading-snug">{alt.note}</p>
      </section>
    </div>
  );
}
