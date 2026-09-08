import { useEffect, useState } from "react";
import type { Report, SampleItem, ProgressEvent } from "./types";
import { PERSONAS, type PersonaId } from "./personas";
import * as api from "./api";
import { Section, Pill, bandColor, Icon, MetricCard, toneForBand } from "./components/ui";
import SampleGallery from "./components/SampleGallery";
import PipelineFunnel, { type StageState } from "./components/PipelineFunnel";
import RiskGauge from "./components/RiskGauge";
import CoverageConfidence from "./components/CoverageConfidence";
import VerdictBanner from "./components/VerdictBanner";
import CompareView from "./components/CompareView";
import BitPlaneHeatmap from "./components/BitPlaneHeatmap";
import EntropyProfileChart from "./components/EntropyProfileChart";
import PrecisionChart from "./components/PrecisionChart";
import LayerRiskBars from "./components/LayerRiskBars";
import PickleOpcodeViewer from "./components/PickleOpcodeViewer";
import TriggerViewer from "./components/TriggerViewer";
import DetectorContribs from "./components/DetectorContribs";
import BenchmarkDashboard from "./components/BenchmarkDashboard";
import EvidenceTimeline from "./components/EvidenceTimeline";
import PatientImpactCard from "./components/PatientImpactCard";
import BlastRadiusGraph from "./components/BlastRadiusGraph";
import RemediationPanel from "./components/RemediationPanel";
import MLBOMPanel from "./components/MLBOMPanel";
import NarrativePanel from "./components/NarrativePanel";
import DemoTour from "./components/DemoTour";
import RedTeamWorkspace from "./components/RedTeamWorkspace";
import AttestationPanel from "./components/AttestationPanel";
import MeasuredLineage from "./components/MeasuredLineage";
import AblationPanel from "./components/AblationPanel";
import HoldoutPanel from "./components/HoldoutPanel";
import SampledScanPanel from "./components/SampledScanPanel";

type ViewId = "scan" | "evidence" | "redteam" | "proof" | "lab";

const VIEWS: { id: ViewId; label: string; hint: string; icon: string }[] = [
  { id: "scan", label: "Scan", hint: "Intake and gate", icon: "scan" },
  { id: "evidence", label: "Evidence", hint: "Timeline, BOM, benchmark", icon: "file" },
  { id: "redteam", label: "Red team", hint: "Forge an attack live", icon: "target" },
  { id: "proof", label: "Proof", hint: "Attestation and ablation", icon: "lock" },
  { id: "lab", label: "Lab", hint: "Every panel", icon: "flask" },
];

const TABS = [
  { id: "heatmap", label: "Heatmap" },
  { id: "entropy", label: "Entropy" },
  { id: "precision", label: "Precision" },
  { id: "layerbars", label: "Layers" },
  { id: "opcodes", label: "Opcodes" },
  { id: "trigger", label: "Trigger" },
  { id: "contribs", label: "Weights" },
  { id: "narrative", label: "Narrative" },
];

const DEMO_TAB: Record<string, string> = {
  clean: "narrative",
  vendor_reexport: "opcodes",
  borderline_backdoor: "trigger",
  backdoor_toycnn: "trigger",
  stego_contiguous: "heatmap",
  stego_scattered: "heatmap",
  stego_silent: "heatmap",
  pickle_fixture: "opcodes",
  zip_slip: "opcodes",
  public_clean: "narrative",
  quantized_clean: "narrative",
  truncated: "narrative",
  malformed: "narrative",
};

const STEGO_IDS = ["stego_contiguous", "stego_scattered", "stego_silent"];
const PICKLE_IDS = ["pickle_fixture", "zip_slip", "vendor_reexport"];
const BACKDOOR_IDS = ["backdoor_toycnn", "borderline_backdoor"];
const BENIGN_IDS = ["public_clean", "quantized_clean"];
const FAILSAFE_IDS = ["malformed", "truncated"];

