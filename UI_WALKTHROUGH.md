# SentinelWeights — Complete UI Walkthrough

This guide explains every main page of SentinelWeights from the beginning, including what each input, button, result, chart, and technical term means.

## 1. Concepts to understand first

### Model weights

An AI model learns numerical values during training. These values are called **weights** and are stored in arrays called **tensors**.

### Detector

A detector is one security check. Different detectors examine different risks, including unsafe files, unusual bit patterns, hidden data, precision-contract violations, and synthetic backdoors.

### Risk score

The model risk score is a combined policy score from 0 to 100. It is not the probability that a model contains malware.

The approximate policy bands are:

| Score | Band | Typical decision |
|---|---|---|
| 0–20 | Clean | Approve |
| Above 20–50 | Low concern | Approve with caveats |
| Above 50–80 | Suspicious | Human review |
| Above 80–100 | Dangerous | Hard block |

### Gate

The gate is the operational release decision:

- **APPROVE:** No executed detector exceeded its relevant threshold.
- **APPROVE WITH CAVEATS:** Minor concerns were recorded.
- **REVIEW:** Human security review is required.
- **HARD BLOCK:** Strong attack evidence or a critical unsafe-file condition was found.
- **QUARANTINE:** The system could not safely establish what the file contains.

### Coverage

Coverage shows how many applicable detectors actually ran. Low risk with high coverage is stronger evidence than low risk with low coverage.

### Attestation

Attestation compares a model with a previously trusted cryptographic fingerprint. It proves that the candidate is identical to or different from that baseline. A difference does not automatically prove malicious intent.

---

# Common interface

## Left navigation

- **Scan — Intake and gate:** Select a model and obtain a security decision.
- **Evidence — Timeline, BOM, benchmark:** Examine and export evidence from the latest scan.
- **Red team — Forge an attack live:** Safely modify a clean model and test the scanner.
- **Proof — Attestation and ablation:** Validate integrity and evaluate the detector system itself.
- **Lab — Every panel:** Inspect detailed technical output from the latest scan.

## Model gallery

The model cards in the left rail are prepared demonstration artifacts. The label on each card is its expected gate. Clicking a card starts a real scan of that artifact.

Examples include clean, quantized, backdoored, stego, malicious pickle, truncated, and malformed models.

## Upload control

**Drop a model, or browse** accepts a model from the user. The uploaded file goes through the same pipeline as a gallery artifact.

Unsafe pickle files are statically disassembled; they are not loaded or executed.

## Header status

- **Ready:** No scan is running.
- **Scanning:** A model is being processed.
- **Stored snapshot:** The visible result came from a stored scan result.

---

# Page 1 — Scan

The Scan page answers: **Should this model be allowed into the next stage of the supply chain?**

## What happens when a model is selected

1. The frontend sends the artifact to the scan endpoint.
2. The backend creates a scan ID.
3. Pipeline progress is streamed back to the page.
4. Detectors produce normalized evidence.
5. The policy combines the evidence.
6. The page displays risk, coverage, gate, findings, and model-specific explanations.

## Top summary cards

### Model risk

Shows the 0–100 risk score and final gate. The score is a policy score, not a malware probability.

### Scan coverage

Shows the percentage of applicable detectors that executed. A badge such as `8/9` means eight of nine applicable detectors ran.

### Strongest evidence

Shows the detector family producing the strongest normalized evidence in the current scan. The badge displays its anomaly strength as a `z` value.

- **None / below threshold:** No detector produced reportable attack evidence.
- **Static / CRITICAL:** Static file inspection found a critical unsafe operation.
- **Ingest / unloadable:** The artifact could not be safely interpreted.
- **Contract, Window, Backdoor, etc.:** The named detector produced the strongest numerical signal.

This is dynamic for the selected model. The `z` value is anomaly strength, not a malware probability.

### Zero Trust

Summarizes the design principle that a model should not be trusted only because its filename or format looks familiar.

The displayed AUC summarizes benchmark ranking performance on the demonstration corpus.

**Attack it yourself** opens the Red Team page.

## Ninety-second path

