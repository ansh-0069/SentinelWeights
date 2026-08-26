import { Pill } from "./ui";

export interface StageState {
  status: string;
  elapsed_ms?: number;
  summary?: string;
}

const TIERS = [
  { key: "tier0", label: "00", name: "Ingest", tint: "99, 102, 241" },
  { key: "tier1", label: "01", name: "Static", tint: "46, 125, 209" },
  { key: "tier2", label: "02", name: "Weights", tint: "14, 159, 126" },
  { key: "tier3", label: "03", name: "Behavior", tint: "176, 125, 12" },
  { key: "tier4", label: "04", name: "Policy", tint: "217, 79, 112" },
];

function statusStyle(s: string) {
  switch (s) {
    case "running":
      return { color: "#6366F1", label: "Running" };
    case "done":
      return { color: "#0E9F7E", label: "Done" };
    case "cache_hit":
      return { color: "#0E9F7E", label: "Cached" };
    case "critical":
      return { color: "#B42318", label: "Stop" };
    case "na":
      return { color: "#8A8278", label: "Skipped" };
    default:
      return { color: "#8A8278", label: "Idle" };
  }
}

export default function PipelineFunnel({ stages }: { stages: Record<string, StageState> }) {
  return (
    <div className="relative">
      {/* Connector rail behind the tier cards. */}
      <div className="absolute left-[6%] right-[6%] top-1/2 h-px bg-paper-line hidden md:block" />

      <div className="relative grid grid-cols-2 md:grid-cols-5 gap-2.5">
        {TIERS.map((t, i) => {
          const st = stages[t.key] || { status: "idle" };
          const s = statusStyle(st.status);
          const active = st.status === "running";
          const hot =
            st.status === "running" ||
            st.status === "done" ||
            st.status === "critical" ||
            st.status === "cache_hit";

          return (
            <div
              key={t.key}
              style={{
                ["--tint" as any]: t.tint,
                animationDelay: `${i * 70}ms`,
              }}
              className={`relative rounded-xl px-3 py-3 min-h-[98px] flex flex-col justify-between animate-fade-up transition-all duration-500 ${
                hot
                  ? "card-tint border border-transparent shadow-lift -translate-y-0.5"
                  : "border border-paper-line bg-paper"
              }`}
            >
              {active && (
                <span
                  className="absolute inset-0 rounded-xl border-2 pointer-events-none animate-blink"
                  style={{ borderColor: `${s.color}55` }}
                />
              )}

              <div className="flex items-center justify-between">
                <span className="text-[11px] tabular-nums text-ink-400 tracking-widest">{t.label}</span>
                <span className="relative flex w-2 h-2">
                  {active && (
                    <span
                      className="absolute inline-flex w-full h-full rounded-full animate-pulse-ring"
                      style={{ background: s.color }}
                    />
                  )}
                  <span
                    className="relative inline-flex w-2 h-2 rounded-full transition-colors duration-500"
                    style={{ background: hot ? s.color : "#D9D2C6" }}
                  />
                </span>
              </div>

              <div className="text-[13.5px] text-ink font-medium">{t.name}</div>

              <div className="flex items-center justify-between gap-1">
                <Pill color={s.color}>{s.label}</Pill>
                <span className="text-[11px] tabular-nums text-ink-400">
                  {st.elapsed_ms != null ? `${st.elapsed_ms} ms` : ""}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
