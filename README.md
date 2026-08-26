# SentinelWeights — Prototype (`proto.demo2`)

> **Zero Trust for AI Models** — a pre-deployment scanner that X-rays model weight
> files for **hidden-data (steganography)**, **artifact-execution risk (unsafe
> pickles)**, and **functional backdoors**, then issues a transparent, signed
> **Model Risk Score** with per-layer, plain-language evidence.

This is the hackathon MVP of an enterprise design (`sol_steg.md`), built to the
specification in `proto.demo2.md`. Both design documents live alongside the
submission deck rather than in this repository. It runs **fully offline**.

The system architecture is documented as a Mermaid flowchart in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## What's real vs. simulated

| Capability | Status |
|---|---|
| Multi-format ingest (`.safetensors`, `.pt` static-first, `.npz`, `.onnx`) | ✅ real |
| L1 unsafe-deserialization scan (stack-aware `pickletools`, never executed) | ✅ real |
| L1 archive / path-traversal / decompression-bomb / metadata scan | ✅ real |
| L2.1 bit-plane entropy vs arch/dtype baseline | ✅ real (NumPy) |
| L2.2 multi-scale windowed randomness + localization (contiguous **and** scattered) | ✅ real |
| L2.3 randomness feature battery (vs empirical baseline) | ✅ real |
| L2.4 distribution divergence + gzip incompressibility | ✅ real |
| L2.5 precision-sensitivity probe (Δk) | ✅ real (toy) |
| L3 backdoor trigger reverse-engineering (Neural Cleanse) | 🟡 real, **labeled synthetic** MNIST-scale net |
| L4 transparent risk fusion + policy overrides | 🟡 real, fixed exposed weights |
| L4 anomaly head (IsolationForest on synthetic clean corpus) | 🟡 experimental side-channel |
| L2.6 precision-contract violation (occupancy in planes the export freed) | ✅ real |
| L5 risk score + coverage/confidence + heatmaps + report | ✅ real |
| Report signing + verification (Ed25519 demo key) | ✅ real |
| Adversary Lab — forge an attack live, scanned by the real pipeline | ✅ real |
| Detection Frontier — swept attacker parameter space, blind spots named | ✅ real |
| Weight-level Merkle attestation, signed root, tamper diff, inclusion proofs | ✅ real (demo key/ledger) |
| Measured lineage from per-tensor hashes | ✅ real |
| Detector ablation + executed alternative-controls baseline | ✅ real |
| Sealed holdout on an uncalibrated recipe | ✅ real |
| Sampled scan mode with confidence interval | ✅ real |
| Registry / CI-CD / K8s integration | ⚪ labeled proposed |

Language discipline is enforced throughout: we say **"no indicators within scan
scope,"** never *"proven clean"* or *"FDA-ready."*

---

## Quick start

### Option A — Docker (one command, offline)
```bash
docker compose up --build
# web at  http://localhost:5173
# api at  http://localhost:8000  (Swagger: /docs)
```
On first build the backend generates the sample gallery, snapshots, anomaly
corpus, benchmark, and the Ed25519 demo key.

### Option B — local dev
```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/activate    # (Windows) or: source .venv/bin/activate
pip install -r requirements.txt
python -m samples.make_samples                     # build gallery + snapshots + benchmark
uvicorn app:app --port 8000
# CI-style gate (from backend/):
python -m cli scan samples/vault/clean.safetensors --fail-on REVIEW

# frontend (new shell)
cd web
npm install
npm run dev                                        # http://localhost:5173
```

---

## The sample gallery (defensive only, inert payloads)

| Sample | Expected verdict |
|---|---|
| `clean.safetensors` | ✅ APPROVE |
| `stego_contiguous.safetensors` | 🔴 HARD BLOCK (localized payload) |
| `stego_scattered.safetensors` | 🔴 HARD BLOCK (pseudo-random spread) |
| `pickle_fixture.pt` | ⛔ HARD BLOCK (unsafe deserialization, never executed) |
| `backdoor_toycnn.safetensors` | 🟠 REVIEW (recovered trigger) |
| `public_clean.safetensors` | ✅ APPROVE (third-party edge-quantized fixture, not our training recipe) |
| `quantized_clean.safetensors` | ✅ APPROVE (legit anomaly, not flagged) |
| `malformed.bin` | 🟠 QUARANTINE (fail-safe, no green pass) |