This is a guided jury walkthrough.

### Model shortcuts

The shortcut labels include Clean, Vendor `.pt`, Borderline, Backdoor, Stego, Silent stego, Pickle, Zip slip, Truncated, Public, Quantized, and Malformed.

Clicking a label starts that example's scan.

### Back and Next

These move through the prepared examples in presentation order and scan the selected example. At the final example, **Next** becomes **Done**.

### Progress rail

The coloured rail and small segments show presentation progress. They do not represent model risk.

## Pipeline

### Tier 00 — Ingest

Identifies the format and size, validates the structure, and determines whether weights can be safely extracted.

### Tier 01 — Static

Examines the file as data for dangerous pickle operations, suspicious archive paths, unsafe deserialization targets, and malformed containers. A critical result can stop the remaining pipeline.

### Tier 02 — Weights

Examines tensors for:

- unusual bit-plane entropy;
- localized random-looking regions;
- compressed or encrypted-looking data;
- cross-layer abnormalities;
- hidden data in near-zero parameters;
- precision-contract violations.

### Tier 03 — Behavior

Runs only when a supported model and test setup are available. In the demo it searches a synthetic CNN for suspicious trigger behaviour. It is not a clinical validation test.

### Tier 04 — Policy

Combines the evidence into the final gate. Critical unsafe deserialization causes HARD BLOCK. An unreadable model causes QUARANTINE. Other models are decided from the risk band.

### Pipeline statuses

- **Idle:** Not started.
- **Running:** Currently executing.
- **Done:** Completed.
- **Cached:** An existing result was reused.
- **Skipped:** Not applicable or unavailable.
- **Stop:** Critical evidence stopped the pipeline.

The milliseconds shown on each card are measured stage durations.

## Risk panel

The circular gauge visualizes the final risk score. The coverage bar underneath shows how much applicable inspection was completed.

## Gate panel

Displays the final release decision and conservative policy wording. Findings underneath show severity, evidence code, and a plain-language message.

## Model-specific sections

### Stego models

- **Sibling compare:** Compares the suspicious model with its clean sibling.
- **Where:** Shows localized low-mantissa entropy and possible payload locations.

### Pickle or archive models

The **Opcodes** panel shows statically disassembled instructions. The file is never executed.

### Backdoor models

The **Trigger** panel shows results from the supported synthetic behavioural probe.

### Public or legitimately quantized models

The **Not a false alarm** panel explains why normal quantization or a third-party model should not automatically be blocked.

### Corrupted or unknown models

The **Fail-safe** panel explains why an unreadable artifact is quarantined. Quarantine means safety was not established; it does not prove malware.

### Remediation

For supported stego or unsafe-format examples, SentinelWeights can create a sanitized or converted copy and rescan it. Remediation may change behaviour, so human approval is still required.

## Limits

The Limits card prevents overclaiming:

- No indicators found does not mean universally safe.
- Thresholds are demonstration values.
- Backdoor tests use a synthetic model.
- Signing uses a local demo key, not production PKI.
- Security clearance is separate from clinical validation.

---

# Page 2 — Evidence

The Evidence page answers: **Why should a reviewer trust the result shown on the Scan page?**

It uses the latest completed scan. If no model was scanned, it shows **No scan yet**. Selecting a model from the sidebar while on Evidence starts a scan and updates the page when it finishes.

## Verdict snapshot

Repeats the risk score and band so the evidence bundle can be understood without returning to Scan.

## Gate language

Repeats the conservative operational decision. The application says “no indicators within scan scope,” not “proven safe.”

## Sample contract

Explains how the demonstration gallery, clean baseline, tampered examples, quantization contract, and benchmark corpus were constructed.

## Scan timeline

Shows the sequence and measured duration of every stage in the selected scan. A longer stage does not necessarily mean that it found more risk.

## Sibling compare

This section appears only after completing a scan of a stego model such as:

- Stego (contiguous)
- Stego (scattered)
- Stego (kept-plane evasion) / Silent stego

It is located below **Scan timeline** on Evidence.

### Clean and tampered sibling cards

