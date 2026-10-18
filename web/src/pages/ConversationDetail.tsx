import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchConversation, fetchPolicy, MODE_NAMES, MODES, type AuditRecord, type Mode } from "../data";
import { AuditPanel } from "../components/AuditPanel";
import { ToolTimeline } from "../components/ToolTimeline";
import { Transcript, type TurnMark } from "../components/Transcript";
import { Loading, Segmented, useLoad } from "../components/ui";
import { preferredModel } from "./Overview";

export function buildMarks(audit: AuditRecord | undefined, truth: { kind: string; category: string; turn: number }[],
  names: Record<string, string>, showTruth: boolean): Record<number, TurnMark> {
  const marks: Record<number, TurnMark> = {};
  if (showTruth) {
    for (const it of truth) {
      const m = (marks[it.turn] ??= {});
      if (it.kind === "violation") m.planted = names[it.category];
      else m.near = names[it.category];
    }
  }
  for (const [cat, r] of Object.entries(audit?.categories ?? {})) {
    for (const f of r.findings) ((marks[f.turn] ??= {}).flagged ??= []).push(names[cat]);
  }
  return marks;
}

export default function ConversationDetail() {
  const { id = "" } = useParams();
  const [detail, err1] = useLoad(() => fetchConversation(id), [id]);
  const [policy, err2] = useLoad(fetchPolicy);
  const [mode, setMode] = useState<Mode>("agentic");
  const [showTruth, setShowTruth] = useState(true);
  const [active, setActive] = useState<number>();

  const model = useMemo(() => preferredModel(Object.keys(detail?.audits ?? {})), [detail]);
  if (!detail || !policy) return <Loading error={err1 ?? err2} />;
  const audits = model ? detail.audits[model] ?? {} : {};
  const available = MODES.filter((m) => audits[m]);
  const audit = audits[mode] ?? (available[0] ? audits[available[0]] : undefined);
  const truth = detail.ground_truth.items ?? [];
  const marks = buildMarks(audit, truth, policy.categories, showTruth);
  const meta = detail.conversation.meta as { subflow?: string; flow?: string };

  return (
    <>
      <p className="eyebrow"><Link to="/conversations">Conversations</Link> · {(meta.subflow ?? meta.flow ?? "").replaceAll("_", " ")}</p>
      <h1 className="title" style={{ fontSize: 34 }}>Chat #{detail.conversation.conv_id}</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        {detail.conversation.turns.length} turns ·{" "}
        {detail.ground_truth.plan === "clean" ? "left untouched (control)" :
          detail.ground_truth.plan === "near_miss" ? "one compliant near-miss planted" :
            `${truth.filter((t) => t.kind === "violation").length} violation(s) planted`}
      </p>
      <div className="toolbar">
        {available.length > 0 && <Segmented label="Method" value={audit?.mode ?? mode} onChange={setMode}
          options={available.map((m) => ({ value: m, label: MODE_NAMES[m] }))} />}
        <label className="small"><input type="checkbox" checked={showTruth} onChange={(e) => setShowTruth(e.target.checked)} /> Show planted turns</label>
      </div>
      <div className="split">
        <div className="card"><Transcript turns={detail.conversation.turns} marks={marks} active={active} /></div>
        <div className="sticky">
          <div className="card">
            <h2 className="headline">Audit</h2>
            {audit ? <AuditPanel audit={audit} categories={policy.categories} truth={truth} onSelect={setActive} />
              : <p className="small muted">This chat has not been audited yet.</p>}
          </div>
          {audit?.mode === "agentic" && (
            <div className="card" style={{ marginTop: 16 }}>
              <h2 className="headline">What the agent looked at</h2>
              <ToolTimeline calls={audit.tool_calls} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
