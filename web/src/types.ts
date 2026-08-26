export interface Verdict {
  risk_score: number;
  band: string;
  gate: string;
  language: string;
  override: string | null;
  reason: string;
  color: "green" | "lime" | "amber" | "red";
}

export interface CoverageBadge {
  detector: string;
  label: string;
  state: string;
}

export interface Coverage {
  badges: CoverageBadge[];
  executed: number;
  applicable: number;
  confidence_pct: number;
}

export interface Finding {
  severity: string;
  code: string;
  message: string;
  evidence?: any;
}

export interface Region {
  tensor: string;
  start: number;
  end: number;
  est_bytes: number;
  scale: number | string;
  zmax: number;
  entropy?: number;
  note?: string;
}

export interface Report {
  schema: string;
  generated_at: number;
  replay: boolean;
  from_cache?: boolean;
  total_ms?: number;
  verdict: Verdict;
  coverage: Coverage;
  fusion: any;
  findings: Finding[];
  detectors: any;
  regions: Region[];
  timeline: { step: string; elapsed_ms: number }[];
  mlbom: any;
  atlas_mapping: { technique: string; name: string; note: string }[];
  disclaimers: string[];
  signature?: any;
}

export interface SampleItem {
  id: string;
  file: string;
  label: string;
  expect: string;
  exists: boolean;
  size: number;
  format: string;
  expected_verdict: Verdict | null;
}

export interface ProgressEvent {
  stage: string;
  status?: string;
  elapsed_ms?: number;
  summary?: string;
  risk_score?: number;
  gate?: string;
  cached?: boolean;
  sha256?: string;
}
