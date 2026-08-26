import { useEffect, useState } from "react";
import { bandColor } from "./ui";

const BANDS = [
  { max: 20, label: "Clean" },
  { max: 50, label: "Low concern" },
  { max: 80, label: "Suspicious" },
  { max: 100, label: "Dangerous" },
];

export default function RiskGauge({ score, color }: { score: number; color: string }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let raf: number;
    const start = performance.now();
    const from = display;
    const dur = 900;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(from + (score - from) * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [score]);

  const c = bandColor[color] || "#0E9F7E";
  const radius = 54;
  const circ = 2 * Math.PI * radius;
  const frac = display / 100;
  const dash = circ * frac;
  const band = BANDS.find((b) => score <= b.max)?.label ?? "Dangerous";

  // Tick marks around the dial give the gauge an instrument feel.
  const ticks = Array.from({ length: 40 }, (_, i) => i);

  return (
    <div className="flex items-center gap-5">
      <div className="relative shrink-0">
        <div
          className="absolute inset-3 rounded-full blur-2xl opacity-30 animate-float"
          style={{ background: c }}
        />
        <svg width="136" height="136" viewBox="0 0 136 136" className="relative">
          <defs>
            <linearGradient id="riskArc" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor={c} stopOpacity="0.55" />
              <stop offset="100%" stopColor={c} />
            </linearGradient>
          </defs>

          {ticks.map((i) => {
            const a = (i / ticks.length) * Math.PI * 2 - Math.PI / 2;
            const lit = i / ticks.length <= frac;
            const r1 = 64;
            const r2 = lit ? 59 : 61;
            return (
              <line
                key={i}
                x1={68 + Math.cos(a) * r1}
                y1={68 + Math.sin(a) * r1}
                x2={68 + Math.cos(a) * r2}
                y2={68 + Math.sin(a) * r2}
                stroke={lit ? c : "#E6E0D6"}
                strokeWidth="1.5"
                strokeLinecap="round"
                opacity={lit ? 0.75 : 1}
              />
            );
          })}

          <circle cx="68" cy="68" r={radius} fill="none" stroke="#EFEAE1" strokeWidth="9" />
          <circle
            cx="68"
            cy="68"
            r={radius}
            fill="none"
            stroke="url(#riskArc)"
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
            transform="rotate(-90 68 68)"
          />
        </svg>
      </div>

      <div>
        <div
          className="display text-[58px] leading-none tracking-tight tabular-nums"
          style={{ color: c }}
        >
          {display.toFixed(0)}
        </div>
        <div className="text-[12px] text-ink-400 mt-1.5">Model risk · 0–100</div>
        <div
          className="inline-flex items-center gap-1.5 mt-2 px-2 py-0.5 rounded-full text-[11px]"
          style={{ background: `${c}14`, color: c, border: `1px solid ${c}30` }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: c }} />
          {band}
        </div>
      </div>
    </div>
  );
}
