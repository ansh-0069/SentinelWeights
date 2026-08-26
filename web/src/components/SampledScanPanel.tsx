import { useState } from "react";
import * as api from "../api";
import { Pill, Stat, bandColor } from "./ui";

const GATE_TONE: Record<string, string> = {
  APPROVE: bandColor.green,
  APPROVE_WITH_CAVEATS: bandColor.lime,
  REVIEW: bandColor.amber,
  QUARANTINE: bandColor.amber,
  HARD_BLOCK: bandColor.red,
};

export default function SampledScanPanel() {
  const [fraction, setFraction] = useState(0.05);
  const [targetMb, setTargetMb] = useState(96);
  const [replicates, setReplicates] = useState(6);
  const [embed, setEmbed] = useState(true);
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function run() {
    setBusy(true);
    setErr("");
    try {
      setRes(
        await api.sampledScan({
          fraction,
          replicates,
          target_mb: targetMb,
          embed_payload: embed,
          seed: 0,
        })
      );
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  const est = res?.estimate;
  const ci = est?.ci95;

  return (
    <div className="space-y-5">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        A real deployment scans checkpoints measured in gigabytes, and "it scales" is the
        easiest claim in the world to assert without evidence. So this builds a large
        artifact on this machine right now, reads only a stratified sample of whole output
        channels, and reports an interval instead of a single confident number.
      </p>

      <div className="grid sm:grid-cols-3 gap-x-6 gap-y-4">
        <label className="block">
          <div className="flex items-baseline justify-between mb-1.5">
            <span className="text-[12px] text-ink-600">Sampling fraction</span>
            <span className="text-[12px] text-ink tabular-nums font-medium">
              {(fraction * 100).toFixed(1)}%
            </span>
          </div>
          <input
            type="range"
            min={0.01}
            max={0.5}
            step={0.01}
            value={fraction}
            onChange={(e) => setFraction(Number(e.target.value))}
            className="w-full accent-forest"
          />
        </label>
        <label className="block">
          <div className="flex items-baseline justify-between mb-1.5">
            <span className="text-[12px] text-ink-600">Fixture size</span>
            <span className="text-[12px] text-ink tabular-nums font-medium">{targetMb} MB</span>
          </div>
          <input
            type="range"
            min={16}
            max={512}
            step={16}
            value={targetMb}
            onChange={(e) => setTargetMb(Number(e.target.value))}
            className="w-full accent-forest"
          />
        </label>
        <label className="block">
          <div className="flex items-baseline justify-between mb-1.5">
            <span className="text-[12px] text-ink-600">Replicates</span>
            <span className="text-[12px] text-ink tabular-nums font-medium">{replicates}</span>
          </div>
          <input
            type="range"
            min={2}
            max={16}
            value={replicates}
            onChange={(e) => setReplicates(Number(e.target.value))}
            className="w-full accent-forest"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={() => setEmbed(!embed)}
          className={`text-[12px] px-3 py-1.5 rounded-full border transition-colors ${
            embed
              ? "border-ink bg-ink text-paper-card"
              : "border-paper-line text-ink-600 hover:border-ink/30"
          }`}
        >
          {embed ? "Payload embedded" : "Clean fixture"}
        </button>
        <button
          onClick={run}
          disabled={busy}
          className="text-[13px] px-4 py-2 rounded-full bg-ink text-paper-card
                     hover:bg-ink-800 disabled:opacity-50"
        >
          {busy ? `Building ${targetMb} MB and scanning…` : "Generate and triage"}
        </button>
        {busy && (
          <span className="text-[12px] text-ink-400">
            training, tiling, writing to disk, then {replicates} independent sampled passes
          </span>
        )}
      </div>

      {err && <p className="text-[13px] text-rust">{err}</p>}

      {res && res.supported === false && (
        <p className="text-[13px] text-ink-600">{res.reason}</p>
      )}

      {res?.supported && (
        <div className="space-y-4">
          <div className="grid sm:grid-cols-4 gap-3">
            <Stat
              label="Artifact"
              value={`${res.file.size_mb} MB`}
              sub={`${res.file.num_tensors} tensors · ${(res.file.total_params / 1e6).toFixed(1)}M params`}
            />
            <Stat
              label="Bytes actually read"
              value={`${res.sampling.bytes_read_mb} MB`}
              sub={`${(res.sampling.achieved_fraction * 100).toFixed(2)}% of the file`}
            />
            <Stat
              label="Estimated risk"
              value={est.risk_score_mean}
              sub={ci ? `95% interval ${ci[0]} – ${ci[1]}` : undefined}
              color={GATE_TONE[est.gate]}
            />
            <Stat
              label="Wall clock"
              value={`${(res.timing.total_ms / 1000).toFixed(1)}s`}
              sub={`${res.timing.mean_replicate_ms} ms per pass · ${res.timing.static_ms} ms static`}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Pill color={GATE_TONE[est.gate]} filled>
              {est.gate.replace(/_/g, " ")}
            </Pill>
            {est.gate_stable ? (
              <Pill color={bandColor.green}>
                same gate across all {res.sampling.replicates} replicates
              </Pill>
            ) : (
              <Pill color={bandColor.amber}>
                gate agreement {(est.gate_agreement * 100).toFixed(0)}% — near a band edge
              </Pill>
            )}
            <span className="text-[12px] text-ink-400">
              spread {est.risk_score_min} – {est.risk_score_max}, σ = {est.risk_score_std}
            </span>
          </div>

          <div>
            <div className="text-[12px] text-ink-600 mb-2">Per replicate</div>
            <div className="flex flex-wrap gap-1.5">
              {est.per_replicate.map((r: any, i: number) => (
                <div
                  key={i}
                  className="rounded-lg px-2.5 py-1.5 border text-center"
                  style={{
                    borderColor: `${GATE_TONE[r.gate]}33`,
                    background: `${GATE_TONE[r.gate]}0f`,
                  }}
                >
                  <div
                    className="text-[13px] font-medium tabular-nums leading-none"
                    style={{ color: GATE_TONE[r.gate] }}
                  >
                    {r.risk_score}
                  </div>
                  <div className="text-[10px] text-ink-400 mt-0.5">{r.ms} ms</div>
                </div>
              ))}
            </div>
          </div>

          {res.generated_fixture && (
            <p className="text-[12px] text-ink-600">
              Fixture built on this machine — {res.generated_fixture.num_tensors} tensors,{" "}
              {res.generated_fixture.size_mb} MB, {res.generated_fixture.payload} — then
              deleted. Nothing about this result was precomputed.
            </p>
          )}

          <ul className="text-[11px] text-ink-400 space-y-1 leading-snug">
            {res.caveats.map((c: string, i: number) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
