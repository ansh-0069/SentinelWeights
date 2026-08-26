import React from "react";

export const bandColor: Record<string, string> = {
  green: "#0E9F7E",
  lime: "#7A9A1F",
  amber: "#C2410C",
  red: "#B42318",
};

export const sevColor: Record<string, string> = {
  CRITICAL: "#B42318",
  HIGH: "#C2410C",
  MEDIUM: "#C2410C",
  REVIEW: "#C2410C",
  LOW: "#7A9A1F",
};

export type Tone = "plain" | "lavender" | "mint" | "sky" | "blush" | "butter" | "dark";

/** RGB triples feed the `--tint` custom property that the tinted CSS classes read. */
export const TONE_RGB: Record<Exclude<Tone, "plain" | "dark">, string> = {
  lavender: "99, 102, 241",
  mint: "14, 159, 126",
  sky: "46, 125, 209",
  blush: "217, 79, 112",
  butter: "176, 125, 12",
};

export const TONE_HEX: Record<Exclude<Tone, "plain" | "dark">, string> = {
  lavender: "#6366F1",
  mint: "#0E9F7E",
  sky: "#2E7DD1",
  blush: "#D94F70",
  butter: "#B07D0C",
};

/** Maps a verdict band colour onto a pastel tone so panels stay colour-coded. */
export function toneForBand(color?: string): Tone {
  switch (color) {
    case "green":
      return "mint";
    case "lime":
      return "butter";
    case "amber":
      return "blush";
    case "red":
      return "blush";
    default:
      return "lavender";
  }
}

export function tintStyle(tone: Tone): React.CSSProperties {
  if (tone === "plain" || tone === "dark") return {};
  return { ["--tint" as any]: TONE_RGB[tone] };
}

