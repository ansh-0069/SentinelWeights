import type { Finding } from "../types";

const DANGER_OPS = new Set(["REDUCE", "GLOBAL", "STACK_GLOBAL", "INST", "OBJ", "NEWOBJ"]);

export default function PickleOpcodeViewer({ detectors, findings }: { detectors: any; findings: Finding[] }) {
  const l1 = detectors?.l1_static || {};
  const trace: { op: string; arg: string; pos: number }[] = l1.opcode_trace || [];
  const globals: string[] = l1.globals || [];
  const dangerGlobals = new Set(
    findings.filter((f) => f.code?.startsWith("PICKLE_DANG")).map((f) => f.evidence?.callee)
  );

  if (!trace.length && !globals.length)
    return <p className="text-[13px] text-ink-400">No serialized-code surface (pure-data format).</p>;

  return (
    <div className="space-y-3">
      {globals.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {globals.map((g) => {
            const danger = dangerGlobals.has(g) || /os\.|subprocess|eval|exec|system|import/.test(g);
            return (
              <span
                key={g}
                className="text-[11px] px-2 py-0.5 rounded-full"
                style={{
                  background: danger ? "#F8E8E6" : "#F8EDE4",
                  color: danger ? "#B42318" : "#C2410C",
                }}
              >
                {g}
              </span>
            );
          })}
        </div>
      )}
      <div className="bg-ink rounded-xl p-3 max-h-64 overflow-auto">
        <table className="w-full text-[11px] font-mono">
          <tbody>
            {trace.slice(0, 120).map((t, i) => {
              const danger = t.op === "REDUCE" || /os|system|exec|eval|import|subprocess/.test(t.arg || "");
              const hl = DANGER_OPS.has(t.op);
              return (
                <tr key={i} className={danger ? "bg-white/5" : ""}>
                  <td className="text-white/30 pr-2 text-right w-10">{t.pos}</td>
                  <td className={`pr-2 ${hl ? "text-[#F4B4AE]" : "text-white/70"}`}>{t.op}</td>
                  <td className="text-white/50 truncate">{t.arg}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[13px] text-ink-600 leading-relaxed">
        Static <span className="font-mono text-[12px]">pickletools.genops</span> — the file is never deserialized.
        REDUCE onto a dangerous callable is the execution path.
      </p>
    </div>
  );
}
