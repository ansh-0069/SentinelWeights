export default function EvidenceTimeline({ timeline }: { timeline: { step: string; elapsed_ms: number }[] }) {
  if (!timeline?.length) return null;
  return (
    <div className="flex items-stretch overflow-x-auto pb-2">
      {timeline.map((t, i) => (
        <div key={i} className="flex items-center">
          <div className="flex flex-col items-center min-w-[110px]">
            <div className="w-7 h-7 rounded-full bg-paper border border-paper-line flex items-center justify-center text-[12px] text-ink">
              {i + 1}
            </div>
            <div className="text-[11px] text-ink mt-1 text-center leading-tight">{t.step}</div>
            <div className="text-[11px] tabular-nums text-ink-400">{t.elapsed_ms} ms</div>
          </div>
          {i < timeline.length - 1 && <div className="w-8 h-px bg-paper-line -mt-6" />}
        </div>
      ))}
    </div>
  );
}
