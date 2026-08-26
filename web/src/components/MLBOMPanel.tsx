import { useState } from "react";
import type { Report } from "../types";
import { verifyReport, reportPdfUrl } from "../api";

export default function MLBOMPanel({ report, scanId }: { report: Report; scanId: string }) {
  const [verify, setVerify] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const bom = report.mlbom;
  const sig = report.signature;

  async function doVerify() {
    setBusy(true);
    try {
      setVerify(await verifyReport(scanId));
    } finally {
      setBusy(false);
    }
  }

  const rows: [string, any][] = [
    ["Format", bom.format],
    ["Filename", bom.filename],
    ["Tensors", bom.num_tensors],
    ["Total params", bom.total_params?.toLocaleString?.() ?? bom.total_params],
    ["Weights loadable", String(bom.weights_loadable)],
    ["Policy version", bom.policy_version],
    ["License", bom.license],
  ];

  return (
    <div className="space-y-3">
      <div className="grid sm:grid-cols-2 gap-x-4 gap-y-1">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between text-[12px] border-b border-paper-line py-1">
            <span className="text-ink-400">{k}</span>
            <span className="tabular-nums text-ink truncate max-w-[60%] text-right">{v}</span>
          </div>
        ))}
      </div>
      <div className="text-[11px] text-ink-400 break-all">sha256: {bom.sha256}</div>

      {sig && (
        <div className="rounded-xl border border-paper-line bg-paper p-3 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[12px] text-forest">Attestation</span>
            <span className="text-[11px] text-ink-400">{sig.algo} · {sig.key_id}</span>
          </div>
          <p className="text-[12px] text-ink-400">{sig.disclaimer}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <a
          href={reportPdfUrl(scanId)}
          target="_blank"
          rel="noreferrer"
          className="px-3 py-1.5 rounded-full bg-ink text-paper-card text-[12px]"
        >
          Export signed PDF
        </a>
        <button
          onClick={doVerify}
          disabled={busy}
          className="px-3 py-1.5 rounded-full border border-paper-line text-[12px] text-ink disabled:opacity-50"
        >
          {busy ? "Verifying…" : "Verify report"}
        </button>
        {verify && (
          <span
            className="px-3 py-1.5 rounded-full text-[12px]"
            style={{ color: verify.valid ? "#1F6F5B" : "#B42318", background: verify.valid ? "#E7F2EE" : "#F8E8E6" }}
          >
            {verify.valid ? "Valid" : "Invalid"} — {verify.message}
          </span>
        )}
      </div>

      {report.atlas_mapping?.length > 0 && (
        <div>
          <div className="text-[11px] text-ink-400 mb-1">MITRE ATLAS</div>
          <div className="flex flex-wrap gap-1.5">
            {report.atlas_mapping.map((a) => (
              <span key={a.technique} className="text-[11px] px-2 py-0.5 rounded-full bg-paper border border-paper-line text-ink"
                title={a.note}>
                {a.technique} · {a.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