Show model name, risk, gate, parameter count, and tensor count.

### Architecture

`Identical` means both models have the same network structure.

### Parameters

`Match` means they have the same number of parameters, not that every value is identical.

### Output agreement

Shows how many sampled numerical probes stayed within tolerance. It is not complete inference accuracy, clinical accuracy, or proof of identical behaviour for every input.

### Hidden capacity

Estimates how many payload bytes occupy the suspicious region.

### Changed bit planes

Shows which mantissa positions changed most between the clean and tampered models.

## Supply chain

Translates the technical result into supply-chain language:

- supply-chain risk;
- release gate;
- recommended action.

This is a cybersecurity assessment, not clinical validation.

## Blast radius

Illustrates how one compromised backbone could affect several downstream products. The displayed product graph is illustrative; measured lineage appears on Proof.

## ML-BOM

The Machine Learning Bill of Materials is the model's identity card.

It shows:

- format;
- filename;
- tensor count;
- parameter count;
- whether weights were safely loadable;
- policy version;
- license;
- SHA-256 file fingerprint.

### Export signed PDF

Opens a PDF containing the scan evidence and signature information.

### Verify report

Verifies that the stored report still matches its digital signature.

- **Valid:** Report content matches the signature.
- **Invalid:** Report content or signature does not match.

A valid signature proves report integrity within the demo. It does not prove that every scientific conclusion is universally correct.

### MITRE ATLAS

Maps applicable findings to standardized machine-learning attack techniques.

## Benchmark

### ROC AUC

Measures how well the system ranks suspicious examples above clean examples. `0.5` is approximately random ranking; values closer to `1.0` show better separation on this corpus.

### Corpus

Shows the number of clean and tampered benchmark examples.

### Latency

- **Mean:** Average scan duration.
- **p95:** Approximately 95% of scans completed within this duration.

### Confusion matrix

- **TP:** Suspicious model correctly detected.
- **FP:** Clean model incorrectly flagged.
- **TN:** Clean model correctly approved.
- **FN:** Suspicious model missed.

### ROC curve

Plots true-positive rate against false-positive rate across multiple thresholds.

### Latency versus model size

Plots parameter count against scan duration.

### Threshold slider

Changes the experimental benchmark threshold and recalculates TP, FP, TN, and FN. It does not modify the stored model verdict or production policy.

---

# Page 3 — Red Team

The Red Team page answers: **Can we deliberately modify a clean model and see whether SentinelWeights detects it?**

It uses harmless inert bytes and never overwrites the original clean baseline.

## Workflow tabs

1. **Live experiment:** Build and run one attack.
2. **Detection frontier:** Compare it with 33 measured configurations.

## Safe attack host

Every run loads a fresh clean baseline, copies it in memory, modifies the copy, scans the copy, and leaves the source model unchanged.

## Guided demo and Advanced controls

- **Guided demo:** Uses jury-friendly presets and hides detailed controls.
- **Advanced controls:** Exposes every attack parameter.

Switching mode does not run an attack.

## Scenario presets

### Obvious hidden payload

Places 4 KB into six freed low-mantissa planes in one contiguous tensor region. Expected result: precision-contract block.

### Low and slow

Places 256 bytes in one plane, spreads it across several tensors, and uses per-channel placement.

### Distribution-matched evasion

Attempts to make inserted bits follow the clean model's existing per-plane distribution. In zero-valued freed planes this may leave almost no usable capacity.

### Kept-plane blind spot

Places data in higher retained precision planes. Statistics may miss it, while attestation detects that the model differs from the trusted baseline.

Changing an advanced control labels the configuration **Custom configuration**.

## Mantissa basics

A float32 weight contains a sign bit, exponent bits, and 23 mantissa bits labelled `b0–b22`.

- `b0` is least significant.
- In the demo contract, `b0–b10` were freed and should remain zero.
- `b11–b22` retain model precision.

Occupancy in freed planes violates the declared export contract. Retained planes are statistically harder to distinguish from trained data.

## Advanced inputs

### Payload size