export function Section({
  id,
  title,
  subtitle,
  right,
  children,
  className = "",
  tone = "plain",
  icon,
  delay = 0,
}: {
  id?: string;
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  tone?: Tone;
  icon?: React.ReactNode;
  delay?: number;
}) {
  const tinted = tone !== "plain" && tone !== "dark";
  return (
    <section
      id={id}
      style={{ ...tintStyle(tone), animationDelay: `${delay}ms` }}
      className={`card reveal p-5 ${tinted ? "card-tint" : ""} ${
        tone === "dark" ? "card-dark" : ""
      } ${className}`}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-start gap-3 min-w-0">
          {icon && (
            <span
              className="shrink-0 w-9 h-9 rounded-xl grid place-items-center tint-chip"
              style={tinted ? undefined : { ["--tint" as any]: "99, 102, 241" }}
            >
              {icon}
            </span>
          )}
          <div className="min-w-0">
            <h3
              className={`text-[15px] font-medium tracking-tight ${
                tone === "dark" ? "text-paper-card" : "text-ink"
              }`}
            >
              {title}
            </h3>
            {subtitle && (
              <p
                className={`text-[13px] mt-0.5 leading-snug ${
                  tone === "dark" ? "text-white/55" : "text-ink-600"
                }`}
              >
                {subtitle}
              </p>
            )}
          </div>
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

export function Pill({
  children,
  color = "#0E9F7E",
  filled = false,
  pulse = false,
}: {
  children: React.ReactNode;
  color?: string;
  filled?: boolean;
  pulse?: boolean;
}) {
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium transition-colors"
      style={
        filled
          ? { background: color, color: "#FFFcf8" }
          : { border: `1px solid ${color}33`, color, background: `${color}12` }
      }
    >
      {pulse && (
        <span className="relative flex w-1.5 h-1.5">
          <span
            className="absolute inline-flex w-full h-full rounded-full animate-pulse-ring"
            style={{ background: color }}
          />
          <span className="relative inline-flex w-1.5 h-1.5 rounded-full" style={{ background: color }} />
        </span>
      )}
      {children}
    </span>
  );
}

export function Stat({
  label,
  value,
  sub,
  color,
  tone = "plain",
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  color?: string;
  tone?: Tone;
}) {
  const tinted = tone !== "plain" && tone !== "dark";
  return (
    <div
      style={tintStyle(tone)}
      className={`rounded-xl px-3 py-2.5 border transition-transform duration-300 hover:-translate-y-0.5 ${
        tinted
          ? "card-tint border-transparent"
          : "bg-paper border-paper-line"
      }`}
    >
      <div className="text-[11px] text-ink-400">{label}</div>
      <div
        className="text-lg font-medium tracking-tight tabular-nums"
        style={{ color: color || (tinted ? TONE_HEX[tone as keyof typeof TONE_HEX] : "#14110F") }}
      >
        {value}
      </div>
      {sub && <div className="text-[11px] text-ink-400 mt-0.5">{sub}</div>}
    </div>
  );
}

/**
 * Headline metric with a segmented capacity meter — the visual language of the
 * reference dashboards, where a big number sits above discrete filled blocks.
 */
export function MetricCard({
  label,
  value,
  unit,
  filled,
  segments = 8,
  badge,
  tone = "lavender",
  icon,
  delay = 0,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  filled: number;
  segments?: number;
  badge?: string;
  tone?: Exclude<Tone, "plain" | "dark">;
  icon?: React.ReactNode;
  delay?: number;
}) {
  const on = Math.max(0, Math.min(segments, Math.round(filled * segments)));
  return (
    <div
      style={{ ...tintStyle(tone), animationDelay: `${delay}ms` }}
      className="card card-tint shine reveal p-5"
    >
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          {icon && (
            <span className="w-8 h-8 rounded-lg grid place-items-center tint-chip shrink-0">{icon}</span>
          )}
          <span className="text-[14px] font-medium text-ink truncate">{label}</span>
        </div>
        {badge && (
          <span className="text-[10.5px] px-2 py-1 rounded-full bg-ink text-paper-card shrink-0 tabular-nums">
            {badge}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-1.5 mb-3.5">
        <span className="display text-[42px] leading-none tracking-tight text-ink tabular-nums">
          {value}
        </span>
        {unit && <span className="text-[13px] text-ink-400">{unit}</span>}
      </div>
      <div className="flex gap-1.5">
        {Array.from({ length: segments }).map((_, i) => (
          <div
            key={i}
            className={`flex-1 seg ${i < on ? "seg-on" : ""}`}
            style={{
              animation: `scale-in 0.45s cubic-bezier(0.22,1,0.36,1) ${delay + i * 55}ms both`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

/** Compact inline SVG glyph set — avoids pulling in an icon dependency. */
export function Icon({ name, className = "w-4 h-4" }: { name: string; className?: string }) {
  const common = {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 3l7 3v6c0 4.4-3 7.9-7 9-4-1.1-7-4.6-7-9V6l7-3z" />
        </svg>
      );
    case "scan":
      return (
        <svg {...common}>
          <path d="M4 8V5a1 1 0 011-1h3M20 8V5a1 1 0 00-1-1h-3M4 16v3a1 1 0 001 1h3M20 16v3a1 1 0 01-1 1h-3M3 12h18" />
        </svg>
      );
    case "layers":
      return (
        <svg {...common}>
          <path d="M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17l9 5 9-5" />
        </svg>
      );
    case "target":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <circle cx="12" cy="12" r="4" />
          <circle cx="12" cy="12" r="1" />
        </svg>
      );
    case "lock":
      return (
        <svg {...common}>
          <rect x="4" y="10" width="16" height="10" rx="2" />
          <path d="M8 10V7a4 4 0 118 0v3" />
        </svg>
      );
    case "chart":
      return (
        <svg {...common}>
          <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
        </svg>
      );
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v4l3 2" />
        </svg>
      );
    case "flask":
      return (
        <svg {...common}>
          <path d="M10 3h4M11 3v6L5 19a2 2 0 001.7 3h10.6A2 2 0 0019 19l-6-10V3" />
        </svg>
      );
    case "book":
      return (
        <svg {...common}>
          <path d="M4 5a2 2 0 012-2h13v18H6a2 2 0 01-2-2V5zM19 17H6" />
        </svg>
      );
    case "spark":
      return (
        <svg {...common}>
          <path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4L12 3z" />
        </svg>
      );
    case "alert":
      return (
        <svg {...common}>
          <path d="M12 4l9 16H3l9-16zM12 10v4M12 17h.01" />
        </svg>
      );
    case "file":
      return (
        <svg {...common}>
          <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5zM14 3v5h5" />
        </svg>
      );
    case "network":
      return (
        <svg {...common}>
          <circle cx="12" cy="5" r="2.5" />
          <circle cx="5" cy="19" r="2.5" />
          <circle cx="19" cy="19" r="2.5" />
          <path d="M12 7.5v4M12 11.5L6.5 17M12 11.5L17.5 17" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
        </svg>
      );
  }
}
