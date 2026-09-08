import { useState } from "react";
import AdversaryLab, { type AttackConfig } from "./AdversaryLab";
import { DetectionFrontier } from "./DetectionFrontier";
import { Icon, Section } from "./ui";

type Tab = "experiment" | "frontier";

export default function RedTeamWorkspace() {
  const [tab, setTab] = useState<Tab>("experiment");
  const [currentAttack, setCurrentAttack] = useState<AttackConfig | null>(null);

  return <>
    <div className="redteam-steps" role="tablist" aria-label="Red team workflow">
      <button type="button" role="tab" aria-selected={tab === "experiment"}
        className={tab === "experiment" ? "active" : ""} onClick={() => setTab("experiment")}>
        <span>1</span><div><strong>Live experiment</strong><small>Build and run one safe attack</small></div>
      </button>
      <span className="step-connector" aria-hidden="true" />
      <button type="button" role="tab" aria-selected={tab === "frontier"}
        className={tab === "frontier" ? "active" : ""} onClick={() => setTab("frontier")}>
        <span>2</span><div><strong>Detection frontier</strong><small>Compare it with 33 measured runs</small></div>
      </button>
    </div>

    {tab === "experiment" ? <Section title="Adversary Lab" subtitle="Configure an inert payload, preview its capacity, then run the real scan pipeline."
      tone="blush" icon={<Icon name="target" className="w-4 h-4" />}>
      <AdversaryLab onExperiment={(config) => setCurrentAttack(config)} onExploreFrontier={() => setTab("frontier")} />
    </Section> : <Section title="Detection frontier" subtitle="A finite, measured sweep—including the cases statistics misses."
      tone="lavender" icon={<Icon name="chart" className="w-4 h-4" />}>
      <DetectionFrontier currentAttack={currentAttack} />
    </Section>}
  </>;
}
