import { useState } from "react";
import * as api from "../api";
import { Pill, Stat, bandColor } from "./ui";

type Layout = "contiguous" | "scattered" | "per_channel";
type PayloadKind = "random" | "compressed";

const LAYOUTS: { id: Layout; label: string; hint: string }[] = [
  { id: "contiguous", label: "Contiguous", hint: "One solid block" },
  { id: "scattered", label: "Scattered", hint: "Pseudo-random slots" },
  { id: "per_channel", label: "Per channel", hint: "Thin slice of every filter" },
];

const PRESETS = [
  {
    id: "textbook",
    label: "Textbook LSB",
    hint: "EvilModel-style, 4 KB in the freed planes",
    cfg: { n_bytes: 4096, n_planes: 6, bit_offset: 0, layout: "contiguous" as Layout, entropy_matched: false, spread_tensors: 1, payload_kind: "random" as PayloadKind },
  },
  {
    id: "quiet",
    label: "Low and slow",
    hint: "256 B on one plane, spread thin",
    cfg: { n_bytes: 256, n_planes: 1, bit_offset: 0, layout: "per_channel" as Layout, entropy_matched: false, spread_tensors: 4, payload_kind: "compressed" as PayloadKind },
  },
  {
    id: "matched",
    label: "Distribution matched",
    hint: "Attacker read our methodology",
    cfg: { n_bytes: 4096, n_planes: 4, bit_offset: 0, layout: "contiguous" as Layout, entropy_matched: true, spread_tensors: 1, payload_kind: "random" as PayloadKind },
  },
  {
    id: "keptplanes",
    label: "Climb to kept planes",
    hint: "Above the precision floor — our blind spot",
    cfg: { n_bytes: 4096, n_planes: 4, bit_offset: 14, layout: "contiguous" as Layout, entropy_matched: false, spread_tensors: 1, payload_kind: "random" as PayloadKind },
  },
];

const GATE_TONE: Record<string, string> = {
  APPROVE: bandColor.green,
  APPROVE_WITH_CAVEATS: bandColor.lime,
  REVIEW: bandColor.amber,
  QUARANTINE: bandColor.amber,
  HARD_BLOCK: bandColor.red,
};

function Slider({
  label, value, min, max, step = 1, onChange, format,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;
}) {
  return (
    <label className="block">
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-[12px] text-ink-600">{label}</span>
        <span className="text-[12px] text-ink tabular-nums font-medium">
          {format ? format(value) : value}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-forest"
      />
    </label>
  );
}

