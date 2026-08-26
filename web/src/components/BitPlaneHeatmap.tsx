function entropyColor(v: number) {
  const r = Math.round(232 - v * 52);
  const g = Math.round(224 - v * 189);
  const b = Math.round(214 - v * 190);
  return `rgb(${r},${g},${b})`;
}

export default function BitPlaneHeatmap({ detectors }: { detectors: any }) {
  const rows: { tensor: string; cells: number[] }[] = detectors?.l2_window?.heatmap || [];
  if (!rows.length)
    return <p className="text-[13px] text-ink-400">No tensor heatmap (weights not loaded / not applicable).</p>;

  return (
    <div className="space-y-2">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        Local low-mantissa-bit entropy across each tensor (left→right = position). A rust band is a
        contiguous high-entropy region — a payload fingerprint.
      </p>
      <div className="space-y-1.5 max-h-72 overflow-auto pr-1">
        {rows.map((r) => (
          <div key={r.tensor} className="flex items-center gap-2">
            <div className="w-28 shrink-0 text-[11px] font-mono text-ink-400 truncate" title={r.tensor}>
              {r.tensor}
            </div>
            <div className="flex-1 flex gap-[1px] h-4">
              {r.cells.map((c, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-[1px]"
                  style={{ background: entropyColor(c) }}
                  title={`entropy ${c.toFixed(3)}`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 text-[11px] text-ink-400">
        <span>low entropy</span>
        <div className="flex-1 h-1.5 rounded-full" style={{
          background: `linear-gradient(90deg, ${entropyColor(0)}, ${entropyColor(0.5)}, ${entropyColor(1)})`,
        }} />
        <span>maximal (payload-like)</span>
      </div>
    </div>
  );
}
