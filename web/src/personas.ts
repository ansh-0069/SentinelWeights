export type PersonaId = "executive" | "security" | "mleng" | "regulatory";

export interface Persona {
  id: PersonaId;
  label: string;
  blurb: string;
  // which detail sections to emphasize
  sections: string[];
}

export const PERSONAS: Persona[] = [
  {
    id: "executive",
    label: "Executive",
    blurb: "Risk, affected assets, release decision.",
    sections: ["verdict", "patient", "blast", "compare"],
  },
  {
    id: "security",
    label: "Security",
    blurb: "Findings, opcodes, ATLAS mapping.",
    sections: ["verdict", "findings", "opcodes", "contribs", "atlas"],
  },
  {
    id: "mleng",
    label: "ML-Engineer",
    blurb: "Heatmaps, Δk, statistics.",
    sections: ["verdict", "heatmap", "entropy", "precision", "layerbars", "compare", "perf"],
  },
  {
    id: "regulatory",
    label: "Regulatory",
    blurb: "Evidence timeline, coverage, signed artifact.",
    sections: ["verdict", "timeline", "coverage", "mlbom", "atlas"],
  },
];
