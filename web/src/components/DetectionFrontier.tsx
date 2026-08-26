import { useEffect, useMemo, useState } from "react";
import * as api from "../api";
import { Stat, bandColor } from "./ui";

type Cell = {
  n_bytes: number;
  n_planes: number;
  bit_offset: number;
  layout: string;
  entropy_matched: boolean;
  effective_bytes: number;
  risk_score: number;
  gate: string;
  detected: boolean;
  output_agreement_pct: number | null;
  loudest_detector: string | null;
  attestation_caught?: boolean;
};

const GATE_TONE: Record<string, string> = {
  APPROVE: bandColor.green,
  APPROVE_WITH_CAVEATS: bandColor.lime,
  REVIEW: bandColor.amber,
  QUARANTINE: bandColor.amber,
  HARD_BLOCK: bandColor.red,
};

function cellTone(c: Cell) {
  if (c.effective_bytes === 0) return { bg: "#EFEAE1", fg: "#8A8278", label: "no capacity" };
  if (c.detected) return { bg: `${bandColor.red}1f`, fg: bandColor.red, label: "blocked" };
  if (c.attestation_caught)
    return { bg: `${bandColor.amber}1f`, fg: bandColor.amber, label: "attestation only" };
  return { bg: `${bandColor.green}1f`, fg: bandColor.green, label: "evaded" };
}

function Legend() {
  const items = [
    { tone: bandColor.red, label: "Blocked by statistics" },
    { tone: bandColor.amber, label: "Missed by statistics, caught by attestation" },
    { tone: bandColor.green, label: "Uncaught" },
    { tone: "#8A8278", label: "No usable capacity" },
  ];
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1.5">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5 text-[11px] text-ink-600">
          <span
            className="w-2.5 h-2.5 rounded-sm"
            style={{ background: `${i.tone}2e`, border: `1px solid ${i.tone}66` }}
          />
          {i.label}
        </span>
      ))}
    </div>
  );
}

