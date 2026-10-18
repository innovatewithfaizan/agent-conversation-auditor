import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchConversations, fetchPolicy, MODE_NAMES, MODES, type ConversationRow, type Mode } from "../data";
import { Loading, Segmented, SeverityPill, StatusPill, useLoad } from "../components/ui";
import { preferredModel } from "./Overview";

type Plan = "all" | "violations" | "near_miss" | "clean";

export function outcome(row: ConversationRow, flagged: string[] | undefined): { caught: number; missed: number; extra: number } {
  const planted = row.planted.filter((p) => p.kind === "violation").map((p) => p.category);
  const f = flagged ?? [];
  return {
    caught: planted.filter((c) => f.includes(c)).length,
    missed: planted.filter((c) => !f.includes(c)).length,
    extra: f.filter((c) => !planted.includes(c)).length,
  };
}

export default function ConversationList() {
  const [rows, err1] = useLoad(fetchConversations);
  const [policy, err2] = useLoad(fetchPolicy);
  const [plan, setPlan] = useState<Plan>("all");
  const [mode, setMode] = useState<Mode>("agentic");
  const navigate = useNavigate();

  const model = useMemo(() => {
    const models = new Set<string>();
    rows?.forEach((r) => Object.keys(r.audits ?? {}).forEach((m) => models.add(m)));
    return preferredModel([...models]);
  }, [rows]);

  if (!rows || !policy) return <Loading error={err1 ?? err2} />;
  const shown = rows.filter((r) => plan === "all" || r.plan === plan);

  return (
    <>
      <p className="eyebrow">Benchmark</p>
      <h1 className="large-title">Conversations</h1>
      <p className="lede">
        {rows.length} real support chats. Some were left untouched, some carry a compliant near-miss, and the rest have
        one or two planted violations. Open one to see the transcript, what was planted and what the auditor found.
      </p>
      <div className="toolbar">
        <Segmented label="Plan" value={plan} onChange={setPlan} options={[
          { value: "all", label: "All" }, { value: "violations", label: "Violations" },
          { value: "near_miss", label: "Near-misses" }, { value: "clean", label: "Clean" }]} />
        {model && <Segmented label="Method" value={mode} onChange={setMode}
          options={MODES.map((m) => ({ value: m, label: MODE_NAMES[m] }))} />}
        {model && <span className="small muted">Auditor: {model}</span>}
      </div>
      <div className="card" style={{ overflowX: "auto" }}>
        <table className="table">
          <thead>
            <tr><th>Chat</th><th className="hide-sm">Topic</th><th className="num">Turns</th><th>Planted</th><th>Auditor result</th></tr>
          </thead>
          <tbody>
            {shown.map((r) => {
              const flagged = model ? r.audits?.[model]?.[mode] : undefined;
              const o = outcome(r, flagged);
              return (
                <tr key={r.id} className="row-link" tabIndex={0} onClick={() => navigate(`/conversations/${r.id}`)}
                  onKeyDown={(e) => e.key === "Enter" && navigate(`/conversations/${r.id}`)}>
                  <td>#{r.id}</td>
                  <td className="muted hide-sm">{(r.subflow ?? r.flow ?? "").replaceAll("_", " ")}</td>
                  <td className="num">{r.turns}</td>
                  <td>
                    <div className="pills">
                      {r.planted.length === 0 && <span className="muted small">nothing (clean)</span>}
                      {r.planted.map((p, i) => p.kind === "near_miss"
                        ? <StatusPill key={i} kind="near">near-miss · {policy.categories[p.category]}</StatusPill>
                        : <span key={i} className="pills"><StatusPill kind="planted">{policy.categories[p.category]}</StatusPill><SeverityPill severity={p.severity} /></span>)}
                    </div>
                  </td>
                  <td>
                    {flagged === undefined ? <span className="muted small">not audited</span> : (
                      <div className="pills">
                        {o.caught > 0 && <StatusPill kind="hit">{o.caught} caught</StatusPill>}
                        {o.missed > 0 && <StatusPill kind="miss">{o.missed} missed</StatusPill>}
                        {o.extra > 0 && <StatusPill kind="false">{o.extra} extra flag{o.extra > 1 ? "s" : ""}</StatusPill>}
                        {o.caught + o.missed + o.extra === 0 && <span className="small muted">no flags, correct</span>}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
