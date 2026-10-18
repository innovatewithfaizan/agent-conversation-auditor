import { useState } from "react";
import { MODE_NAMES, pct, type Metrics, type Mode } from "../data";

const COLORS: Record<Mode, string> = { full: "var(--series-full)", rag: "var(--series-rag)", agentic: "var(--series-agentic)" };

/** Recall by category, one bar per mode. Bars have value labels and a hover
 * tooltip; the table on the same page carries the exact numbers. */
export function RecallChart({ metrics, categories }: { metrics: Metrics; categories: Record<string, string> }) {
  const modes = (["full", "rag", "agentic"] as Mode[]).filter((m) => metrics.modes[m]);
  const cats = Object.keys(categories);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const W = 760, H = 240, left = 36, bottom = 44, top = 12;
  const plotH = H - bottom - top;
  const group = (W - left) / cats.length;
  const bar = Math.min(28, (group - 24) / modes.length);

  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Recall of planted violations by category and method">
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line className="grid-line" x1={left} x2={W} y1={top + plotH * (1 - v)} y2={top + plotH * (1 - v)} />
            <text x={left - 8} y={top + plotH * (1 - v) + 4} textAnchor="end">{v * 100}%</text>
          </g>
        ))}
        {cats.map((cat, ci) => {
          const x0 = left + ci * group + (group - bar * modes.length - 2 * (modes.length - 1)) / 2;
          return (
            <g key={cat}>
              {modes.map((m, mi) => {
                const c = metrics.modes[m]!.categories[cat];
                const none = c.recall === null || Number.isNaN(c.recall);  // nothing planted in this category
                const v: number = c.recall === null || Number.isNaN(c.recall) ? 0 : c.recall;
                const h = none ? 0 : Math.max(plotH * v, 1);
                const x = x0 + mi * (bar + 2);
                const text = none ? `${categories[cat]}: nothing planted, so recall is undefined`
                  : `${categories[cat]} · ${MODE_NAMES[m]}: ${pct(c.recall)} (${c.tp} of ${c.tp + c.fn} caught)`;
                return (
                  <g key={m}
                    onMouseMove={(e) => setTip({ x: e.clientX + 12, y: e.clientY + 12, text })}
                    onMouseLeave={() => setTip(null)}>
                    <rect x={x - 4} y={top} width={bar + 8} height={plotH} fill="transparent" />
                    {!none && <rect x={x} y={top + plotH - h} width={bar} height={h} rx={4} fill={COLORS[m]} />}
                    {!none && <text x={x + bar / 2} y={top + plotH - h - 5} textAnchor="middle" fontSize="11">{Math.round(v * 100)}</text>}
                  </g>
                );
              })}
              <text x={left + ci * group + group / 2} y={H - bottom + 20} textAnchor="middle">{categories[cat].split(" ")[0]}</text>
              {modes.every((m) => metrics.modes[m]!.categories[cat].recall === null) && (
                <text x={left + ci * group + group / 2} y={top + plotH - 8} textAnchor="middle" fontSize="11">nothing planted</text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {modes.map((m) => <span key={m} style={{ ["--swatch" as string]: COLORS[m] }}>{MODE_NAMES[m]}</span>)}
      </div>
      {tip && <div className="tooltip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
    </div>
  );
}
