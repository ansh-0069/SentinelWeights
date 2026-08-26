import { useEffect, useState } from "react";
import * as api from "../api";
import { Pill, Stat, bandColor } from "./ui";

const GATE_TONE: Record<string, string> = {
  APPROVE: bandColor.green,
  APPROVE_WITH_CAVEATS: bandColor.lime,
  REVIEW: bandColor.amber,
  QUARANTINE: bandColor.amber,
  HARD_BLOCK: bandColor.red,
};

const REL_TONE: Record<string, string> = {
  identical: bandColor.red,
  derived: bandColor.amber,
  weak: "#8A8278",
};

export default function MeasuredLineage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.getLineage().then(setData).catch((e) => setErr(String(e?.message || e)));
  }, []);

  if (err) return <p className="text-[13px] text-ink-400">Lineage unavailable.</p>;
  if (!data) return <p className="text-[13px] text-ink-400">Hashing the vault…</p>;

  const loadable = data.nodes.filter((n: any) => n.loadable !== false);

  return (
    <div className="space-y-5">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        Every artifact in the vault is hashed tensor by tensor, so shared provenance is
        measured rather than drawn. That turns lineage into a detector: if a blocked model
        shares eleven of twelve tensors byte-identically with an approved one, it is a
        derivative of that approved model and the payload lives in the tensor that differs.
      </p>

      <div className="grid sm:grid-cols-4 gap-3">
        <Stat label="Artifacts hashed" value={data.nodes.length} sub={`${loadable.length} loadable`} />
        <Stat label="Related pairs" value={data.edges.length} sub="non-zero tensor overlap" />
        <Stat label="Derived pairs" value={data.derived_pairs} sub="≥50% byte-identical" />
        <Stat
          label="Propagation findings"
          value={data.propagation.length}
          color={data.propagation.length ? bandColor.amber : undefined}
          sub="approved model with a tainted sibling"
        />
      </div>

      {data.propagation.length > 0 && (
        <div className="space-y-2">
          {data.propagation.map((p: any, i: number) => (
            <div key={i} className="rounded-xl border border-rust/25 bg-rust/[0.05] px-4 py-3">
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <Pill color={bandColor.green}>{p.approved}</Pill>
                <span className="text-ink-400 text-[12px]">
                  shares {(p.tensor_overlap * 100).toFixed(0)}% of tensors with
                </span>
                <Pill color={GATE_TONE[p.flagged_gate] || bandColor.red} filled>
                  {p.flagged} · {p.flagged_gate?.replace(/_/g, " ")}
                </Pill>
              </div>
              <p className="text-[13px] text-ink leading-relaxed">{p.finding}</p>
              <p className="text-[12px] text-ink-600 mt-1">
                {(p.param_overlap * 100).toFixed(1)}% of parameters are byte-identical, so
                the divergence is a localized edit, not a retrain.
              </p>
            </div>
          ))}
        </div>
      )}

      <div>
        <div className="text-[12px] text-ink-600 mb-2">Artifacts</div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {data.nodes.map((n: any) => (
            <div key={n.id} className="rounded-lg border border-paper-line bg-paper px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[12px] text-ink font-medium truncate">{n.label}</span>
                {n.gate && (
                  <Pill color={GATE_TONE[n.gate] || "#8A8278"}>{n.gate.replace(/_/g, " ")}</Pill>
                )}
              </div>
              <div className="text-[11px] text-ink-400 mt-0.5">
                {n.loadable === false ? (
                  <>not loadable{n.error ? ` (${n.error})` : ""} — excluded from hashing</>
                ) : (
                  <>
                    {n.num_tensors} tensors · {(n.total_params / 1000).toFixed(1)}k params
                  </>
                )}
              </div>
              {n.merkle_root && (
                <div className="mono text-[10px] text-ink-400 mt-0.5">{n.merkle_root}…</div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="text-[12px] text-ink-600 mb-2">Measured relationships</div>
        <div className="space-y-1.5">
          {data.edges.map((e: any, i: number) => (
            <div key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <Pill color={REL_TONE[e.relation] || "#8A8278"}>{e.relation}</Pill>
              <span className="text-[12px] text-ink">
                {e.a} ↔ {e.b}
              </span>
              <span className="text-[12px] text-ink-400 tabular-nums">
                {e.n_identical} identical / {e.n_differing} differing ·{" "}
                {(e.tensor_overlap * 100).toFixed(0)}% overlap
              </span>
              {e.differing_tensors.length > 0 && e.differing_tensors.length <= 3 && (
                <span className="mono text-[11px] text-rust">
                  Δ {e.differing_tensors.join(", ")}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="text-[11px] text-ink-400 space-y-1 leading-snug">
        <p>{data.method}</p>
        {data.notes.map((n: string, i: number) => (
          <p key={i}>{n}</p>
        ))}
      </div>
    </div>
  );
}