export default function App() {
  const [samples, setSamples] = useState<SampleItem[]>([]);
  const [methodology, setMethodology] = useState<string>("");
  const [scanId, setScanId] = useState<string>("");
  const [fileInfo, setFileInfo] = useState<any>(null);
  const [stages, setStages] = useState<Record<string, StageState>>({});
  const [report, setReport] = useState<Report | null>(null);
  const [activeSample, setActiveSample] = useState<string>("");
  const [replay, setReplay] = useState(false);
  const [persona, setPersona] = useState<PersonaId>("security");
  const [tab, setTab] = useState("heatmap");
  const [bench, setBench] = useState<any>(null);
  const [scanning, setScanning] = useState(false);
  const [view, setView] = useState<ViewId>(() => {
    const q = new URLSearchParams(window.location.search).get("view");
    return VIEWS.some((v) => v.id === q) ? (q as ViewId) : "scan";
  });

  const isScanView = view === "scan";
  const isEvidenceView = view === "evidence";
  const isLabView = view === "lab";
  const showPipeline = isScanView || isLabView;
  const showEvidencePanels = isEvidenceView || isLabView;

  useEffect(() => {
    api.listSamples().then((s: any) => {
      setSamples(s?.samples || []);
      setMethodology(s?.methodology || "");
    }).catch(() => {});
    api.getBenchmark().then(setBench).catch(() => {});
  }, []);

  async function startScan(opts: { sampleId?: string; file?: File }, sampleId?: string) {
    setReport(null);
    setStages({});
    setScanning(true);
    setActiveSample(sampleId || "");
    if (sampleId && DEMO_TAB[sampleId]) setTab(DEMO_TAB[sampleId]);
    try {
      const info = await api.createScan(opts);
      setFileInfo(info);
      setScanId(info.scan_id);
      api.streamScan(
        info.scan_id,
        (e: ProgressEvent) => {
          setStages((prev) => ({
            ...prev,
            [e.stage]: { status: e.status || "running", elapsed_ms: e.elapsed_ms, summary: e.summary },
          }));
          if (e.stage === "tier0" && e.cached) setReplay(false);
        },
        (rep) => {
          setReport(rep);
          setReplay(!!rep.replay);
          setScanning(false);
          setStages((prev) => {
            const next = { ...prev };
            ["tier0", "tier1", "tier2", "tier3", "tier4"].forEach((t) => {
              if (!next[t]) next[t] = { status: "idle" };
            });
            return next;
          });
        },
        (msg) => {
          setScanning(false);
          console.error(msg);
        }
      );
    } catch (e) {
      setScanning(false);
      console.error(e);
    }
  }

  const activePersona = PERSONAS.find((p) => p.id === persona)!;
  const show = (id: string) => (isLabView ? activePersona.sections.includes(id) : true);
  const narratives = (report as any)?.narratives || [];
  const isStego = STEGO_IDS.includes(activeSample);
  const isPickle = PICKLE_IDS.includes(activeSample);
  const isBackdoor = BACKDOOR_IDS.includes(activeSample);
  const isPublic = BENIGN_IDS.includes(activeSample);
  const isFailsafe = FAILSAFE_IDS.includes(activeSample);

  const verdictTone = toneForBand(report?.verdict.color);
  const gatesCovered = new Set(
    samples.map((s) => s.expected_verdict?.gate).filter(Boolean)
  ).size;
  const auc = bench?.roc?.auc;

  return (
    <div className="min-h-screen p-3 md:p-5">
      <div className="shell glass flex h-[calc(100vh-1.5rem)] md:h-[calc(100vh-2.5rem)]">
        {/* ------------------------------- rail ------------------------------- */}
        <aside className="w-[248px] shrink-0 flex flex-col px-3.5 py-5 relative overflow-hidden bg-gradient-to-b from-[#1D1A17] via-[#14110F] to-[#181C22]">
          <div
            className="absolute -top-16 -left-10 w-56 h-56 rounded-full blur-3xl opacity-25 animate-float"
            style={{ background: "radial-gradient(circle, #6366F1 0%, transparent 70%)" }}
          />
          <div
            className="absolute bottom-10 -right-14 w-56 h-56 rounded-full blur-3xl opacity-20 animate-float"
            style={{ background: "radial-gradient(circle, #0E9F7E 0%, transparent 70%)", animationDelay: "2s" }}
          />

          <div className="relative flex items-center gap-2.5 px-1.5 mb-7">
            <img src="/img/sentinel-mark.svg" alt="" className="w-9 h-9 animate-scale-in" />
            <div>
              <div className="display text-[21px] leading-none tracking-tight text-paper-card">Sentinel</div>
              <div className="text-[10.5px] text-white/40 mt-1 tracking-[0.14em] uppercase">Weights</div>
            </div>
          </div>

          <nav className="relative mb-6 space-y-1">
            {VIEWS.map((v, i) => {
              const on = view === v.id;
              return (
                <button
                  key={v.id}
                  onClick={() => setView(v.id)}
                  style={{ animationDelay: `${i * 45}ms` }}
                  className={`w-full text-left px-2.5 py-2 rounded-xl flex items-center gap-2.5 animate-slide-right press transition-all duration-300 ${
                    on
                      ? "bg-white text-ink shadow-lift"
                      : "text-white/55 hover:bg-white/10 hover:text-white hover:translate-x-0.5"
                  }`}
                >
                  <span
                    className={`w-7 h-7 rounded-lg grid place-items-center shrink-0 transition-colors ${
                      on ? "bg-ink text-paper-card" : "bg-white/10 text-white/70"
                    }`}
                  >
                    <Icon name={v.icon} className="w-3.5 h-3.5" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[13px] leading-none">{v.label}</span>
                    <span
                      className={`block text-[10.5px] mt-1 leading-none truncate ${
                        on ? "text-ink-400" : "text-white/30"
                      }`}
                    >
                      {v.hint}
                    </span>
                  </span>
                </button>
              );
            })}
          </nav>

          {view === "redteam" ? (
            <div className="relative flex-1 px-2">
              <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-3.5">
                <div className="flex items-center gap-2 text-white/85 text-[12px] font-medium">
                  <span className="w-7 h-7 rounded-lg bg-mint/15 text-mint grid place-items-center"><Icon name="shield" className="w-3.5 h-3.5" /></span>
                  Safe attack host
                </div>
                <p className="text-[11px] text-white/40 leading-relaxed mt-2">Each run starts from the clean baseline in memory. The source model is never overwritten.</p>
                <button className="mt-3 text-[11px] text-white/65 hover:text-white underline underline-offset-4" onClick={() => setView("scan")}>View the full model gallery</button>
              </div>
            </div>
          ) : <>
            <div className="relative flex items-center justify-between px-2 mb-2">
              <span className="text-[10.5px] uppercase tracking-[0.16em] text-white/35">Demo models · expected gate</span>
              <span className="text-[10.5px] text-white/30 tabular-nums">{samples.length}</span>
            </div>
            <div className="relative flex-1 overflow-auto -mx-1 px-1">
              <SampleGallery samples={samples} activeId={activeSample} compact
                onSelect={(s) => startScan({ sampleId: s.id }, s.id)} onUpload={(f) => startScan({ file: f })} />
            </div>
          </>}

          <div className="relative px-2 pt-4 mt-3 border-t border-white/10">
            <div className="text-[12.5px] text-white/80">Precision Care Challenge</div>
            <div className="text-[10.5px] text-white/35 mt-0.5">Offline prototype · demo attestation</div>
          </div>
        </aside>

        {/* ------------------------------ content ------------------------------ */}
        <div className="flex-1 min-w-0 flex flex-col bg-paper/70">
          <header className="h-[70px] px-7 flex items-center justify-between border-b border-paper-line/70 bg-paper-card/60 backdrop-blur-xl shrink-0">
            <div className="min-w-0">
              <div className="display text-[23px] leading-none tracking-tight text-gradient">
                {VIEWS.find((v) => v.id === view)!.label}
              </div>
              <div className="text-[12px] text-ink-400 mt-1.5 tabular-nums truncate">
                {view === "redteam"
                  ? "Author an attack against our own detector"
                  : view === "proof"
                  ? "The claims a reviewer should not have to take on trust"
                  : isEvidenceView
                  ? report
                    ? `Evidence bundle · ${fileInfo?.filename ?? "scan"} · ${report.total_ms ?? "?"} ms`
                    : "Run a scan first — timeline, BOM, and benchmark live here"
                  : fileInfo
                  ? `${fileInfo.filename} · ${fileInfo.format} · ${(fileInfo.size / 1024).toFixed(0)} KB`
                  : "Select a model in the rail"}
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {isLabView && (
                <div className="flex gap-1 p-1 rounded-full bg-paper border border-paper-line">
                  {PERSONAS.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setPersona(p.id)}
                      className={`text-[12px] px-2.5 py-1 rounded-full press transition-all duration-300 ${
                        persona === p.id
                          ? "bg-ink text-paper-card shadow-lift"
                          : "text-ink-400 hover:text-ink"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              )}
              <span
                className={`text-[12px] px-3 py-1.5 rounded-full border flex items-center gap-2 transition-colors ${
                  scanning
                    ? "border-lavender/40 bg-lavender-dim text-lavender"
                    : replay
                    ? "border-butter/40 bg-butter-dim text-butter"
                    : "border-mint/40 bg-mint-dim text-mint"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${scanning ? "animate-blink" : ""}`}
                  style={{ background: "currentColor" }}
                />
                {scanning ? "Scanning" : replay ? "Stored snapshot" : "Ready"}
              </span>

              <div className="flex items-center gap-2.5 pl-3 ml-1 border-l border-paper-line animate-fade-in">
                <img
                  src="/img/ge-logo.png"
                  alt="GE"
                  className="w-8 h-8 rounded-full shrink-0 transition-transform duration-500 hover:rotate-6 hover:scale-105"
                />
                <div className="leading-none">
                  <div className="text-[12.5px] font-medium tracking-[0.02em] text-ink">
                    GE HEALTHCARE
                  </div>
                  <div className="text-[10px] text-ink-400 mt-1 tracking-[0.14em] uppercase">
                    Precision Care
                  </div>
                </div>
              </div>
            </div>
          </header>

          <main key={view} className="flex-1 overflow-auto px-7 py-6 space-y-5 animate-fade-in">
            {/* ---------------------- hero metric strip ---------------------- */}
            {isScanView && (
              <div className="grid lg:grid-cols-4 gap-4">
                <MetricCard
                  label="Model risk"
                  value={report ? report.verdict.risk_score : "—"}
                  unit="/ 100"
                  filled={report ? report.verdict.risk_score / 100 : 0}
                  badge={report ? report.verdict.gate.replace(/_/g, " ") : "Idle"}
                  tone={report ? (verdictTone as any) : "lavender"}
                  icon={<Icon name="shield" className="w-4 h-4" />}
                  delay={0}
                />
                <MetricCard
                  label="Scan coverage"
                  value={report ? report.coverage.confidence_pct : "—"}
                  unit="%"
                  filled={report ? report.coverage.confidence_pct / 100 : 0}
                  badge={report ? `${report.coverage.executed}/${report.coverage.applicable}` : "—"}
                  tone="sky"
                  icon={<Icon name="layers" className="w-4 h-4" />}
                  delay={70}
                />
                <MetricCard
                  label="Gallery gates"
                  value={gatesCovered || "—"}
                  unit="of 5"
                  filled={gatesCovered / 5}
                  badge={`${samples.length} models`}
                  tone="mint"
                  icon={<Icon name="network" className="w-4 h-4" />}
                  delay={140}
                />
                <div
                  className="card card-dark shine reveal p-5 flex flex-col justify-between anim-delay-3"
                  style={{ animationDelay: "210ms" }}
                >
                  <div>
                    <div className="flex items-center gap-2 mb-2.5">
                      <span className="w-8 h-8 rounded-lg grid place-items-center bg-white/10 text-white/80">
                        <Icon name="spark" className="w-4 h-4" />
                      </span>
                      <span className="text-[11px] uppercase tracking-[0.14em] text-white/40">
                        Zero trust
                      </span>
                    </div>
                    <div className="display text-[19px] leading-tight text-paper-card">
                      Every model guilty until statistically cleared
                    </div>
                    <p className="text-[12px] text-white/45 mt-1.5 leading-relaxed">
                      {auc != null ? `Benchmark AUC ${auc}` : "Benchmark loading"} · pickle never executed
                    </p>
                  </div>
                  <button
                    onClick={() => setView("redteam")}
                    className="mt-4 w-full h-9 rounded-full bg-paper-card text-ink text-[12.5px] press hover:bg-white transition-colors flex items-center justify-center gap-1.5"
                  >
                    Attack it yourself
                    <Icon name="target" className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}

            {isScanView && (
              <Section
                title="Ninety-second path"
                subtitle="Guided gallery — each sample lands on a different gate"
                tone="butter"
                icon={<Icon name="spark" className="w-4 h-4" />}
                delay={40}
              >
                <DemoTour
                  activeId={activeSample}
                  onSelect={(id) => startScan({ sampleId: id }, id)}
                />
              </Section>
            )}

            {showPipeline && (
              <Section
                title="Pipeline"
                subtitle="Cheapest check first. Tier 1 can stop the rest."
                tone="lavender"
                icon={<Icon name="layers" className="w-4 h-4" />}
                delay={80}
                right={
                  scanning ? (
                    <Pill color="#6366F1" pulse>
                      Running
                    </Pill>
                  ) : undefined
                }
              >
                <PipelineFunnel stages={stages} />
                {!fileInfo && (
                  <p className="text-[13px] text-ink-400 mt-4">Choose a model in the rail to start.</p>
                )}
              </Section>
            )}

            {showPipeline && report && (
              <div className="grid lg:grid-cols-5 gap-5">
                <Section
                  title="Risk"
                  subtitle={`${report.total_ms ?? "?"} ms end to end`}
                  className="lg:col-span-2"
                  tone={verdictTone}
                  icon={<Icon name="shield" className="w-4 h-4" />}
                  delay={0}
                >
                  <RiskGauge score={report.verdict.risk_score} color={report.verdict.color} />
                  <div className="mt-4">
                    <CoverageConfidence coverage={report.coverage} />
                  </div>
                </Section>
                <Section
                  title="Gate"
                  subtitle="Release language is conservative"
                  className="lg:col-span-3"
                  tone="plain"
                  icon={<Icon name="lock" className="w-4 h-4" />}
                  delay={90}
                >
                  <VerdictBanner verdict={report.verdict} />
                  {report.findings.length > 0 && (
                    <div className="mt-3 space-y-2 max-h-40 overflow-auto pr-1">
                      {report.findings.map((f, i) => (
                        <div
                          key={i}
                          style={{ animationDelay: `${i * 50}ms` }}
                          className="flex items-start gap-2 text-[12px] animate-slide-right rounded-lg px-2 py-1.5 hover:bg-paper transition-colors"
                        >
                          <Pill color={bandColor[f.severity === "CRITICAL" ? "red" : "amber"]}>
                            {f.severity}
                          </Pill>
                          <span className="text-ink-400 tabular-nums">{f.code}</span>
                          <span className="text-ink">{f.message}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </Section>
              </div>
            )}

            {report && isScanView && (
              <>
                {isStego && (
                  <Section
                    title="Sibling compare"
                    subtitle="Same architecture, opposite gate"
                    tone="sky"
                    icon={<Icon name="network" className="w-4 h-4" />}
                  >
                    <CompareView
                      a="clean"
                      b={activeSample === "clean" ? "stego_contiguous" : activeSample}
                    />
                  </Section>
                )}
                {isStego && (
                  <Section
                    title="Where"
                    subtitle="Local entropy along the tensor"
                    tone="blush"
                    icon={<Icon name="chart" className="w-4 h-4" />}
                  >
                    <BitPlaneHeatmap detectors={report.detectors} />
                  </Section>
                )}
                {isPickle && (
                  <Section
                    title="Opcodes"
                    subtitle="Disassembled. Never executed."
                    tone="blush"
                    icon={<Icon name="alert" className="w-4 h-4" />}
                  >
                    <PickleOpcodeViewer detectors={report.detectors} findings={report.findings} />
                  </Section>
                )}
                {isBackdoor && (
                  <Section
                    title="Trigger"
                    subtitle="Synthetic probe — not a clinical model"
                    tone="butter"
                    icon={<Icon name="target" className="w-4 h-4" />}
                  >
                    <TriggerViewer detectors={report.detectors} />
                  </Section>
                )}
                {isPublic && (
                  <Section
                    title="Not a false alarm"
                    subtitle="Third-party or legitimate quantization"
                    tone="mint"
                    icon={<Icon name="shield" className="w-4 h-4" />}
                  >
                    <p className="text-[13px] text-ink-600 mb-3 leading-relaxed">
                      {activeSample === "public_clean"
                        ? "This file is not from our LSB training recipe. Int8 edge-quantized fixture."
                        : "Legitimate low-precision export. The scanner does not treat quantization as tamper."}
                    </p>
                    <NarrativePanel narratives={narratives} />
                  </Section>
                )}
                {isFailsafe && (
                  <Section
                    title="Fail-safe"
                    subtitle="Unable to establish safety"
                    tone="butter"
                    icon={<Icon name="alert" className="w-4 h-4" />}
                  >
                    <NarrativePanel narratives={narratives} />
                  </Section>
                )}
                {activeSample === "clean" && (
                  <Section
                    title="Why this gate"
                    subtitle="Tied to detector output"
                    tone="mint"
                    icon={<Icon name="book" className="w-4 h-4" />}
                  >
                    <NarrativePanel narratives={narratives} />
                  </Section>
                )}
                {(activeSample === "pickle_fixture" || activeSample === "zip_slip") && scanId && (
                  <Section
                    title="Convert format"
                    subtitle="Teaching moment — pickle never executed"
                    tone="sky"
                    icon={<Icon name="file" className="w-4 h-4" />}
                  >
                    <RemediationPanel scanId={scanId} />
                  </Section>
                )}
                {isStego && scanId && (
                  <Section
                    title="Sanitize"
                    subtitle="Experimental. Human keeps approval."
                    tone="lavender"
                    icon={<Icon name="flask" className="w-4 h-4" />}
                  >
                    <RemediationPanel scanId={scanId} />
                  </Section>
                )}
              </>
            )}

            {view === "redteam" && <RedTeamWorkspace />}

            {view === "proof" && (
              <>
                <Section
                  title="Weight-level attestation"
                  subtitle="Merkle root over per-tensor hashes, signed and ledgered"
                  tone="mint"
                  icon={<Icon name="lock" className="w-4 h-4" />}
                >
                  <AttestationPanel />
                </Section>
                <Section
                  title="Measured lineage"
                  subtitle="Computed from tensor hashes, not drawn by hand"
                  tone="sky"
                  icon={<Icon name="network" className="w-4 h-4" />}
                  delay={60}
                >
                  <MeasuredLineage />
                </Section>
                <Section
                  title="Detector ablation and alternative controls"
                  subtitle="What each detector earns, and what existing tooling would have caught"
                  tone="lavender"
                  icon={<Icon name="chart" className="w-4 h-4" />}
                  delay={120}
                >
                  <AblationPanel />
                </Section>
                <Section
                  title="Sealed holdout"
                  subtitle="A recipe we did not calibrate against"
                  tone="butter"
                  icon={<Icon name="flask" className="w-4 h-4" />}
                  delay={180}
                >
                  <HoldoutPanel />
                </Section>
                <Section
                  title="Scale: sampled triage"
                  subtitle="Large artifact built and scanned here, with an interval"
                  tone="blush"
                  icon={<Icon name="layers" className="w-4 h-4" />}
                  delay={240}
                >
                  <SampledScanPanel />
                </Section>
              </>
            )}

            {isEvidenceView && !report && (
              <Section
                title="No scan yet"
                subtitle="Evidence attaches to a completed scan"
                tone="sky"
                icon={<Icon name="file" className="w-4 h-4" />}
              >
                <p className="text-[13px] text-ink-600 leading-relaxed">
                  Pick a model from the rail or switch to <strong>Scan</strong> and run the guided tour.
                  This view shows the audit trail — stage timings, ML-BOM, benchmark corpus, and
                  supply-chain context — not the live intake funnel.
                </p>
              </Section>
            )}

            {report && isEvidenceView && (
              <div className="grid lg:grid-cols-5 gap-5">
                <Section
                  title="Verdict snapshot"
                  subtitle="For the evidence bundle"
                  className="lg:col-span-2"
                  tone={verdictTone}
                  icon={<Icon name="shield" className="w-4 h-4" />}
                >
                  <RiskGauge score={report.verdict.risk_score} color={report.verdict.color} />
                </Section>
                <Section
                  title="Gate language"
                  subtitle="Conservative release wording"
                  className="lg:col-span-3"
                  icon={<Icon name="lock" className="w-4 h-4" />}
                  delay={80}
                >
                  <VerdictBanner verdict={report.verdict} />
                </Section>
              </div>
            )}

            {report && isLabView && (
              <Section title="Drill-down" tone="lavender" icon={<Icon name="flask" className="w-4 h-4" />}>
                <div className="flex flex-wrap gap-1.5 mb-4">
                  {TABS.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setTab(t.id)}
                      className={`text-[12px] px-3 py-1.5 rounded-full border press transition-all duration-300 ${
                        tab === t.id
                          ? "border-ink bg-ink text-paper-card shadow-lift"
                          : "border-paper-line text-ink-600 hover:border-ink/30 hover:-translate-y-0.5"
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
                <div key={tab} className="min-h-[220px] animate-fade-up">
                  {tab === "heatmap" && <BitPlaneHeatmap detectors={report.detectors} />}
                  {tab === "entropy" && <EntropyProfileChart detectors={report.detectors} />}
                  {tab === "precision" && <PrecisionChart detectors={report.detectors} />}
                  {tab === "layerbars" && <LayerRiskBars detectors={report.detectors} />}
                  {tab === "opcodes" && (
                    <PickleOpcodeViewer detectors={report.detectors} findings={report.findings} />
                  )}
                  {tab === "trigger" && <TriggerViewer detectors={report.detectors} />}
                  {tab === "contribs" && <DetectorContribs fusion={report.fusion} />}
                  {tab === "narrative" && <NarrativePanel narratives={narratives} />}
                </div>
              </Section>
            )}

            {report && isLabView && show("compare") && (
              <Section title="Sibling compare" tone="sky" icon={<Icon name="network" className="w-4 h-4" />}>
                <CompareView a="clean" b="stego_contiguous" />
              </Section>
            )}

            {showEvidencePanels && (
              <div className="space-y-5">
                {methodology && (
                  <Section
                    title="Sample contract"
                    subtitle="How the gallery was built"
                    tone="butter"
                    icon={<Icon name="book" className="w-4 h-4" />}
                  >
                    <p className="text-[13px] text-ink-600 leading-relaxed">{methodology}</p>
                  </Section>
                )}
                {report && (
                  <Section
                    title="Scan timeline"
                    subtitle="Elapsed per stage — measured this run"
                    tone="lavender"
                    icon={<Icon name="clock" className="w-4 h-4" />}
                    delay={60}
                  >
                    <EvidenceTimeline timeline={report.timeline} />
                  </Section>
                )}
                {report && isEvidenceView && isStego && (
                  <Section
                    title="Sibling compare"
                    subtitle="Same architecture, opposite gate — evidence for judges"
                    tone="sky"
                    icon={<Icon name="network" className="w-4 h-4" />}
                  >
                    <CompareView
                      a="clean"
                      b={activeSample === "clean" ? "stego_contiguous" : activeSample}
                    />
                  </Section>
                )}
                <div className="grid lg:grid-cols-2 gap-5">
                  {report && (
                    <Section
                      title="Supply chain"
                      subtitle="Non-clinical"
                      tone="mint"
                      icon={<Icon name="network" className="w-4 h-4" />}
                    >
                      <PatientImpactCard report={report} />
                    </Section>
                  )}
                  {report && (
                    <Section
                      title="Blast radius"
                      subtitle="Illustrative downstream products — measured lineage lives in Proof"
                      tone="blush"
                      icon={<Icon name="alert" className="w-4 h-4" />}
                      delay={60}
                    >
                      <BlastRadiusGraph verdict={report.verdict} />
                    </Section>
                  )}
                  {report && scanId && isLabView && (
                    <Section title="Remediation" tone="sky" icon={<Icon name="flask" className="w-4 h-4" />}>
                      <RemediationPanel scanId={scanId} />
                    </Section>
                  )}
                  {report && (
                    <Section
                      title="ML-BOM"
                      subtitle="Signed report export lives here"
                      tone="lavender"
                      icon={<Icon name="file" className="w-4 h-4" />}
                      delay={120}
                    >
                      <MLBOMPanel report={report} scanId={scanId} />
                    </Section>
                  )}
                </div>
                <Section
                  title="Benchmark"
                  subtitle="Full pipeline. Policy band is the operating point."
                  tone="plain"
                  icon={<Icon name="chart" className="w-4 h-4" />}
                >
                  <BenchmarkDashboard bench={bench} />
                </Section>
              </div>
            )}

            <Section title="Limits" tone="plain" icon={<Icon name="alert" className="w-4 h-4" />}>
              <ul className="text-[13px] text-ink-600 space-y-1.5 leading-relaxed">
                {(report?.disclaimers || [
                  "Reports “no indicators within scan scope,” never “proven safe.”",
                  "Thresholds/weights are fixed demo values, exposed on screen.",
                  "Backdoor detection runs on a labeled synthetic model.",
                  "Signing uses a local demo key (real Ed25519), not production PKI.",
                  "Security clearance is separate from clinical validation.",
                ]).map((d, i) => (
                  <li key={i} className="flex gap-2.5">
                    <span
                      className="mt-[7px] w-1 h-1 rounded-full shrink-0"
                      style={{ background: "#8A8278" }}
                    />
                    <span>{d}</span>
                  </li>
                ))}
              </ul>
            </Section>
          </main>
        </div>
      </div>
    </div>
  );
}
