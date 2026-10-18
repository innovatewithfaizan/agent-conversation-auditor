import type { AuditRecord, PlantedItem } from "../data";
import { SeverityPill, StatusPill } from "./ui";

/** Per-category result for one audit, compared with the planted ground truth
 * when there is one. Clicking a finding jumps to its turn. */
export function AuditPanel({ audit, categories, truth, onSelect }: {
  audit: AuditRecord; categories: Record<string, string>; truth?: PlantedItem[]; onSelect: (turn: number) => void;
}) {
  return (
    <div>
      {audit.summary && <p className="small">{audit.summary}</p>}
      {Object.entries(categories).map(([cat, name]) => {
        const r = audit.categories[cat];
        const planted = truth?.find((i) => i.category === cat && i.kind === "violation");
        const near = truth?.find((i) => i.category === cat && i.kind === "near_miss");
        const flagged = r.severity !== "none";
        return (
          <div className="cat" key={cat}>
            <div className="cat-head">
              <span className="headline" style={{ margin: 0 }}>{name}</span>
              <span className="pills">
                {planted && (flagged
                  ? <StatusPill kind="hit">caught</StatusPill>
                  : <StatusPill kind="miss">missed</StatusPill>)}
                {!planted && truth && flagged && <StatusPill kind="false">{near ? "near-miss flagged" : "extra flag"}</StatusPill>}
                <SeverityPill severity={r.severity} />
              </span>
            </div>
            {planted && (
              <p className="tiny muted" style={{ margin: "6px 0 0" }}>
                Planted: {planted.severity}, {planted.subtlety}, at turn #{planted.turn}
              </p>
            )}
            {r.findings.map((f, i) => (
              <button key={i} type="button" className="finding" onClick={() => onSelect(f.turn)}>
                <div className="tiny muted">Turn #{f.turn}</div>
                <q>{f.quote}</q>
                <div className="small muted" style={{ marginTop: 4 }}>{f.explanation}</div>
              </button>
            ))}
          </div>
        );
      })}
      <p className="tiny muted" style={{ marginTop: 16 }}>
        {audit.provider}/{audit.model} · effort {audit.effort} · {audit.usage.calls} calls ·{" "}
        {audit.usage.input_tokens.toLocaleString()} in / {audit.usage.output_tokens.toLocaleString()} out tokens ·{" "}
        ${audit.usage.cost_usd.toFixed(4)} at list price · {audit.seconds}s · {audit.tool_calls.length} tool calls
      </p>
    </div>
  );
}