function Grid({
  rows, rowKey, colKey, rowLabel, colLabel, rowFmt, colFmt,
}: {
  rows: Cell[];
  rowKey: keyof Cell;
  colKey: keyof Cell;
  rowLabel: string;
  colLabel: string;
  rowFmt: (v: any) => string;
  colFmt: (v: any) => string;
}) {
  const rowVals = useMemo(
    () => Array.from(new Set(rows.map((r) => r[rowKey] as any))).sort((a, b) => a - b),
    [rows, rowKey]
  );
  const colVals = useMemo(
    () => Array.from(new Set(rows.map((r) => r[colKey] as any))).sort((a, b) => a - b),
    [rows, colKey]
  );

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: "3px" }}>
        <thead>
          <tr>
            <th className="text-[11px] text-ink-400 font-normal text-left pr-2 align-bottom">
              {rowLabel} ↓ / {colLabel} →
            </th>
            {colVals.map((c) => (
              <th key={String(c)} className="text-[11px] text-ink-600 font-normal px-1">
                {colFmt(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rowVals.map((rv) => (
            <tr key={String(rv)}>
              <td className="text-[11px] text-ink-600 pr-2 whitespace-nowrap">{rowFmt(rv)}</td>
              {colVals.map((cv) => {
                const cell = rows.find((r) => r[rowKey] === rv && r[colKey] === cv);
                if (!cell)
                  return <td key={String(cv)} className="w-20 h-12 rounded-lg bg-paper" />;
                const tone = cellTone(cell);
                return (
                  <td
                    key={String(cv)}
                    title={`${cell.gate} · risk ${cell.risk_score} · ${cell.effective_bytes} B placed · ${
                      cell.output_agreement_pct ?? "?"
                    }% agreement · loudest ${cell.loudest_detector ?? "none"}`}
                    className="w-20 h-12 rounded-lg align-middle text-center"
                    style={{ background: tone.bg, border: `1px solid ${tone.fg}44` }}
                  >
                    <div
                      className="text-[13px] font-medium tabular-nums leading-none"
                      style={{ color: tone.fg }}
                    >
                      {cell.risk_score}
                    </div>
                    <div className="text-[10px] mt-0.5" style={{ color: tone.fg, opacity: 0.75 }}>
                      {tone.label}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DetectionFrontier() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.getFrontier().then(setData).catch((e) => setErr(String(e?.message || e)));
  }, []);

  if (err) return <p className="text-[13px] text-ink-400">Frontier not generated yet.</p>;
  if (!data) return <p className="text-[13px] text-ink-400">Loading frontier…</p>;

  const s = data.summary;
  const depth: Cell[] = data.sweeps.depth_vs_size || [];
  const offset: Cell[] = data.sweeps.plane_offset || [];

  return (
    <div className="space-y-6">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        A ROC curve measures the detector on a corpus we chose. This measures it across the
        attacker's own parameter space — payload size, mantissa depth, where in the mantissa
        the payload sits, and whether the attacker matched our distribution. Every cell is a
        real embed and a real full-pipeline scan.
      </p>

      <div className="grid sm:grid-cols-4 gap-3">
        <Stat label="Configurations" value={s.configs_tested} sub={`${s.with_real_capacity} with usable capacity`} />
        <Stat
          label="Caught by statistics"
          value={`${s.detected_statistically}/${s.with_real_capacity}`}
          sub={`${(s.statistical_detection_rate * 100).toFixed(0)}% of viable attacks`}
        />
        <Stat
          label="Statistical blind spots"
          value={s.statistical_blind_spots}
          color={bandColor.amber}
          sub={`attestation caught ${s.blind_spots_caught_by_attestation}`}
        />
        <Stat
          label="Uncaught by any control"
          value={s.uncaught_by_any_control}
          color={s.uncaught_by_any_control === 0 ? bandColor.green : bandColor.red}
          sub={`combined coverage ${(s.combined_coverage_rate * 100).toFixed(0)}%`}
        />
      </div>

      <Legend />

      <div>
        <div className="text-[13px] text-ink font-medium mb-1">Depth against payload size</div>
        <p className="text-[12px] text-ink-600 mb-3">
          Inside the freed region there is nothing to hide behind: those planes are supposed
          to be exactly zero, so occupancy is a contract violation rather than a statistical
          outlier. Risk still climbs with depth and payload size, but even the smallest cell
          here — one plane, 512 bytes — is already over the block threshold.
        </p>
        <Grid
          rows={depth}
          rowKey="n_planes"
          colKey="n_bytes"
          rowLabel="planes"
          colLabel="payload"
          rowFmt={(v) => `${v} plane${v > 1 ? "s" : ""}`}
          colFmt={(v) => `${(v / 1024).toFixed(v >= 1024 ? 0 : 1)} KB`}
        />
      </div>

      <div>
        <div className="text-[13px] text-ink font-medium mb-1">The attacker's dilemma</div>
        <p className="text-[12px] text-ink-600 mb-3">
          Rows are where the payload starts in the mantissa. Below the precision floor at
          b11 we catch everything. Above it, payload bits and trained value bits are the
          same thing to any bit-level statistic — no threshold fixes that, which is why the
          attested baseline is a separate control rather than a nicety.
        </p>
        <Grid
          rows={offset}
          rowKey="bit_offset"
          colKey="entropy_matched"
          rowLabel="first plane"
          colLabel="matched"
          rowFmt={(v) => `b${v}${v >= 11 ? " (kept)" : " (freed)"}`}
          colFmt={(v) => (v ? "distribution matched" : "naive")}
        />
      </div>

      {data.blind_spots?.length > 0 && (
        <div>
          <div className="text-[13px] text-ink font-medium mb-2">Blind spots, named</div>
          <div className="space-y-1.5">
            {data.blind_spots.map((b: Cell, i: number) => (
              <div key={i} className="text-[12px] text-ink-600 flex flex-wrap gap-x-2">
                <span className="mono text-ink">
                  b{b.bit_offset}–b{b.bit_offset + b.n_planes - 1}
                </span>
                <span>{b.effective_bytes} B</span>
                <span>{b.layout}</span>
                <span>{b.entropy_matched ? "matched" : "naive"}</span>
                <span>{b.output_agreement_pct}% agreement</span>
                <span style={{ color: b.attestation_caught ? bandColor.green : bandColor.red }}>
                  {b.attestation_caught ? "attestation caught it" : "uncaught"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <ul className="text-[11px] text-ink-400 space-y-1 leading-snug">
        {data.notes.map((n: string, i: number) => (
          <li key={i}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
