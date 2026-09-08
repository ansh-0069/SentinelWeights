import { useEffect, useMemo, useRef, useState } from "react";
import * as api from "../api";
import { Pill, Stat, bandColor } from "./ui";

export type Layout = "contiguous" | "scattered" | "per_channel";
export type PayloadKind = "random" | "compressed";
export type AttackConfig = api.ForgeRequest;

type Mode = "guided" | "advanced";
type ResultTab = "summary" | "evidence" | "changes" | "attestation";

const DEFAULT_CONFIG: AttackConfig = {
  n_bytes: 4096,
  n_planes: 6,
  bit_offset: 0,
  layout: "contiguous",
  entropy_matched: false,
  spread_tensors: 1,
  payload_kind: "random",
  seed: 42,
};

const LAYOUTS: { id: Layout; label: string; hint: string }[] = [
  { id: "contiguous", label: "Contiguous", hint: "one solid block" },
  { id: "scattered", label: "Scattered", hint: "pseudo-random slots" },
  { id: "per_channel", label: "Per channel", hint: "a thin slice of every filter" },
];

const PRESETS: { id: string; label: string; hint: string; outcome: string; cfg: Omit<AttackConfig, "seed"> }[] = [
  {
    id: "textbook",
    label: "Obvious hidden payload",
    hint: "4 KB in six unused precision planes",
    outcome: "Expected: precision contract blocks it",
    cfg: { n_bytes: 4096, n_planes: 6, bit_offset: 0, layout: "contiguous", entropy_matched: false, spread_tensors: 1, payload_kind: "random" },
  },
  {
    id: "quiet",
    label: "Low and slow",
    hint: "256 B on one plane, spread across filters",
    outcome: "Tests sparse localization",
    cfg: { n_bytes: 256, n_planes: 1, bit_offset: 0, layout: "per_channel", entropy_matched: false, spread_tensors: 4, payload_kind: "compressed" },
  },
  {
    id: "matched",
    label: "Distribution-matched evasion",
    hint: "Mimic the clean model's bit distribution",
    outcome: "Expected: capacity may collapse",
    cfg: { n_bytes: 4096, n_planes: 4, bit_offset: 0, layout: "contiguous", entropy_matched: true, spread_tensors: 1, payload_kind: "random" },
  },
  {
    id: "keptplanes",
    label: "Kept-plane blind spot",
    hint: "Move above the export precision floor",
    outcome: "Expected: statistics may miss; attestation catches drift",
    cfg: { n_bytes: 4096, n_planes: 4, bit_offset: 14, layout: "contiguous", entropy_matched: false, spread_tensors: 1, payload_kind: "random" },
  },
];

const GATE_TONE: Record<string, string> = {
  APPROVE: bandColor.green,
  APPROVE_WITH_CAVEATS: bandColor.lime,
  REVIEW: bandColor.amber,
  QUARANTINE: bandColor.amber,
  HARD_BLOCK: bandColor.red,
};

function Slider({ label, value, min, max, step = 1, onChange, format, help }: {
  label: string; value: number; min: number; max: number; step?: number;
  onChange: (value: number) => void; format?: (value: number) => string; help?: string;
}) {
  return (
    <label className="block" title={help}>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-[12px] text-ink-600">{label}</span>
        <span className="text-[12px] text-ink tabular-nums font-medium">{format ? format(value) : value}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full accent-forest" />
    </label>
  );
}

function MantissaStrip({ offset, count, floor = 11 }: { offset: number; count: number; floor?: number }) {
  return (
    <div>
      <div className="flex justify-between text-[10px] text-ink-400 mb-1">
        <span>least significant · freed by export</span>
        <span>kept model precision · most significant</span>
      </div>
      <div className="grid gap-[2px]" style={{ gridTemplateColumns: "repeat(23, minmax(0, 1fr))" }}>
        {Array.from({ length: 23 }, (_, bit) => {
          const selected = bit >= offset && bit < offset + count;
          const kept = bit >= floor;
          const color = selected ? (kept ? bandColor.red : bandColor.amber) : kept ? "#C7CCFF" : "#DCD6CC";
          return (
            <div key={bit} title={`b${bit} · ${kept ? "kept" : "freed"}${selected ? " · selected" : ""}`}
              className="h-7 rounded-sm flex items-center justify-center text-[9px]"
              style={{ background: color, color: selected ? "#FFFcf8" : "#5C564E" }}>
              {bit % 2 === 0 || selected ? bit : ""}
            </div>
          );
        })}
      </div>
      <div className="text-[10px] text-ink-400 mt-1">b0–b{floor - 1} must remain zero · precision floor at b{floor}</div>
    </div>
  );
}

