import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchMetrics, fetchPolicy, MODE_NAMES, MODES, pct, type Mode } from "../data";
import { RecallChart } from "../components/RecallChart";
import { Loading, MetricTile, Segmented, useLoad } from "../components/ui";

export function preferredModel(models: string[]): string | undefined {
  return models.find((m) => m === "gpt-5-mini") ?? models[0];
}

export default function Overview() {
  const [metrics, err1] = useLoad(fetchMetrics);
  const [policy, err2] = useLoad(fetchPolicy);
  const [model, setModel] = useState<string>();
  const [mode, setMode] = useState<Mode>("agentic");

  if (!metrics || !policy) return <Loading error={err1 ?? err2} />;
  const models = Object.keys(metrics);
  const current = metrics[model ?? preferredModel(models) ?? ""];
  const m = current?.modes[mode];
  const available = MODES.filter((x) => current?.modes[x]);

  return (
    <>
      <section>
        <p className="eyebrow">Agentic RAG · compliance auditing</p>
        <h1 className="large-title">Did the agent follow the policy?</h1>
        <p className="lede">
          An AI auditor reads customer-support conversations, checks them against a written policy, and cites the exact
          turn behind every finding. We plant known violations into real chats, so every score below is measured
          against ground truth.
        </p>
        <div className="toolbar">
          <Link className="button" to="/conversations">Browse audited conversations</Link>
          <Link className="button secondary" to="/audit">Try a live audit</Link>
        </div>
      </section>

      {!current ? (
        <section><p className="notice">No evaluation results yet. Run the benchmark, then <code>python -m auditor export-web</code>.</p></section>
      ) : (
        <section>
          <div className="toolbar">
            <h2 className="title" style={{ margin: 0, flex: 1 }}>Results</h2>
            {models.length > 1 && (
              <Segmented label="Model" value={current.model} onChange={setModel}
                options={models.map((x) => ({ value: x, label: x }))} />
            )}
            <Segmented label="Method" value={mode} onChange={setMode}
              options={available.map((x) => ({ value: x, label: MODE_NAMES[x] }))} />
          </div>
          {current.note && <p className="notice" style={{ marginBottom: 16 }}>{current.note}</p>}
          {m && (
            <>
              <div className="grid grid-4">
                <MetricTile label="Violations caught (recall)" value={pct(m.overall.recall)}
                  sub={`95% CI ${pct(m.overall.ci95.recall[0])}–${pct(m.overall.ci95.recall[1])} · ${m.violations} planted`} />
                <MetricTile label="Flags that were real (precision)" value={pct(m.overall.precision)}
                  sub={`95% CI ${pct(m.overall.ci95.precision[0])}–${pct(m.overall.ci95.precision[1])}`} />
                <MetricTile label="Clean chats wrongly flagged" value={pct(m.clean_flagged)}
                  sub={`of ${m.clean_chats} untouched chats`} />
                <MetricTile label="Finding cites the planted turn" value={pct(m.localised_exact)}
                  sub="of the violations it caught" />
              </div>
              <div className="card" style={{ marginTop: 16 }}>
                <h3 className="headline">Recall by policy category</h3>
                <p className="small muted" style={{ marginTop: 0 }}>
                  Share of planted violations caught, {current.model}, {current.conversations_compared} conversations.
                </p>
                <RecallChart metrics={current} categories={policy.categories} />
              </div>
              <div className="card" style={{ marginTop: 16, overflowX: "auto" }}>
                <table className="table">
                  <thead>
                    <tr><th>Method</th><th className="num">Recall</th><th className="num">Precision</th><th className="num">F1</th>
                      <th className="num">Near-miss false alarms</th><th className="num">Severity exact</th>
                      <th className="num">Quotes in cited turn</th><th className="num">Tool calls</th><th className="num">Cost</th></tr>
                  </thead>
                  <tbody>
                    {available.map((x) => {
                      const r = current.modes[x]!;
                      return (
                        <tr key={x}>
                          <td>{MODE_NAMES[x]}</td>
                          <td className="num">{pct(r.overall.recall)}</td>
                          <td className="num">{pct(r.overall.precision)}</td>
                          <td className="num">{r.overall.f1.toFixed(2)}</td>
                          <td className="num">{pct(r.near_miss_flagged)}</td>
                          <td className="num">{pct(r.severity_exact)}</td>
                          <td className="num">{pct(r.quotes_in_cited_turn)}</td>
                          <td className="num">{r.mean_tool_calls.toFixed(1)}</td>
                          <td className="num">${r.cost_usd.toFixed(2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      <section>
        <h2 className="title">How it works</h2>
        <div className="grid grid-3">
          {[
            ["Real conversations", "Customer-service chats from the public ABCD dataset, whose agent handbook becomes the written policy."],
            ["Planted ground truth", "A different AI inserts known violations and look-alike near-misses at recorded turns, and a second pass checks each one."],
            ["Three auditors", "Fixed-query RAG, an agent that searches the conversation with tools, and a full-transcript reader, all scored on the same chats."],
          ].map(([h, p], i) => (
            <div className="card" key={h}>
              <div className="step-num">{i + 1}</div>
              <h3 className="headline">{h}</h3>
              <p className="small muted" style={{ margin: 0 }}>{p}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
