import type { Report, SampleItem, ProgressEvent } from "./types";

const BASE = "/api";

export async function listSamples(): Promise<{ samples: SampleItem[]; methodology?: string }> {
  const r = await fetch(`${BASE}/samples`);
  const j = await r.json();
  return { samples: j.samples || [], methodology: j.methodology };
}

export async function createScan(opts: { sampleId?: string; file?: File }): Promise<{
  scan_id: string;
  filename: string;
  sha256: string;
  size: number;
  format: string;
}> {
  if (opts.sampleId) {
    const r = await fetch(`${BASE}/scan?sample=${encodeURIComponent(opts.sampleId)}`, {
      method: "POST",
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
  const fd = new FormData();
  fd.append("file", opts.file!);
  const r = await fetch(`${BASE}/scan`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export function streamScan(
  scanId: string,
  onProgress: (e: ProgressEvent) => void,
  onComplete: (report: Report) => void,
  onError: (msg: string) => void
): () => void {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}/api/ws/${scanId}`);
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.stage === "complete") {
      onComplete(data.report as Report);
      ws.close();
    } else if (data.stage === "error") {
      onError(data.message || "scan error");
      ws.close();
    } else {
      onProgress(data as ProgressEvent);
    }
  };
  ws.onerror = () => onError("WebSocket error");
  return () => ws.close();
}

export async function getResult(scanId: string): Promise<Report> {
  const r = await fetch(`${BASE}/result/${scanId}`);
  return r.json();
}

export async function compare(a: string, b: string) {
  const r = await fetch(`${BASE}/compare?a=${a}&b=${b}`);
  return r.json();
}

export async function getBenchmark() {
  const r = await fetch(`${BASE}/benchmark`);
  return r.json();
}

export async function verifyReport(scanId: string) {
  const r = await fetch(`${BASE}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scan_id: scanId }),
  });
  return r.json();
}

export async function remediate(scanId: string) {
  const r = await fetch(`${BASE}/remediate/${scanId}`, { method: "POST" });
  return r.json();
}

export function reportPdfUrl(scanId: string) {
  return `${BASE}/report/${scanId}.pdf`;
}

async function post(path: string, body?: unknown) {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function get(path: string) {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type ForgeRequest = {
  n_bytes: number;
  n_planes: number;
  bit_offset: number;
  layout: "contiguous" | "scattered" | "per_channel";
  entropy_matched: boolean;
  spread_tensors: number;
  payload_kind: "random" | "compressed";
  seed: number;
};

export const forge = (req: ForgeRequest) => post("/forge", req);
export const getFrontier = () => get("/frontier");
export const getLineage = () => get("/lineage");
export const getAblation = () => get("/ablation");
export const getHoldout = () => get("/holdout");
export const listAttestations = () => get("/attestations");

export const attestArtifact = (body: {
  sample?: string;
  scan_id?: string;
  declared_version?: string;
  label?: string;
}) => post("/attest", body);

export const attestDiff = (body: {
  attestation_id: string;
  sample?: string;
  scan_id?: string;
}) => post("/attest/diff", body);

export const attestProof = (id: string, tensor: string) =>
  get(`/attest/proof/${id}?tensor=${encodeURIComponent(tensor)}`);

export const sampledScan = (body: {
  sample?: string;
  fraction: number;
  replicates: number;
  target_mb: number;
  embed_payload: boolean;
  seed?: number;
}) => post("/sampled_scan", body);
