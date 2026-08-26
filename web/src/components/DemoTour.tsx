import { useState } from "react";

export const STEPS = [
  { id: "clean", label: "Clean", n: "01", tip: "Baseline SGD-trained CNN — APPROVE, risk ~2." },
  { id: "vendor_reexport", label: "Vendor .pt", n: "02", tip: "Unsigned re-export bundle — static findings logged, still APPROVE (~11)." },
  { id: "borderline_backdoor", label: "Borderline", n: "03", tip: "Weak trigger implant — APPROVE WITH CAVEATS (~43). Not a full backdoor." },
  { id: "backdoor_toycnn", label: "Backdoor", n: "04", tip: "Confirmed tiny trigger — REVIEW (~78). Synthetic toy net." },
  { id: "stego_contiguous", label: "Stego", n: "05", tip: "Freed-plane payload — HARD BLOCK (~100). ~100% output agreement." },
  { id: "stego_silent", label: "Silent stego", n: "06", tip: "Kept-plane evasion — APPROVE on scan; attestation catches drift." },
  { id: "pickle_fixture", label: "Pickle", n: "07", tip: "os.system in pickle — L1 CRITICAL HARD BLOCK. Never loaded." },
  { id: "zip_slip", label: "Zip slip", n: "08", tip: "Path traversal in archive — L1 CRITICAL HARD BLOCK." },
  { id: "truncated", label: "Truncated", n: "09", tip: "Corrupt safetensors — QUARANTINE. Fail-safe." },
  { id: "public_clean", label: "Public", n: "10", tip: "Third-party int8 fixture — APPROVE. We do not cry wolf." },
  { id: "quantized_clean", label: "Quantized", n: "11", tip: "Legitimate int8 export — APPROVE despite low entropy." },
  { id: "malformed", label: "Malformed", n: "12", tip: "Unknown format — QUARANTINE. Then try PDF Verify." },
];

export default function DemoTour({
  onSelect,
  activeId,
}: {
  onSelect: (sampleId: string) => void;
  activeId?: string;
}) {
  const [step, setStep] = useState(0);

  function go(i: number) {
    setStep(i);
    onSelect(STEPS[i].id);
  }

  const current = STEPS[step];
  const progress = ((step + 1) / STEPS.length) * 100;

  return (
    <div className="space-y-3.5">
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="display text-[26px] leading-none text-ink/25 tabular-nums">
              {current.n}
            </span>
            <span className="text-[13px] font-medium text-ink">{current.label}</span>
          </div>
          <p
            key={current.id}
            className="text-[13.5px] text-ink-600 max-w-2xl leading-relaxed animate-fade-up"
          >
            {current.tip}
          </p>
        </div>

        <div className="flex gap-2 shrink-0">
          <button
            className="h-9 px-3.5 rounded-full border border-paper-line text-[13px] text-ink-600 press transition-all duration-300 hover:border-ink/30 hover:bg-paper-card disabled:opacity-30 disabled:hover:border-paper-line"
            disabled={step === 0}
            onClick={() => go(step - 1)}
          >
            Back
          </button>
          <button
            className="h-9 px-4 rounded-full bg-ink text-paper-card text-[13px] press shadow-lift transition-transform duration-300 hover:-translate-y-0.5"
            onClick={() => go(Math.min(STEPS.length - 1, step + 1))}
          >
            {step === STEPS.length - 1 ? "Done" : "Next"}
          </button>
        </div>
      </div>

      {/* Continuous progress rail under the discrete step ticks. */}
      <div className="relative h-1.5 rounded-full bg-paper-line/70 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-500 ease-out"
          style={{
            width: `${progress}%`,
            background: "linear-gradient(90deg, #6366F1, #0E9F7E, #B07D0C)",
          }}
        />
      </div>

      <div className="flex gap-1">
        {STEPS.map((s, i) => (
          <button
            key={s.id}
            onClick={() => go(i)}
            title={s.label}
            className={`flex-1 h-1.5 rounded-full transition-all duration-300 hover:scale-y-150 ${
              activeId === s.id || step === i ? "bg-ink" : "bg-paper-line hover:bg-ink/30"
            }`}
          />
        ))}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[12px] text-ink-400">
        {STEPS.map((s, i) => (
          <button
            key={s.id}
            onClick={() => go(i)}
            className={`press transition-colors duration-200 ${
              activeId === s.id || step === i ? "text-ink font-medium" : "hover:text-ink-600"
            }`}
          >
            <span className="tabular-nums opacity-50 mr-1">{s.n}</span>
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
