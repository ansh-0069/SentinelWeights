import { useEffect, useMemo, useState } from "react";
import type { AttackConfig } from "./AdversaryLab";
import { getFrontier } from "../api";

type Cell = {
  n_bytes: number; n_planes: number; bit_offset: number; match_distribution: boolean;
  layout: "contiguous" | "scattered" | "per_channel"; spread_tensors?: number;
  payload_kind: "random" | "compressed"; gate: string; risk: number;
  effective_bytes: number; output_agreement: number | null; loudest_detector: string;
  detected_by_statistics: boolean; detected_by_attestation: boolean; capacity_limited: boolean;
};
type Frontier = {
  summary: { total_configurations: number; viable_configurations: number; statistics_caught: number;
    statistical_blind_spots: number; blind_spots_caught_by_attestation: number; escaped_all_controls: number };
  sweeps: { depth_size: Cell[]; offset_matching: Cell[]; layout: Cell[]; payload_kind: Cell[] };
};

function normalizeCell(raw: any): Cell {
  return {
    n_bytes: Number(raw.n_bytes ?? 0),
    n_planes: Number(raw.n_planes ?? 0),
    bit_offset: Number(raw.bit_offset ?? 0),
    match_distribution: Boolean(raw.match_distribution ?? raw.entropy_matched),
    layout: raw.layout ?? "contiguous",
    spread_tensors: raw.spread_tensors,
    payload_kind: raw.payload_kind ?? "random",
    gate: raw.gate ?? "APPROVE",
    risk: Number(raw.risk ?? raw.risk_score ?? 0),
    effective_bytes: Number(raw.effective_bytes ?? 0),
    output_agreement: raw.output_agreement != null ? Number(raw.output_agreement)
      : raw.output_agreement_pct != null ? Number(raw.output_agreement_pct) / 100 : null,
    loudest_detector: raw.loudest_detector ?? "",
    detected_by_statistics: Boolean(raw.detected_by_statistics ?? raw.detected),
    detected_by_attestation: Boolean(raw.detected_by_attestation ?? raw.attestation_caught),
    capacity_limited: Boolean(raw.capacity_limited ?? Number(raw.effective_bytes ?? 0) < Number(raw.n_bytes ?? 0)),
  };
}

function normalizeFrontier(raw: any): Frontier {
  const summary = raw.summary ?? {};
  return {
    summary: {
      total_configurations: Number(summary.total_configurations ?? summary.configs_tested ?? 0),
      viable_configurations: Number(summary.viable_configurations ?? summary.with_real_capacity ?? 0),
      statistics_caught: Number(summary.statistics_caught ?? summary.detected_statistically ?? 0),
      statistical_blind_spots: Number(summary.statistical_blind_spots ?? 0),
      blind_spots_caught_by_attestation: Number(summary.blind_spots_caught_by_attestation ?? 0),
      escaped_all_controls: Number(summary.escaped_all_controls ?? summary.uncaught_by_any_control ?? 0),
    },
    sweeps: {
      depth_size: (raw.sweeps?.depth_size ?? raw.sweeps?.depth_vs_size ?? []).map(normalizeCell),
      offset_matching: (raw.sweeps?.offset_matching ?? raw.sweeps?.plane_offset ?? []).map(normalizeCell),
      layout: (raw.sweeps?.layout ?? []).map(normalizeCell),
      payload_kind: (raw.sweeps?.payload_kind ?? []).map(normalizeCell),
    },
  };
}

const gateClass = (cell: Cell) => cell.capacity_limited && cell.effective_bytes === 0 ? "frontier-cell no-capacity"
  : cell.detected_by_statistics ? "frontier-cell caught"
  : cell.detected_by_attestation ? "frontier-cell attested" : "frontier-cell escaped";
const gateLabel = (cell: Cell) => cell.capacity_limited && cell.effective_bytes === 0 ? "no capacity"
  : cell.detected_by_statistics ? "statistics" : cell.detected_by_attestation ? "attestation" : "uncaught";
const layoutName = (layout: Cell["layout"]) => ({ contiguous: "Contiguous", scattered: "Scattered", per_channel: "Per channel" })[layout];

function attackDistance(cell: Cell, attack: AttackConfig) {
  return Math.abs(cell.n_bytes - attack.n_bytes) / 8192 + Math.abs(cell.n_planes - attack.n_planes) / 12
    + Math.abs(cell.bit_offset - attack.bit_offset) / 22
    + (cell.match_distribution === attack.entropy_matched ? 0 : 1)
    + (cell.layout === attack.layout ? 0 : 1) + (cell.payload_kind === attack.payload_kind ? 0 : 0.25);
}

