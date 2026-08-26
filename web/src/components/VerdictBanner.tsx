import type { Verdict } from "../types";
import { bandColor } from "./ui";

export default function VerdictBanner({ verdict }: { verdict: Verdict }) {
  const c = bandColor[verdict.color] || "#0E9F7E";
  return (
    <div
      className="relative rounded-2xl px-5 py-4 overflow-hidden animate-scale-in"
      style={{
        background: `linear-gradient(150deg, ${c}14 0%, ${c}05 46%, rgba(255,252,248,0.9) 100%)`,
        border: `1px solid ${c}2E`,
      }}
    >
      {/* Slow specular sweep so the verdict reads as a live surface, not a flat box. */}
      <span
        className="absolute inset-y-0 -left-1/3 w-1/3 pointer-events-none animate-shimmer"
        style={{
          background: `linear-gradient(100deg, transparent, ${c}1F, transparent)`,
          transform: "skewX(-18deg)",
        }}
      />
      <div className="relative flex items-baseline gap-3 flex-wrap">
        <span className="display text-[30px] leading-none tracking-tight" style={{ color: c }}>
          {verdict.gate.replace(/_/g, " ")}
        </span>
        <span className="text-[12px] text-ink-400 tracking-wide uppercase">
          {verdict.band.replace(/_/g, " ")}
        </span>
        {verdict.override && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-rust-dim text-rust border border-rust/20">
            Override {verdict.override}
          </span>
        )}
        <span className="ml-auto text-[11px] tabular-nums text-ink-400">
          score {verdict.risk_score}
        </span>
      </div>
      <p className="relative text-[14px] text-ink mt-2.5 leading-relaxed">{verdict.language}</p>
      <p className="relative text-[12px] text-ink-400 mt-2">
        No indicators within scan scope — never “proven clean.”
      </p>
    </div>
  );
}