All "payloads" are **inert test bytes**. The malicious pickle is **statically
inspected only — never deserialized**.

---

## API surface

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/scan` | Upload a model (or `?sample=<id>`); returns `scan_id` |
| `WS` | `/ws/{scan_id}` | Streams per-tier progress + real `elapsed_ms` |
| `GET` | `/result/{scan_id}` | Full JSON verdict |
| `GET` | `/compare?a=&b=` | Side-by-side clean vs tampered |
| `GET` | `/benchmark` | Confusion / ROC / latency snapshot |
| `POST` | `/remediate/{scan_id}` | Experimental sanitize + rescan |
| `GET` | `/report/{scan_id}.pdf` | Signed PDF evidence artifact |
| `POST` | `/verify` | Verify a report signature (`{scan_id}`) |
| `GET` | `/samples` | Sample gallery listing |
| `POST` | `/forge` | Embed a caller-specified payload into the clean model and scan it |
| `GET` | `/frontier` | Swept attack space: gate, risk, fidelity, blind spots |
| `POST` | `/attest` | Merkle root over per-tensor hashes, signed and ledgered |
| `GET` | `/attestations` | Attestation ledger summary |
| `POST` | `/attest/diff` | Candidate vs attested baseline, with bit-level forensics |
| `GET` | `/attest/proof/{id}?tensor=` | Inclusion proof for one tensor |
| `GET` | `/lineage` | Measured cross-model tensor overlap |
| `GET` | `/ablation` | Leave-one-out detector AUC + alternative-controls baseline |
| `GET` | `/holdout` | Sealed holdout metrics on an uncalibrated recipe |
| `POST` | `/sampled_scan` | Build a large fixture, triage a sampled fraction, return an interval |

CLI (from `backend/`): `python -m cli scan <path> --fail-on REVIEW` (exit 0 / 2 / 3).

---

## Architecture

```
web (React+Vite+TS+Tailwind)  ──REST/WS──▶  FastAPI backend
  gallery · pipeline funnel                 orchestrator (tiered funnel, real timings)
  risk gauge · coverage                     ├─ ir.py + ingest/  (canonical IR)
  compare · heatmap · opcodes               ├─ detectors/  (L1..L4, real math)
  benchmark · timeline · ML-BOM             ├─ policy.py    (deterministic overrides)
  persona views · signing/verify            ├─ signing/     (Ed25519 demo key)
                                            └─ report/      (JSON + signed PDF)
```

See `proto.demo2.md` for the full screen-by-screen spec and demo script.

---

## Proving it rather than asserting it

The UI has five views. Three of them exist to be attacked:

- **Red team** — the *Adversary Lab* lets a judge author the attack (payload size,
  mantissa depth, plane offset, layout, distribution matching) and watch the real
  pipeline verdict. The *Detection Frontier* sweeps that whole space and names the
  configurations we miss. Every statistical blind spot is a payload written into
  *kept* mantissa planes, where payload bits and trained value bits are the same
  thing to any bit-level test — no threshold change fixes that.
- **Proof** — the attested Merkle baseline that catches those blind spots and
  classifies silent substitution; measured lineage; leave-one-out detector ablation
  next to an *executed* conventional-tooling baseline; a sealed holdout on a recipe
  the thresholds never saw; and a sampled scan on a large artifact built on the spot.

Where a conventional control wins, the panel says so: a format policy and a
signature scan genuinely stop the malicious pickle. Neither reads a float mantissa.

---

## Honest limitations

- Thresholds/fusion weights are **fixed demo values**, exposed on screen.
- Attestation uses a **local ledger and demo key**; the cryptography is real, the
  surrounding trust infrastructure (PKI, transparency log) is not.
- The frontier is an envelope for **this artifact class** under the declared export
  contract, not a GE-wide claim. Cross-architecture generalization is untested.
- Ablation runs on a narrow corpus. One detector group currently **ranks better
  when removed**; we report that rather than quietly keeping the claim.
- Backdoor detection runs on a **labeled synthetic** model; large-model behavioral
  results would be **cached and labeled**, never a live pass.
- Signing uses a **local demo key** (real Ed25519 + verify), not production PKI/Sigstore.
- A **cybersecurity** pass never implies **clinical** validation.