export default function AdversaryLab({ onExperiment, onExploreFrontier }: {
  onExperiment?: (config: AttackConfig, result: any) => void;
  onExploreFrontier?: () => void;
}) {
  const [cfg, setCfg] = useState<AttackConfig>(DEFAULT_CONFIG);
  const [mode, setMode] = useState<Mode>("guided");
  const [preset, setPreset] = useState("textbook");
  const [preview, setPreview] = useState<any>(null);
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const [err, setErr] = useState("");
  const [resultTab, setResultTab] = useState<ResultTab>("summary");
  const resultRef = useRef<HTMLDivElement>(null);

  const planeHi = Math.min(22, cfg.bit_offset + cfg.n_planes - 1);
  const maxOffset = 23 - cfg.n_planes;

  function update(patch: Partial<AttackConfig>, custom = true) {
    setCfg((current) => {
      const next = { ...current, ...patch };
      next.bit_offset = Math.min(next.bit_offset, 23 - next.n_planes);
      return next;
    });
    if (custom) setPreset("custom");
    if (res) setStale(true);
  }

  function choosePreset(id: string) {
    const selected = PRESETS.find((item) => item.id === id);
    if (!selected) return;
    setCfg((current) => ({ ...selected.cfg, seed: current.seed }));
    setPreset(id);
    if (res) setStale(true);
  }

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      api.previewForge(cfg).then((value) => {
        if (!cancelled) setPreview(value);
      }).catch(() => {
        if (!cancelled) setPreview(null);
      });
    }, 180);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [cfg]);

  async function run() {
    setBusy(true);
    setErr("");
    setStale(false);
    try {
      const value = await api.forge(cfg);
      setRes(value);
      setResultTab("summary");
      onExperiment?.(cfg, value);
      window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (error: any) {
      setErr(String(error?.message || error));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setCfg(DEFAULT_CONFIG);
    setPreset("textbook");
    setRes(null);
    setStale(false);
    setErr("");
  }

  const atk = res?.attack;
  const verdict = res?.verdict;
  const att = res?.attestation;
  const zeroCapacity = atk && atk.effective_bytes === 0;
  const previewSentence = useMemo(() => {
    const layout = LAYOUTS.find((item) => item.id === cfg.layout)?.label.toLowerCase();
    const region = cfg.bit_offset < 11 && planeHi < 11 ? "inside freed precision" :
      cfg.bit_offset >= 11 ? "inside kept model precision" : "across the precision boundary";
    return `Place ${(cfg.n_bytes / 1024).toFixed(cfg.n_bytes >= 1024 ? 1 : 2)} KB across ${cfg.spread_tensors} ${cfg.spread_tensors === 1 ? "tensor" : "tensors"}, using b${cfg.bit_offset}–b${planeHi} in ${layout} positions ${region}.`;
  }, [cfg, planeHi]);

  const resultTabs: { id: ResultTab; label: string }[] = [
    { id: "summary", label: "Why this verdict" },
    { id: "evidence", label: "Detector evidence" },
    { id: "changes", label: "Changed tensors" },
    { id: "attestation", label: "Attestation" },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-ink-600 leading-relaxed max-w-3xl">
          Build a controlled attack with inert bytes, then send it through the same scanner as every other model.
        </p>
        <div className="flex gap-1 p-1 rounded-full bg-paper border border-paper-line" aria-label="Experiment detail">
          {(["guided", "advanced"] as Mode[]).map((item) => (
            <button key={item} onClick={() => setMode(item)}
              className={`text-[12px] px-3 py-1 rounded-full transition-colors ${mode === item ? "bg-ink text-paper-card" : "text-ink-400 hover:text-ink"}`}>
              {item === "guided" ? "Guided demo" : "Advanced controls"}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="text-[11px] uppercase tracking-[0.14em] text-ink-400 mb-2">1 · Choose a scenario</div>
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-2">
          {PRESETS.map((item) => (
            <button key={item.id} onClick={() => choosePreset(item.id)}
              className={`text-left rounded-xl p-3 border transition-all ${preset === item.id ? "border-ink bg-ink text-paper-card shadow-lift" : "border-paper-line bg-paper-card/70 text-ink hover:border-ink/30"}`}>
              <span className="block text-[13px] font-medium">{item.label}</span>
              <span className={`block text-[11px] mt-1 ${preset === item.id ? "text-white/60" : "text-ink-600"}`}>{item.hint}</span>
              <span className={`block text-[10px] mt-2 ${preset === item.id ? "text-mint-soft" : "text-forest"}`}>{item.outcome}</span>
            </button>
          ))}
        </div>
        {preset === "custom" && <div className="mt-2"><Pill color={bandColor.amber}>Custom configuration</Pill></div>}
      </div>

      {mode === "advanced" && (
        <div className="grid lg:grid-cols-3 gap-5 border-y border-paper-line py-4">
          <div className="space-y-4">
            <div className="text-[12px] font-medium text-ink">Payload</div>
            <Slider label="Payload size" value={cfg.n_bytes} min={0} max={32768} step={256}
              onChange={(value) => update({ n_bytes: value })}
              format={(value) => `${(value / 1024).toFixed(value >= 1024 ? 1 : 2)} KB`}
              help="Requested inert payload capacity." />
            <div>
              <div className="text-[12px] text-ink-600 mb-1.5">Payload pattern</div>
              <div className="grid grid-cols-2 gap-1">
                {(["random", "compressed"] as PayloadKind[]).map((kind) => (
                  <button key={kind} disabled={cfg.entropy_matched}
                    onClick={() => update({ payload_kind: kind })}
                    className={`text-left text-[12px] px-2.5 py-2 rounded-lg border transition-colors disabled:opacity-40 ${cfg.payload_kind === kind ? "border-ink bg-ink text-paper-card" : "border-paper-line text-ink-600"}`}>
                    {kind === "random" ? "Uniform random" : "Compressed text"}
                  </button>
                ))}
              </div>
              {cfg.entropy_matched && <p className="text-[10px] text-ink-400 mt-1">Pattern is controlled by distribution matching.</p>}
            </div>
          </div>

          <div className="space-y-4">
            <div className="text-[12px] font-medium text-ink">Placement</div>
            <Slider label="Mantissa planes" value={cfg.n_planes} min={1} max={8}
              onChange={(value) => update({ n_planes: value })}
              format={(value) => `${value} plane${value > 1 ? "s" : ""}`} />
            <Slider label="First plane" value={cfg.bit_offset} min={0} max={maxOffset}
              onChange={(value) => update({ bit_offset: value })}
              format={() => `b${cfg.bit_offset}–b${planeHi}`} />
            <Slider label="Tensors targeted" value={cfg.spread_tensors} min={1} max={5}
              onChange={(value) => update({ spread_tensors: value })} />
          </div>

          <div className="space-y-4">
            <div className="text-[12px] font-medium text-ink">Layout and evasion</div>
            <div className="space-y-1">
              {LAYOUTS.map((layout) => (
                <button key={layout.id} onClick={() => update({ layout: layout.id })}
                  className={`w-full text-left text-[12px] px-2.5 py-2 rounded-lg border transition-colors ${cfg.layout === layout.id ? "border-ink bg-ink text-paper-card" : "border-paper-line text-ink-600"}`}>
                  {layout.label} <span className={cfg.layout === layout.id ? "text-white/55" : "text-ink-400"}>· {layout.hint}</span>
                </button>
              ))}
            </div>
            <button onClick={() => update({ entropy_matched: !cfg.entropy_matched })}
              className={`w-full text-left text-[12px] px-2.5 py-2 rounded-lg border transition-colors ${cfg.entropy_matched ? "border-ink bg-ink text-paper-card" : "border-paper-line text-ink-600"}`}>
              Distribution matching · {cfg.entropy_matched ? "on" : "off"}
            </button>
          </div>
        </div>
      )}

      <div>
        <div className="text-[11px] uppercase tracking-[0.14em] text-ink-400 mb-2">2 · Review the attack</div>
        <div className="rounded-xl bg-paper px-4 py-3 border border-paper-line space-y-3">
          <p className="text-[13px] text-ink leading-relaxed">{previewSentence}</p>
          <MantissaStrip offset={cfg.bit_offset} count={cfg.n_planes} floor={preview?.precision_floor ?? 11} />
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-ink-600">
            <span>Requested <strong className="text-ink">{cfg.n_bytes} B</strong></span>
            <span>Estimated capacity <strong className="text-ink">{preview ? `${preview.capacity_bytes} B` : "measuring…"}</strong></span>
            <span>Status <strong style={{ color: preview?.capacity_shortfall > 0 ? bandColor.amber : bandColor.green }}>
              {preview ? (preview.capacity_shortfall > 0 ? `${preview.capacity_shortfall} B short` : "fits") : "checking"}
            </strong></span>
            {preview?.targets?.length > 0 && <span>Host <strong className="mono text-ink">{preview.targets.join(", ")}</strong></span>}
          </div>
        </div>
      </div>

      <div className="sticky bottom-2 z-10 flex flex-wrap items-center gap-3 rounded-xl bg-paper-card/95 backdrop-blur border border-paper-line px-3 py-2 shadow-lift">
        <span className="text-[11px] uppercase tracking-[0.14em] text-ink-400">3 · Run</span>
        <button onClick={run} disabled={busy || preview?.effective_bytes === 0}
          className="text-[13px] px-4 py-2 rounded-full bg-ink text-paper-card hover:bg-ink-800 disabled:opacity-45 transition-colors">
          {busy ? "Embedding payload → scanning…" : "Run attack simulation"}
        </button>
        <button onClick={reset} className="text-[12px] text-ink-600 hover:text-ink">Reset</button>
        <button onClick={() => update({ seed: Math.floor(Math.random() * 100000) }, false)}
          className="text-[12px] text-ink-400 hover:text-ink underline decoration-dotted">New seed</button>
        <span className="text-[11px] text-ink-400">seed {cfg.seed} · inert bytes · original unchanged</span>
      </div>

      {err && <p role="alert" className="text-[13px] text-rust">{err}</p>}

      {res && verdict && (
        <div ref={resultRef} className={`space-y-4 scroll-mt-24 ${stale ? "opacity-55" : ""}`}>
          {stale && (
            <div role="alert" className="rounded-xl px-4 py-3 border border-butter/30 bg-butter-dim text-[13px] text-ink">
              Configuration changed — run the simulation again to update these results.
            </div>
          )}
          <div className="rounded-2xl px-5 py-4 border" style={{ borderColor: `${GATE_TONE[verdict.gate]}44`, background: `${GATE_TONE[verdict.gate]}0f` }}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] text-ink-400">Simulation result</div>
                <div className="display text-[28px] mt-1" style={{ color: GATE_TONE[verdict.gate] }}>
                  {verdict.gate.replace(/_/g, " ")} — {res.loudest_detector === "l2_contract" ? "precision contract violated" : "attack evidence detected"}
                </div>
                <p className="text-[13px] text-ink-600 mt-1">{res.interpretation}</p>
              </div>
              <button onClick={onExploreFrontier} className="text-[12px] px-3 py-2 rounded-full border border-ink/20 hover:border-ink/50 text-ink">
                Explore this attack in the frontier →
              </button>
            </div>
          </div>

          <div className="grid sm:grid-cols-4 gap-3">
            <Stat label="Gate" value={verdict.gate.replace(/_/g, " ")} color={GATE_TONE[verdict.gate]} sub={`risk ${verdict.risk_score}/100`} />
            <Stat label="Effective payload" value={`${atk.effective_bytes} B`}
              sub={atk.capacity_shortfall > 0 ? `${atk.capacity_shortfall} B not encoded` : "full request encoded"}
              color={zeroCapacity ? bandColor.amber : undefined} />
            <Stat label="Numerical probe agreement"
              value={res.fidelity?.output_agreement_pct != null ? `${res.fidelity.output_agreement_pct}%` : "n/a"}
              sub={`${res.fidelity?.n_probes ?? 0}/512 layer probes within tolerance`} />
            <Stat label="Strongest evidence" value={res.loudest_detector?.replace("l2_", "").replace("contract", "precision contract") || "none"}
              sub={`anomaly strength ${res.detector_z?.[res.loudest_detector] ?? 0}`} />
          </div>

          <div className="flex flex-wrap gap-1.5 border-b border-paper-line pb-2">
            {resultTabs.map((item) => (
              <button key={item.id} onClick={() => setResultTab(item.id)}
                className={`text-[12px] px-3 py-1.5 rounded-full transition-colors ${resultTab === item.id ? "bg-ink text-paper-card" : "text-ink-600 hover:bg-paper"}`}>
                {item.label}
              </button>
            ))}
          </div>

          {resultTab === "summary" && (
            <div className="space-y-3">
              <p className="text-[13px] text-ink leading-relaxed">{res.interpretation}</p>
              <p className="text-[11px] text-ink-400">Probe agreement is measured across 512 numerical layer probes with a 5% relative-error tolerance. It is not full-model or clinical accuracy.</p>
            </div>
          )}

          {resultTab === "evidence" && (
            <div className="space-y-1.5">
              {Object.entries(res.detector_z as Record<string, number>).sort((a, b) => b[1] - a[1]).map(([key, z]) => (
                <div key={key} className="flex items-center gap-3" title="Anomaly strength is normalized detector evidence, not a malware probability.">
                  <span className="text-[12px] text-ink-600 w-32 shrink-0">{key.replace("l2_", "").replace("contract", "precision contract")}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-paper-line overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${Math.min(100, (z / 8) * 100)}%`, background: z > 3 ? bandColor.red : z > 1 ? bandColor.amber : bandColor.green }} />
                  </div>
                  <span className="text-[12px] text-ink-400 tabular-nums w-20 text-right">z {z}</span>
                </div>
              ))}
              <p className="text-[10px] text-ink-400 pt-2">z is anomaly strength, not the probability of malware. Correlated steganography signals are grouped before fusion.</p>
            </div>
          )}

          {resultTab === "changes" && (
            <div className="space-y-2">
              {res.contract?.length > 0 ? res.contract.map((violation: any, index: number) => (
                <div key={index} className="rounded-xl bg-paper border border-paper-line px-4 py-3 text-[12px] text-ink-600">
                  <div className="mono text-ink">{violation.tensor}</div>
                  <div className="mt-1">{violation.occupancy_pct}% of values affected · {violation.freed_planes} · approximately {violation.est_bytes} B occupied</div>
                </div>
              )) : <p className="text-[13px] text-ink-600">No precision-contract violation was localized. Kept-plane changes may still appear in attestation.</p>}
            </div>
          )}

          {resultTab === "attestation" && (
            <div className="rounded-xl px-4 py-3 border border-forest/25 bg-forest/[0.06]">
              {att?.available ? (
                <>
                  <Pill color={att.caught ? bandColor.green : bandColor.amber} filled>{att.caught ? "Attestation detected drift" : "No attested drift"}</Pill>
                  <p className="text-[13px] text-ink mt-2 leading-relaxed">{att.headline}</p>
                  {att.changed_tensors?.length > 0 && <p className="text-[12px] text-ink-600 mt-1.5">Changed: <span className="mono">{att.changed_tensors.join(", ")}</span>{att.changed_regions?.length > 0 && <> · bits moved in {att.changed_regions.join(", ")}</>}</p>}
                  <p className="text-[11px] text-ink-400 mt-2">Attestation proves difference from a previously trusted baseline; it does not prove malicious intent.</p>
                </>
              ) : <p className="text-[13px] text-ink-600">No trusted baseline was available for this comparison.</p>}
            </div>
          )}

          <p className="text-[11px] text-ink-400 leading-snug">{atk.note} The simulation uses inert bytes; nothing executable is created.</p>
        </div>
      )}
    </div>
  );
}