export default function AdversaryLab() {
  const [cfg, setCfg] = useState({
    n_bytes: 4096,
    n_planes: 6,
    bit_offset: 0,
    layout: "contiguous" as Layout,
    entropy_matched: false,
    spread_tensors: 1,
    payload_kind: "random" as PayloadKind,
    seed: 42,
  });
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const set = (patch: Partial<typeof cfg>) => setCfg((c) => ({ ...c, ...patch }));

  async function run() {
    setBusy(true);
    setErr("");
    try {
      setRes(await api.forge({ ...cfg }));
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  const atk = res?.attack;
  const verdict = res?.verdict;
  const att = res?.attestation;
  const zeroCapacity = atk && atk.effective_bytes === 0;
  const planeHi = cfg.bit_offset + cfg.n_planes - 1;

  return (
    <div className="space-y-5">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        Build the attack yourself. The payload is inert filler, embedded into the clean
        gallery model in memory and then put through the same pipeline as every other
        scan — no separate code path, no cached answer.
      </p>

      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => set(p.cfg)}
            title={p.hint}
            className="text-[12px] px-3 py-1.5 rounded-full border border-paper-line text-ink-600
                       hover:border-ink/30 hover:text-ink transition-colors"
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-x-6 gap-y-4">
        <Slider
          label="Payload size"
          value={cfg.n_bytes}
          min={0}
          max={32768}
          step={256}
          onChange={(v) => set({ n_bytes: v })}
          format={(v) => `${(v / 1024).toFixed(v >= 1024 ? 1 : 2)} KB`}
        />
        <Slider
          label="Mantissa planes used"
          value={cfg.n_planes}
          min={1}
          max={8}
          onChange={(v) => set({ n_planes: v })}
          format={(v) => `${v} plane${v > 1 ? "s" : ""}`}
        />
        <Slider
          label="First plane written"
          value={cfg.bit_offset}
          min={0}
          max={18}
          onChange={(v) => set({ bit_offset: v })}
          format={(v) => `b${v} – b${planeHi}`}
        />
        <Slider
          label="Tensors targeted"
          value={cfg.spread_tensors}
          min={1}
          max={5}
          onChange={(v) => set({ spread_tensors: v })}
        />
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div>
          <div className="text-[12px] text-ink-600 mb-1.5">Layout</div>
          <div className="flex flex-col gap-1">
            {LAYOUTS.map((l) => (
              <button
                key={l.id}
                onClick={() => set({ layout: l.id })}
                className={`text-left text-[12px] px-2.5 py-1.5 rounded-lg border transition-colors ${
                  cfg.layout === l.id
                    ? "border-ink bg-ink text-paper-card"
                    : "border-paper-line text-ink-600 hover:border-ink/30"
                }`}
              >
                {l.label}
                <span className={cfg.layout === l.id ? "text-white/55" : "text-ink-400"}>
                  {" · "}{l.hint}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="text-[12px] text-ink-600 mb-1.5">Payload entropy</div>
          <div className="flex flex-col gap-1">
            {(["random", "compressed"] as PayloadKind[]).map((k) => (
              <button
                key={k}
                onClick={() => set({ payload_kind: k })}
                className={`text-left text-[12px] px-2.5 py-1.5 rounded-lg border transition-colors ${
                  cfg.payload_kind === k
                    ? "border-ink bg-ink text-paper-card"
                    : "border-paper-line text-ink-600 hover:border-ink/30"
                }`}
              >
                {k === "random" ? "Uniform random" : "Compressed text"}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="text-[12px] text-ink-600 mb-1.5">Evasion</div>
          <button
            onClick={() => set({ entropy_matched: !cfg.entropy_matched })}
            className={`w-full text-left text-[12px] px-2.5 py-1.5 rounded-lg border transition-colors ${
              cfg.entropy_matched
                ? "border-ink bg-ink text-paper-card"
                : "border-paper-line text-ink-600 hover:border-ink/30"
            }`}
          >
            Distribution matched
            <span className={cfg.entropy_matched ? "text-white/55" : "text-ink-400"}>
              {" · "}{cfg.entropy_matched ? "on" : "off"}
            </span>
          </button>
          <p className="text-[11px] text-ink-400 mt-1.5 leading-snug">
            Draws payload bits from the clean model's own per-plane distribution, so
            entropy tests see nothing unusual.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={run}
          disabled={busy}
          className="text-[13px] px-4 py-2 rounded-full bg-ink text-paper-card
                     hover:bg-ink-800 disabled:opacity-50 transition-colors"
        >
          {busy ? "Embedding and scanning…" : "Embed and scan"}
        </button>
        {res && (
          <span className="text-[12px] text-ink-400 tabular-nums">
            {res.total_ms} ms · seed {cfg.seed}
          </span>
        )}
        <button
          onClick={() => set({ seed: Math.floor(Math.random() * 100000) })}
          className="text-[12px] text-ink-400 hover:text-ink underline decoration-dotted"
        >
          new seed
        </button>
      </div>

      {err && <p className="text-[13px] text-rust">{err}</p>}

      {res && verdict && (
        <div className="space-y-4 pt-1">
          <div className="grid sm:grid-cols-4 gap-3">
            <Stat
              label="Gate"
              value={verdict.gate.replace(/_/g, " ")}
              color={GATE_TONE[verdict.gate]}
              sub={`risk ${verdict.risk_score}`}
            />
            <Stat
              label="Payload placed"
              value={`${atk.effective_bytes} B`}
              sub={
                atk.capacity_shortfall > 0
                  ? `${atk.capacity_shortfall} B could not be encoded`
                  : "full request encoded"
              }
              color={zeroCapacity ? bandColor.amber : undefined}
            />
            <Stat
              label="Output agreement"
              value={
                res.fidelity?.output_agreement_pct != null
                  ? `${res.fidelity.output_agreement_pct}%`
                  : "n/a"
              }
              sub="vs the clean sibling"
            />
            <Stat
              label="Loudest detector"
              value={res.loudest_detector?.replace("l2_", "") || "none"}
              sub={`z = ${res.detector_z?.[res.loudest_detector] ?? 0}`}
            />
          </div>

          <div
            className="rounded-xl px-4 py-3 border"
            style={{
              borderColor: `${GATE_TONE[verdict.gate]}33`,
              background: `${GATE_TONE[verdict.gate]}0f`,
            }}
          >
            <p className="text-[13px] text-ink leading-relaxed">{res.interpretation}</p>
          </div>

          {att?.available && res.evaded && (
            <div className="rounded-xl px-4 py-3 border border-forest/25 bg-forest/[0.06]">
              <div className="flex items-center gap-2 mb-1.5">
                <Pill color={bandColor.green} filled>
                  Attestation caught it
                </Pill>
                <span className="text-[11px] text-ink-400 mono">
                  {att.attested_root}… → {att.candidate_root}…
                </span>
              </div>
              <p className="text-[13px] text-ink leading-relaxed">{att.headline}</p>
              {att.changed_tensors?.length > 0 && (
                <p className="text-[12px] text-ink-600 mt-1.5">
                  Changed: <span className="mono">{att.changed_tensors.join(", ")}</span>
                  {att.changed_regions?.length > 0 && (
                    <> · bits moved in {att.changed_regions.join(", ")}</>
                  )}
                </p>
              )}
            </div>
          )}

          <div>
            <div className="text-[12px] text-ink-600 mb-2">Detector response</div>
            <div className="space-y-1.5">
              {Object.entries(res.detector_z as Record<string, number>)
                .sort((a, b) => b[1] - a[1])
                .map(([k, z]) => (
                  <div key={k} className="flex items-center gap-3">
                    <span className="text-[12px] text-ink-600 w-28 shrink-0">
                      {k.replace("l2_", "")}
                    </span>
                    <div className="flex-1 h-1.5 rounded-full bg-paper-line overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.min(100, (z / 8) * 100)}%`,
                          background: z > 3 ? bandColor.red : z > 1 ? bandColor.amber : bandColor.green,
                        }}
                      />
                    </div>
                    <span className="text-[12px] text-ink-400 tabular-nums w-10 text-right">
                      {z}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {res.contract?.length > 0 && (
            <div>
              <div className="text-[12px] text-ink-600 mb-2">Precision-contract violations</div>
              <div className="space-y-1">
                {res.contract.map((v: any, i: number) => (
                  <p key={i} className="text-[12px] text-ink-600">
                    <span className="mono text-ink">{v.tensor}</span> · {v.occupancy_pct}% of
                    weights occupy {v.freed_planes} · ~{v.est_bytes} B
                  </p>
                ))}
              </div>
            </div>
          )}

          <p className="text-[11px] text-ink-400 leading-snug">
            {atk.note} Payloads are inert bytes; nothing executable is created.
          </p>
        </div>
      )}
    </div>
  );
}
