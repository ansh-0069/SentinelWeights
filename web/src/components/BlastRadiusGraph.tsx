import { bandColor } from "./ui";
import type { Verdict } from "../types";

const APPS = [
  { id: "ct", label: "CT Recon", y: 30 },
  { id: "xray", label: "Chest X-ray Triage", y: 80 },
  { id: "us", label: "Ultrasound Assist", y: 130 },
  { id: "monitor", label: "Patient Monitor", y: 180 },
];

export default function BlastRadiusGraph({ verdict }: { verdict: Verdict }) {
  const risky = verdict.band === "SUSPICIOUS" || verdict.band === "DANGEROUS";
  const c = risky ? bandColor[verdict.color] : "#1F6F5B";
  return (
    <div>
      <p className="text-[13px] text-ink-600 mb-3 leading-relaxed">
        Illustrative lineage — one backbone fans out. A single compromise inherits everywhere.
      </p>
      <svg width="100%" viewBox="0 0 420 210" className="max-w-full">
        {APPS.map((a) => (
          <line key={a.id} x1="120" y1="105" x2="290" y2={a.y}
            stroke={risky ? c : "#E6E0D6"} strokeWidth={risky ? 2 : 1} />
        ))}
        <g>
          <circle cx="80" cy="105" r="34" fill={`${c}18`} stroke={c} strokeWidth="1.5" />
          <text x="80" y="101" textAnchor="middle" fontSize="11" fill={c}>Backbone</text>
          <text x="80" y="116" textAnchor="middle" fontSize="9" fill="#8A8278">scanned</text>
        </g>
        {APPS.map((a) => (
          <g key={a.id}>
            <rect x="290" y={a.y - 13} width="120" height="26" rx="8"
              fill={risky ? `${c}12` : "#FFFcf8"} stroke={risky ? c : "#E6E0D6"} />
            <text x="350" y={a.y + 4} textAnchor="middle" fontSize="10" fill={risky ? c : "#5C564E"}>
              {a.label}
            </text>
          </g>
        ))}
      </svg>
      {risky && (
        <p className="text-[13px] mt-2" style={{ color: c }}>
          {APPS.length} downstream products would inherit this risk if released.
        </p>
      )}
    </div>
  );
}
