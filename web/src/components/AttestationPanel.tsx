import { useEffect, useState } from "react";
import * as api from "../api";
import type { SampleItem } from "../types";
import { Pill, Stat, bandColor } from "./ui";

const CLASS_TONE: Record<string, string> = {
  IDENTICAL: bandColor.green,
  SILENT_SUBSTITUTION: bandColor.red,
  DECLARED_CHANGE: bandColor.amber,
};

function Mono({ children }: { children: React.ReactNode }) {
  return <span className="mono text-[11px] text-ink-600">{children}</span>;
}

export default function AttestationPanel() {
  const [samples, setSamples] = useState<SampleItem[]>([]);
  const [ledger, setLedger] = useState<any[]>([]);
  const [baseline, setBaseline] = useState("");
  const [candidate, setCandidate] = useState("");
  const [diff, setDiff] = useState<any>(null);
  const [proof, setProof] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const loadable = samples.filter((s) => s.file?.endsWith(".safetensors"));

  async function refresh() {
    const j = await api.listAttestations();
    setLedger(j.attestations || []);
    if (!baseline && j.attestations?.length) {
      setBaseline(j.attestations[j.attestations.length - 1].attestation_id);
    }
  }

  useEffect(() => {
    api.listSamples().then((j) => {
      setSamples(j.samples);
      const first = j.samples.find((s) => s.id !== "clean" && s.file?.endsWith(".safetensors"));
      if (first) setCandidate(first.id);
    });
    refresh().catch((e) => setErr(String(e?.message || e)));
  }, []);

  const record = ledger.find((r) => r.attestation_id === baseline);

  async function attestSample(id: string) {
    setBusy("attest");
    setErr("");
    try {
      const r = await api.attestArtifact({ sample: id, label: id });
      await refresh();
      setBaseline(r.attestation_id);
      setDiff(null);
      setProof(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runDiff() {
    if (!baseline || !candidate) return;
    setBusy("diff");
    setErr("");
    setProof(null);
    try {
      setDiff(await api.attestDiff({ attestation_id: baseline, sample: candidate }));
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  async function runProof(tensor: string) {
    setBusy("proof");
    try {
      setProof(await api.attestProof(baseline, tensor));
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-5">
      <p className="text-[13px] text-ink-600 leading-relaxed">
        A signed report proves the report wasn't edited. It says nothing about the model
        the report describes. So we attest the artifact itself: one SHA-256 leaf per tensor,
        name-sorted into a Merkle tree, root signed with Ed25519 and appended to a local
        ledger. That gives us the case accuracy tests cannot see — a vendor reships the same
        version number, the same tensor count, the same parameter count, and different weights.
      </p>

      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <div className="text-[12px] text-ink-600 mb-1.5">Attested baseline</div>
          <select
            value={baseline}
            onChange={(e) => {
              setBaseline(e.target.value);
              setDiff(null);
              setProof(null);
            }}
            className="w-full text-[12px] px-2.5 py-2 rounded-lg border border-paper-line bg-paper-card text-ink"
          >
            <option value="">— none selected —</option>
            {ledger.map((r) => (
              <option key={r.attestation_id} value={r.attestation_id}>
                {r.label} · {r.declared_version} · {r.merkle_root.slice(0, 12)}…
              </option>
            ))}
          </select>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {loadable.slice(0, 6).map((s) => (
              <button
                key={s.id}
                onClick={() => attestSample(s.id)}
                disabled={!!busy}
                className="text-[11px] px-2.5 py-1 rounded-full border border-paper-line
                           text-ink-600 hover:border-ink/30 hover:text-ink disabled:opacity-50"
              >
                attest {s.id}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="text-[12px] text-ink-600 mb-1.5">Candidate artifact</div>
          <select
            value={candidate}
            onChange={(e) => setCandidate(e.target.value)}
            className="w-full text-[12px] px-2.5 py-2 rounded-lg border border-paper-line bg-paper-card text-ink"
          >
            {loadable.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
          <button
            onClick={runDiff}
            disabled={!!busy || !baseline}
            className="mt-2 text-[13px] px-4 py-1.5 rounded-full bg-ink text-paper-card
                       hover:bg-ink-800 disabled:opacity-50"
          >
            {busy === "diff" ? "Diffing…" : "Diff against baseline"}
          </button>
        </div>
      </div>

      {record && (
        <div className="text-[11px] text-ink-400 space-y-0.5">
          <div>
            root <Mono>{record.merkle_root}</Mono>
          </div>
          <div>
            {record.n_leaves} tensor leaves · file sha256{" "}
            <Mono>{String(record.file_sha256).slice(0, 24)}…</Mono>
            {record.gate_at_attestation && <> · gate at attestation {record.gate_at_attestation}</>}
          </div>
        </div>
      )}

      {err && <p className="text-[13px] text-rust">{err}</p>}

      {diff && (
        <div className="space-y-4">
          <div
            className="rounded-xl px-4 py-3 border"
            style={{
              borderColor: `${CLASS_TONE[diff.classification]}33`,
              background: `${CLASS_TONE[diff.classification]}0f`,
            }}
          >
            <div className="flex items-center gap-2 mb-1.5">
              <Pill color={CLASS_TONE[diff.classification]} filled>
                {diff.classification.replace(/_/g, " ")}
              </Pill>
              {diff.signature_valid ? (
                <Pill color={bandColor.green}>attestation signature valid</Pill>
              ) : (
                <Pill color={bandColor.red}>signature invalid</Pill>
              )}
            </div>
            <p className="text-[13px] text-ink leading-relaxed">{diff.headline}</p>
          </div>

          <div className="grid sm:grid-cols-4 gap-3">
            <Stat
              label="Merkle root"
              value={diff.root_match ? "match" : "differs"}
              color={diff.root_match ? bandColor.green : bandColor.red}
            />
            <Stat
              label="Declared metadata"
              value={diff.declared_metadata_match ? "identical" : "changed"}
              color={diff.declared_metadata_match ? bandColor.amber : undefined}
              sub={diff.declared_metadata_match ? "would pass an inventory check" : undefined}
            />
            <Stat label="Tensors changed" value={diff.changed_count} sub={`${diff.unchanged_count} untouched`} />
            <Stat
              label="File hash"
              value={diff.file_hash_match ? "match" : "differs"}
              sub="whole-artifact SHA-256"
            />
          </div>

          {diff.changed?.length > 0 && (
            <div>
              <div className="text-[12px] text-ink-600 mb-2">Changed leaves</div>
              <div className="space-y-1">
                {diff.changed.map((c: any) => (
                  <div key={c.name} className="flex flex-wrap items-baseline gap-x-2">
                    <span className="mono text-[12px] text-ink">{c.name}</span>
                    <Mono>
                      {c.attested_leaf}… → {c.candidate_leaf}…
                    </Mono>
                    {c.shape_changed && <Pill color={bandColor.amber}>shape changed</Pill>}
                    <button
                      onClick={() => runProof(c.name)}
                      className="text-[11px] text-forest hover:underline"
                    >
                      inclusion proof
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {diff.bit_forensics?.length > 0 && (
            <div>
              <div className="text-[12px] text-ink-600 mb-2">
                Which bits moved
              </div>
              <div className="space-y-2">
                {diff.bit_forensics.map((f: any) => (
                  <div key={f.tensor} className="rounded-lg bg-paper border border-paper-line px-3 py-2">
                    <div className="text-[12px] text-ink mono mb-1">{f.tensor}</div>
                    <div className="text-[12px] text-ink-600">
                      {f.slots_changed.toLocaleString()} of {f.slots_total.toLocaleString()} weights
                      touched · {f.bits_changed.toLocaleString()} bits flipped · relative L2 change{" "}
                      {f.rel_l2_delta}
                    </div>
                    <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
                      {Object.entries(f.by_region as Record<string, number>).map(([r, n]) => (
                        <span key={r} className="text-[11px] text-ink-400">
                          {r}: {n.toLocaleString()}
                        </span>
                      ))}
                    </div>
                    {f.highest_plane_touched != null && (
                      <div className="text-[11px] text-ink-400 mt-1">
                        Highest plane touched: b{f.highest_plane_touched} — the exponent and sign
                        are untouched, which is exactly what a payload-not-retrain signature
                        looks like.
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-[11px] text-ink-400 leading-snug">{diff.forensics_note}</p>
        </div>
      )}

      {proof && (
        <div className="rounded-xl bg-paper border border-paper-line px-4 py-3">
          <div className="flex items-center gap-2 mb-1.5">
            <Pill color={proof.verified ? bandColor.green : bandColor.red} filled>
              {proof.verified ? "proof verifies" : "proof failed"}
            </Pill>
            <span className="mono text-[11px] text-ink-600">{proof.tensor}</span>
          </div>
          <p className="text-[12px] text-ink-600 leading-relaxed">{proof.note}</p>
          <div className="mt-1.5 space-y-0.5">
            {proof.proof.map((s: any, i: number) => (
              <Mono key={i}>
                {i + 1}. {s.side.padEnd(5)} {s.hash.slice(0, 32)}…
              </Mono>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="text-[12px] text-ink-600 mb-2">Ledger ({ledger.length} entries)</div>
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {ledger.slice().reverse().map((r) => (
            <div key={r.attestation_id} className="flex flex-wrap gap-x-2 text-[11px]">
              <span className="text-ink-400 tabular-nums">
                {new Date(r.created_at * 1000).toLocaleString()}
              </span>
              <span className="text-ink">{r.label}</span>
              <span className="text-ink-400">{r.declared_version}</span>
              <Mono>{r.merkle_root.slice(0, 16)}…</Mono>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-ink-400 mt-2 leading-snug">
          Append-only local file, signed per entry. A production deployment would put this
          in a transparency log with a real PKI; the cryptography here is real, the trust
          infrastructure around it is a demo.
        </p>
      </div>
    </div>
  );
}
