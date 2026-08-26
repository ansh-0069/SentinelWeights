import { useRef } from "react";
import type { SampleItem } from "../types";
import { bandColor } from "./ui";

export default function SampleGallery({
  samples,
  activeId,
  methodology,
  onSelect,
  onUpload,
  compact = false,
}: {
  samples: SampleItem[];
  activeId?: string;
  methodology?: string;
  onSelect: (s: SampleItem) => void;
  onUpload: (f: File) => void;
  compact?: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-3">
      {!compact && methodology && (
        <p className="text-[12px] leading-relaxed text-ink-600">{methodology}</p>
      )}

      <div className={compact ? "space-y-1" : "space-y-1.5"}>
        {samples.map((s, i) => {
          const v = s.expected_verdict;
          const c = v ? bandColor[v.color] : "#8A8278";
          const active = s.id === activeId;
          return (
            <button
              key={s.id}
              onClick={() => onSelect(s)}
              style={{ animationDelay: `${Math.min(i, 12) * 30}ms` }}
              className={`group relative w-full text-left rounded-xl px-3 py-2.5 animate-fade-in press transition-all duration-300 ${
                compact
                  ? active
                    ? "bg-white text-ink shadow-lift"
                    : "bg-white/[0.04] text-white/75 hover:bg-white/[0.12] hover:text-white hover:translate-x-0.5"
                  : active
                    ? "bg-paper-card border border-paper-line text-ink shadow-lift"
                    : "bg-transparent border border-transparent text-ink hover:bg-paper-card hover:-translate-y-0.5"
              }`}
            >
              {/* Gate colour bead — the fastest read of what a sample will do. */}
              <span
                className={`absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-r-full transition-all duration-300 ${
                  active ? "h-7 opacity-100" : "h-3 opacity-45 group-hover:h-5 group-hover:opacity-80"
                }`}
                style={{ background: c }}
              />

              <div className="flex items-center justify-between gap-2 pl-1.5">
                <span className="text-[12.5px] leading-tight truncate">{s.label}</span>
                {v && (
                  <span
                    className="text-[9.5px] tabular-nums tracking-wide uppercase shrink-0 px-1.5 py-0.5 rounded-full transition-colors"
                    style={{
                      color: compact && !active ? "#C4BDB3" : c,
                      background: active ? `${c}14` : "transparent",
                    }}
                  >
                    {v.gate.replace(/_/g, " ")}
                  </span>
                )}
              </div>

              {!compact && (
                <div className="flex items-center justify-between mt-1 pl-1.5 text-[11px] text-ink-400">
                  <span>{s.format}</span>
                  <span>{(s.size / 1024).toFixed(0)} KB</span>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (e.dataTransfer.files[0]) onUpload(e.dataTransfer.files[0]);
        }}
        onClick={() => fileRef.current?.click()}
        className={`w-full rounded-xl border border-dashed px-3 py-3 text-[12px] text-left press transition-all duration-300 ${
          compact
            ? "border-white/20 text-white/50 hover:border-white/45 hover:text-white/85 hover:bg-white/5"
            : "border-paper-line text-ink-400 hover:border-ink/30 hover:text-ink hover:bg-paper-card"
        }`}
      >
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          accept=".safetensors,.pt,.pth,.bin,.npz,.npy,.pkl,.onnx"
          onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
        />
        <span className="flex items-center gap-2">
          <svg
            viewBox="0 0 24 24"
            className="w-3.5 h-3.5 shrink-0"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 16V4M12 4L7 9M12 4l5 5M4 17v2a1 1 0 001 1h14a1 1 0 001-1v-2" />
          </svg>
          Drop a model, or browse
        </span>
      </button>
    </div>
  );
}
