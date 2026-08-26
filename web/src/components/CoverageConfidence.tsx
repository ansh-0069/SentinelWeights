import type { Coverage } from "../types";
import { Pill } from "./ui";

const STATE_COLOR: Record<string, string> = {
  Executed: "#0E9F7E",
  "Executed (synthetic model)": "#0E9F7E",
  "Not applicable": "#8A8278",
  Unsupported: "#8A8278",
  "Skipped (missing input)": "#C2410C",
  "Failed-safe": "#C2410C",
};

const SEGMENTS = 12;

export default function CoverageConfidence({ coverage }: { coverage: Coverage }) {
  const conf = coverage.confidence_pct;
  const confColor = conf >= 80 ? "#0E9F7E" : conf >= 50 ? "#C2410C" : "#B42318";
  const on = Math.round((conf / 100) * SEGMENTS);

  return (
    <div className="space-y-3">
      <div>
        <div className="flex justify-between text-[12px] mb-2">
          <span className="text-ink-400">Coverage</span>
          <span className="tabular-nums font-medium" style={{ color: confColor }}>
            {conf}%
          </span>
        </div>

        {/* Discrete blocks read faster than a continuous bar at a glance. */}
        <div className="flex gap-1">
          {Array.from({ length: SEGMENTS }).map((_, i) => (
            <div
              key={i}
              className="flex-1 h-2.5 rounded-[3px] transition-colors duration-500"
              style={{
                background: i < on ? confColor : "#EBE5DB",
                opacity: i < on ? 0.55 + (i / SEGMENTS) * 0.45 : 1,
                animation: `scale-in 0.4s cubic-bezier(0.22,1,0.36,1) ${i * 40}ms both`,
              }}
            />
          ))}
        </div>

        <div className="text-[11px] text-ink-400 mt-1.5">
          {coverage.executed}/{coverage.applicable} applicable detectors ran
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {coverage.badges.map((b, i) => (
          <div
            key={b.detector}
            title={`${b.label}: ${b.state}`}
            style={{ animationDelay: `${i * 35}ms` }}
            className="animate-scale-in"
          >
            <Pill color={STATE_COLOR[b.state] || "#8A8278"}>{b.label.split(" ")[0]}</Pill>
          </div>
        ))}
      </div>
    </div>
  );
}