function FrontierButton({ cell, selected, closest, onSelect, compact = false }: {
  cell: Cell; selected: boolean; closest: boolean; onSelect: (cell: Cell) => void; compact?: boolean;
}) {
  return <button type="button"
    className={`${gateClass(cell)}${selected ? " selected" : ""}${closest ? " current" : ""}${compact ? " compact" : ""}`}
    onClick={() => onSelect(cell)} aria-pressed={selected} title="Open configuration details">
    <strong>{cell.capacity_limited && cell.effective_bytes === 0 ? "—" : cell.risk.toFixed(1)}</strong>
    <span>{gateLabel(cell)}</span>{closest && <em>Nearest test</em>}
  </button>;
}

function Matrix({ cells, rows, cols, rowKey, colKey, rowLabel, colLabel, selected, closest, onSelect }: {
  cells: Cell[]; rows: number[]; cols: Array<number | boolean>; rowKey: keyof Cell; colKey: keyof Cell;
  rowLabel: (value: number) => string; colLabel: (value: number | boolean) => string;
  selected: Cell | null; closest: Cell | null; onSelect: (cell: Cell) => void;
}) {
  const find = (row: number, col: number | boolean) => cells.find((cell) => cell[rowKey] === row && cell[colKey] === col);
  return <div className="frontier-grid-wrap"><table className="frontier-grid">
    <thead><tr><th>planes ↓ / setting →</th>{cols.map((col) => <th key={String(col)}>{colLabel(col)}</th>)}</tr></thead>
    <tbody>{rows.map((row) => <tr key={row}><th>{rowLabel(row)}</th>{cols.map((col) => {
      const cell = find(row, col);
      return <td key={String(col)}>{cell ? <FrontierButton cell={cell} selected={selected === cell}
        closest={closest === cell} onSelect={onSelect} /> : <span className="frontier-empty">—</span>}</td>;
    })}</tr>)}</tbody>
  </table></div>;
}

function DetailPanel({ cell, isClosest }: { cell: Cell; isClosest: boolean }) {
  return <aside className="frontier-detail" aria-live="polite">
    <div className="frontier-detail-head"><div><p className="eyebrow">{isClosest ? "Nearest measured configuration" : "Selected configuration"}</p>
      <h4>{cell.n_planes} plane{cell.n_planes === 1 ? "" : "s"} · {(cell.n_bytes / 1024).toFixed(cell.n_bytes < 1024 ? 1 : 0)} KB requested</h4></div>
      <span className={`mini-gate ${cell.gate.toLowerCase().replace(/_/g, "-")}`}>{cell.gate.replace(/_/g, " ")}</span></div>
    <div className="detail-facts">
      <div><span>Placement</span><strong>b{cell.bit_offset}–b{cell.bit_offset + cell.n_planes - 1}</strong></div>
      <div><span>Layout</span><strong>{layoutName(cell.layout)}</strong></div>
      <div><span>Distribution</span><strong>{cell.match_distribution ? "Matched" : "Naive"}</strong></div>
      <div><span>Payload bytes</span><strong>{cell.payload_kind === "compressed" ? "Compressed" : "Random"}</strong></div>
      <div><span>Actually embedded</span><strong>{cell.effective_bytes.toLocaleString()} B</strong></div>
      <div><span>Risk / 100</span><strong>{cell.risk.toFixed(1)}</strong></div>
      <div><span>Numerical probe</span><strong>{cell.output_agreement == null ? "Not measured" : `${(cell.output_agreement * 100).toFixed(1)}% agreement`}</strong></div>
      <div><span>Strongest detector</span><strong>{cell.loudest_detector || "None"}</strong></div>
    </div>
    <p className="detail-conclusion">{cell.detected_by_statistics
      ? "The statistical detector blocked this configuration without needing the trusted baseline."
      : cell.detected_by_attestation ? "Statistics approved this configuration, but integrity attestation still found that the weights changed."
        : "Neither statistical detection nor attestation caught this sampled configuration."}</p>
  </aside>;
}