Requested inert data size from 0 to 32 KB in 256-byte steps. Larger payloads change more values and are usually easier to detect.

### Payload pattern

- **Uniform random:** High-entropy random bytes.
- **Compressed text:** Compressed inert demonstration text.

When distribution matching is on, the clean model's distribution controls the pattern, so these options are disabled.

### Mantissa planes

Number of consecutive planes used to carry payload bits.

### First plane

Starting plane of the range. The interface prevents the selected range from exceeding `b22`.

### Tensors targeted

Number of weight tensors receiving payload data.

### Layout

- **Contiguous:** One continuous block.
- **Scattered:** Pseudo-random positions.
- **Per channel:** A thin slice across output channels.

### Distribution matching

- **Off:** Payload bits directly overwrite planes; maximum capacity and stronger entropy signature.
- **On:** Replacement bits follow the clean plane distribution; potentially stealthier but lower capacity.

## Review the attack

Before any modification, the page calls a capacity-preview endpoint.

### Mantissa strip

Shows selected planes and whether they lie in freed or retained precision.

### Requested

Number of payload bytes requested.

### Estimated capacity

Approximate number of bytes the selected tensors and planes can carry.

### Status

- **Fits:** Full request can be encoded.
- **X B short:** Only part can fit.
- **Zero capacity:** The attack cannot be constructed; Run is disabled.

### Host

Names the tensors expected to carry the payload.

## Run controls

### Run attack simulation

1. Loads a fresh clean baseline.
2. Generates inert payload bytes.
3. Converts the payload to bits.
4. Selects tensor positions.
5. Writes bits into selected mantissa planes.
6. Runs the normal scan pipeline.
7. Compares with the trusted baseline.
8. Returns gate, risk, evidence, fidelity, and attestation.

### Reset

Restores the default obvious-payload configuration and clears the result.

### New seed

Changes pseudo-random payload bytes and positions. The same configuration and seed are reproducible.

## Result cards

### Gate

Final decision and risk score.

### Effective payload

Bytes actually embedded. It can be lower than the requested size when capacity is insufficient.

### Numerical probe agreement

Compares 512 numerical layer probes with a 5% relative-error tolerance. It is not end-to-end accuracy or clinical validation.

### Strongest evidence

Shows the detector with the largest normalized anomaly signal. Anomaly strength is not a malware probability.

## Result tabs

### Why this verdict

Plain-language result explanation.

### Detector evidence

Shows normalized `z` evidence for each detector. Related steganography signals are grouped before fusion.

### Changed tensors

Lists localized precision-contract violations, affected weights, planes, and estimated occupied bytes.

### Attestation

Shows whether the candidate differs from the trusted baseline and identifies changed tensors and bit regions.

### Stale-result warning

If configuration changes after a run, the old result fades and the page asks you to run again.

## Explore this attack in the frontier

Switches to the measured frontier and highlights the nearest stored configuration.

## Detection frontier

The frontier contains 33 real embed-and-scan measurements. It is a finite experiment, not every possible attack.

### Summary

- measured runs;
- viable attacks with usable capacity;
- attacks caught statistically;
- statistical blind spots;
- blind spots caught by attestation;
- attacks uncaught by both controls.

### Colours

- Red/pink: statistics blocked the attack.
- Orange: statistics missed it; attestation caught it.
- Green: neither control caught it.
- Grey: no usable attack capacity.
- Purple outline: nearest configuration to the latest live experiment.

### Four sweeps

1. Payload size × mantissa depth
2. Starting plane × distribution matching
3. Layout × tensor spread
4. Payload byte pattern

Clicking a cell opens its requested size, planes, layout, distribution mode, effective bytes, risk, gate, numerical agreement, and strongest detector.

---

# Page 4 — Proof

The Proof page answers: **How do we know the model changed, and how do we know the detector system itself is credible?**

## Weight-level attestation

For every tensor, SentinelWeights calculates a SHA-256 leaf hash. Name-sorted leaves are combined into a Merkle tree. The root is signed with Ed25519 and added to a local ledger.

Any tensor change produces a different leaf and root.

### Attested baseline

