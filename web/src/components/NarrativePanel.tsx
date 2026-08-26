/** Plain-language narratives grounded in detector evidence. */
export default function NarrativePanel({ narratives }: { narratives: any[] }) {
  if (!narratives?.length) return null;
  const color: Record<string, string> = {
    CRITICAL: "#B42318",
    HIGH: "#C2410C",
    MEDIUM: "#C2410C",
    INFO: "#5C564E",
  };
  return (
    <div className="space-y-2">
      {narratives.map((n, i) => (
        <div
          key={i}
          className="rounded-xl border border-paper-line bg-paper p-4"
        >
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ color: color[n.severity], background: `${color[n.severity]}14` }}>
              {n.severity}
            </span>
            <span className="text-[13px] text-ink">{n.title}</span>
          </div>
          <p className="text-[13px] text-ink-600 leading-relaxed">{n.body}</p>
        </div>
      ))}
    </div>
  );
}