export function DetectionFrontier({ currentAttack }: { currentAttack?: AttackConfig | null }) {
  const [data, setData] = useState<Frontier | null>(null);
  const [selected, setSelected] = useState<Cell | null>(null);
  useEffect(() => { getFrontier().then((value) => setData(normalizeFrontier(value))); }, []);
  const allCells = useMemo(() => data ? [...data.sweeps.depth_size, ...data.sweeps.offset_matching,
    ...data.sweeps.layout, ...data.sweeps.payload_kind] : [], [data]);
  const closest = useMemo(() => {
    if (!currentAttack || !allCells.length) return null;
    return allCells.reduce((best, cell) => attackDistance(cell, currentAttack) < attackDistance(best, currentAttack) ? cell : best);
  }, [allCells, currentAttack]);
  useEffect(() => {
    if (closest) setSelected(closest);
    else if (!selected && allCells.length) setSelected(allCells[0]);
  }, [closest, allCells, selected]);
  if (!data) return <div className="loading-card">Loading the measured frontier…</div>;
  const s = data.summary;

  return <div className="frontier">
    <p className="frontier-method">These are {s.total_configurations} real embed-and-scan runs across four controlled sweeps—not a claim about every possible attack. Select any cell to inspect its evidence.</p>
    <div className="frontier-summary">
      <div><span>Measured runs</span><strong>{s.total_configurations}</strong><small>{s.viable_configurations} had usable capacity</small></div>
      <div><span>Statistics caught</span><strong>{s.statistics_caught}/{s.viable_configurations}</strong><small>{Math.round(100 * s.statistics_caught / s.viable_configurations)}% of viable runs</small></div>
      <div><span>Statistical blind spots</span><strong className="orange">{s.statistical_blind_spots}</strong><small>attestation caught all {s.blind_spots_caught_by_attestation}</small></div>
      <div><span>Uncaught by both</span><strong className="green">{s.escaped_all_controls}</strong><small>{s.viable_configurations - s.escaped_all_controls}/{s.viable_configurations} viable runs covered</small></div>
    </div>
    <div className="frontier-legend"><span><i className="legend caught" />Statistics blocked</span><span><i className="legend attested" />Statistics missed; attestation caught</span>
      <span><i className="legend escaped" />Uncaught</span><span><i className="legend no-capacity" />No usable capacity</span>
      {currentAttack && <span><i className="legend current" />Nearest to your live test</span>}</div>
    <div className="frontier-content"><div className="frontier-sweeps">
      <section className="sweep-block"><h4>1. Payload size × mantissa depth</h4><p>Larger payloads and deeper overwrites are generally easier for statistical checks to see.</p>
        <Matrix cells={data.sweeps.depth_size} rows={[1, 2, 4, 8, 12]} cols={[512, 2048, 8192]} rowKey="n_planes" colKey="n_bytes"
          rowLabel={(v) => `${v} plane${v === 1 ? "" : "s"}`} colLabel={(v) => `${Number(v) / 1024} KB`}
          selected={selected} closest={closest} onSelect={setSelected} /></section>
      <section className="sweep-block"><h4>2. Starting plane × distribution matching</h4><p>Higher kept planes can look statistically normal because payload bits and trained bits become indistinguishable to bit-level tests.</p>
        <Matrix cells={data.sweeps.offset_matching} rows={[0, 4, 8, 12, 16]} cols={[false, true]} rowKey="bit_offset" colKey="match_distribution"
          rowLabel={(v) => `b${v} (${v < 11 ? "freed" : "kept"})`} colLabel={(v) => v ? "Matched" : "Naive"}
          selected={selected} closest={closest} onSelect={setSelected} /></section>
      <section className="sweep-block"><h4>3. Layout × tensor spread</h4><p>The same 4 KB request is placed contiguously, scattered, or sliced across channels and one or four tensors.</p>
        <div className="compact-sweep">{data.sweeps.layout.map((cell, index) => <div className="compact-config" key={`${cell.layout}-${cell.spread_tensors}-${index}`}>
          <span>{layoutName(cell.layout)} · {cell.spread_tensors ?? 1} tensor{cell.spread_tensors === 1 ? "" : "s"}</span>
          <FrontierButton cell={cell} selected={selected === cell} closest={closest === cell} onSelect={setSelected} compact /></div>)}</div></section>
      <section className="sweep-block"><h4>4. Payload byte pattern</h4><p>Random bytes and compressed text travel through the same embedding and detection pipeline.</p>
        <div className="compact-sweep two">{data.sweeps.payload_kind.map((cell, index) => <div className="compact-config" key={`${cell.payload_kind}-${index}`}>
          <span>{cell.payload_kind === "compressed" ? "Compressed text" : "Uniform random"}</span>
          <FrontierButton cell={cell} selected={selected === cell} closest={closest === cell} onSelect={setSelected} compact /></div>)}</div></section>
    </div>{selected && <DetailPanel cell={selected} isClosest={selected === closest} />}</div>
    <div className="frontier-notes"><h4>What this proves—and what it does not</h4>
      <p><strong>Measured:</strong> every cell above modified a clean demo CNN in memory and passed it through the same scan pipeline.</p>
      <p><strong>Defense in depth:</strong> {s.statistical_blind_spots} viable configurations passed statistical thresholds; the separately trusted Merkle baseline caught all {s.blind_spots_caught_by_attestation}.</p>
      <p><strong>Limit:</strong> this is a finite demo sweep under the declared export-and-quantize contract. It is evidence for these configurations, not universal proof for all models or attacks.</p>
    </div>
  </div>;
}