Selects a previously trusted artifact fingerprint.

### Attest buttons

Create a new tensor-level fingerprint, sign its root, append it to the ledger, and select it as the baseline.

Attesting a model records identity; it should not replace scanning and authorization.

### Candidate artifact

Selects the model to compare with the baseline.

### Diff against baseline

Checks signature validity, Merkle root, file hash, declared metadata, tensor hashes, and bit-level differences.

### Classifications

- **IDENTICAL:** Candidate matches the baseline.
- **SILENT SUBSTITUTION:** Declared identity appears unchanged but tensor bytes differ.
- **DECLARED CHANGE:** Artifact and declared identity both changed.

### Result cards

- **Merkle root:** Match or difference.
- **Declared metadata:** Whether inventory-like fields changed.
- **Tensors changed:** Changed versus untouched leaves.
- **File hash:** Whole-file SHA-256 comparison.

### Changed leaves

Shows old and new tensor hashes and whether tensor shape changed.

### Inclusion proof

Proves that one tensor leaf belongs to the signed Merkle root without requiring every tensor to be displayed.

### Which bits moved

Shows weights touched, bits flipped, relative L2 change, floating-point regions affected, and highest plane touched.

### Ledger

Lists attestation time, label, declared version, and Merkle root. The demo uses real cryptography with local trust infrastructure; production requires protected keys and an external transparency log.

## Measured lineage

Hashes all loadable gallery artifacts tensor by tensor and measures relationships.

### Summary

- artifacts hashed;
- related pairs;
- derived pairs with substantial identical tensor overlap;
- propagation findings where an approved model has a tainted sibling.

### Relationships

- **Identical:** Complete tensor-hash match.
- **Derived:** Substantial overlap.
- **Weak:** Limited overlap.

The section shows identical and differing tensors, overlap percentage, and localized differences.

## Detector ablation

Ablation asks whether every detector earns its place.

Stored feature vectors are passed through the real fusion function with one detector group removed, then with that group used alone.

### Metrics

- Full-stack AUC
- Corpus size and composition
- Confusion matrix at the normal threshold
- AUC without each group
- AUC change if removed
- AUC when used alone
- Change in true and false positives

### Detector verdicts

- **Load bearing:** Removal harms performance.
- **Redundant here:** Useful but covered by another detector on this corpus.
- **Ranking better without it:** Removal improves this particular benchmark.
- **No signal on this corpus:** No useful separation in these examples.

## Alternative controls

Actually evaluates conventional approaches:

- SentinelWeights
- file hash versus baseline
- accuracy regression
- byte-signature scan
- SafeTensors-only format policy

Coverage bars show how many tampered artifacts each control catches. Expand a model row to see the result from every control.

## Sealed holdout

Evaluates unchanged thresholds on model and attack recipes that did not participate in calibration.

### Outputs

- true-positive rate on unseen viable attacks;
- false-positive rate on unseen clean variants;
- unchanged operating point;
- negligible-capacity exclusions;
- differences from the calibrated recipe;
- openly reported misses and false alarms;
- per-example risk scores.

## Scale — sampled triage

Builds a large temporary artifact and estimates its risk from repeated stratified samples of whole output channels.

### Sampling fraction

Percentage read in each pass, from 1% to 50%.

### Fixture size

Approximate generated artifact size, from 16 MB to 512 MB.

### Replicates

Number of independent sampled passes, from 2 to 16.

### Payload embedded / Clean fixture

Toggles whether the generated artifact contains an inert payload.

### Generate and triage

Builds the fixture, optionally embeds a payload, writes it temporarily, runs static analysis and repeated samples, combines estimates, and deletes the fixture.

### Outputs

- actual artifact size and parameters;
- bytes actually read;
- mean risk and 95% interval;
- wall-clock time;
- gate stability and agreement;
- score from every replicate;
- caveats and confirmation that the fixture was generated live.

Large values may be slow or memory-intensive on Render.

---

# Page 5 — Lab

The Lab page answers: **Show all detailed detector outputs for the latest scan.**

Select a model from the sidebar first. Lab displays pipeline progress, risk, coverage, gate, findings, drill-downs, evidence, remediation, ML-BOM, and benchmark information.

## Persona selector

- **Executive:** Risk, release decision, affected assets, and comparison.
- **Security:** Findings, opcodes, ATLAS, and detector contributions.
- **ML-Engineer:** Heatmaps, entropy, precision, layer statistics, and comparison.
- **Regulatory:** Timeline, coverage, signed artifact, and mappings.

All drill-down tabs remain accessible. Persona selection changes emphasis and whether the additional sibling comparison is shown; it is not an access-control system.

## Pipeline, Risk, and Gate

These work as described on Scan. Lab continues into detailed detector output after the decision.

## Drill-down tabs

### Heatmap

Shows local low-mantissa entropy across each tensor. A continuous dark rust band indicates a random-looking localized region consistent with a payload.

### Entropy

Compares observed mantissa-bit entropy with the clean baseline across `b0–b22`. The excess region highlights suspicious deviation.

### Precision

Clears increasing numbers of low mantissa bits and measures relative numerical output change. A flat curve suggests spare numerical capacity. Tolerated `k` is the approximate number of low bits removable without substantial sampled change.

### Layers

Ranks tensors by localized suspicion using incompressibility, entropy excess, and flagged regions. It is a location-ranking score, not the final model risk.

### Opcodes

Displays statically disassembled pickle operations and dangerous globals. `REDUCE` applied to a dangerous callable can create an execution path. The file is never deserialized.

Pure-data files normally show **No serialized-code surface**.

### Trigger

Shows recovered synthetic trigger masks, per-class anomaly index, clean and triggered accuracy, attack success rate, and accuracy drop. It only runs for the supported synthetic model and is suspicion-elevating evidence, not clinical proof.

### Weights

Explains fusion weights and actual detector contributions, not raw model parameters.

The simplified fusion is:

`risk = 100 × sigmoid(bias + sum(weight × normalized evidence))`

Related steganography signals are grouped so one anomaly is not counted several times independently.

### Narrative

Translates structured detector evidence into plain language. Narratives are generated from detector fields and evidence codes, not free-form AI text.

## Sibling compare

Executive and ML-Engineer emphasis can show the clean-versus-stego comparison. It demonstrates identical architecture and parameter count with different security outcomes.

## Evidence sections

Lab also contains the Sample contract, Scan timeline, Supply chain, Blast radius, ML-BOM, signed report controls, MITRE ATLAS, and Benchmark described on Evidence.

## Remediation

**Remediate and rescan** creates a sanitized or converted copy when supported.

- Stego: Clears or sanitizes suspicious low-significance regions.
- Unsafe format: Attempts conversion into a data-only format without executing pickle instructions.
- Unsupported artifact: Explains that remediation is unavailable.

The before-and-after cards show risk and gate. Remediation can alter behaviour and never replaces human approval, accuracy testing, or clinical validation.

---

# Recommended jury flow

1. **Scan → Clean:** Demonstrate a normal approval.
2. **Scan → Stego:** Demonstrate a high-risk hidden payload with near-identical numerical probes.
3. **Evidence:** Show the timeline, sibling comparison, model fingerprint, and signed report.
4. **Red Team → Obvious hidden payload:** Run an attack configured in front of the jury.
5. **Red Team → Kept-plane blind spot:** Show that statistics can miss a case while attestation catches model drift.
6. **Proof:** Explain the trusted baseline, tensor-level changes, lineage, ablation, and holdout.
7. **Lab:** Use only for technical questions about entropy, bit planes, opcodes, triggers, or fusion.

# Complete system flow

`Select or upload model → safe intake → static inspection → weight analysis → optional behavioural analysis → policy gate → evidence bundle → controlled attack → integrity proof → technical drill-down`

# Final interpretation

SentinelWeights provides evidence about model-file security and integrity. It does not claim universal attack coverage, complete behavioural equivalence, medical safety, or clinical approval. Its strongest design principle is to state what was measured, show where controls fail, and use a separately trusted attestation baseline for statistical blind spots.
