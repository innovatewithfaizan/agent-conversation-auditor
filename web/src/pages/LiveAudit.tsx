import { useRef, useState } from "react";
import {
  fetchConversations, fetchHealth, fetchPolicy, fetchProviders, LIVE, MODE_NAMES, MODES, parseUpload, streamAudit,
  type AuditRecord, type Conversation, type Mode, type ToolCall,
} from "../data";
import { AuditPanel } from "../components/AuditPanel";
import { ToolTimeline } from "../components/ToolTimeline";
import { Transcript } from "../components/Transcript";
import { buildMarks } from "./ConversationDetail";
import { Loading, Segmented, useLoad } from "../components/ui";

type Source = "benchmark" | "upload";

export default function LiveAudit() {
  if (!LIVE) {
    return (
      <>
        <p className="eyebrow">Live audit</p>
        <h1 className="large-title">Audit a conversation yourself</h1>
        <p className="lede">Live auditing needs the API server, which this static copy of the site does not have.</p>
        <div className="notice">
          Run it locally: start the API with <code>uvicorn auditor.api:app</code>, then the app with{" "}
          <code>VITE_API_URL=http://localhost:8000 npm run dev</code>. You bring your own provider key; Groq has a free tier.
        </div>
      </>
    );
  }
  return <LiveAuditForm />;
}

function LiveAuditForm() {
  const [providers, e1] = useLoad(fetchProviders);
  const [rows, e2] = useLoad(fetchConversations);
  const [policy, e3] = useLoad(fetchPolicy);
  const [health] = useLoad(fetchHealth);
  const devKeys = health?.dev_keys ?? false;
  const [provider, setProvider] = useState("groq");
  const [model, setModel] = useState("openai/gpt-oss-120b");
  const [effort, setEffort] = useState("medium");
  const [mode, setMode] = useState<Mode>("agentic");
  const [key, setKey] = useState("");
  const [source, setSource] = useState<Source>("benchmark");
  const [convId, setConvId] = useState("");
  const [upload, setUpload] = useState<Conversation>();
  const [calls, setCalls] = useState<ToolCall[]>([]);
  const [result, setResult] = useState<AuditRecord>();
  const [error, setError] = useState<string>();
  const [running, setRunning] = useState(false);
  const [active, setActive] = useState<number>();
  const abort = useRef<AbortController>();

  if (!providers || !rows || !policy) return <Loading error={e1 ?? e2 ?? e3} />;
  const spec = providers[provider];
  const ready = (key.trim() !== "" || devKeys) && (source === "benchmark" ? convId !== "" : upload !== undefined) && !running;

  async function onFile(file: File | undefined) {
    setUpload(undefined);
    setError(undefined);
    if (!file) return;
    try { setUpload(await parseUpload(file)); } catch (e) { setError((e as Error).message); }
  }

  async function run() {
    setCalls([]); setResult(undefined); setError(undefined); setRunning(true);
    abort.current = new AbortController();
    try {
      await streamAudit({
        mode, provider, model, effort,
        ...(source === "benchmark" ? { conversation_id: convId } : { turns: upload!.turns }),
      }, key, (e) => {
        if (e.type === "tool") setCalls((c) => [...c, e]);
        if (e.type === "result") setResult(e.audit);
        if (e.type === "error") setError(e.message);
      }, abort.current.signal);
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  const turns = source === "upload" ? upload?.turns : undefined;
  return (
    <>
      <p className="eyebrow">Live audit</p>
      <h1 className="large-title">Audit a conversation yourself</h1>
      <p className="lede">Pick a provider, paste your own API key, and watch the auditor work through a chat step by step.</p>

      <div className="card">
        <div className="form-grid">
          <label className="field">Provider
            <select value={provider} onChange={(e) => { setProvider(e.target.value); setModel(providers[e.target.value].models[0]); }}>
              {Object.entries(providers).map(([p, s]) => <option key={p} value={p}>{s.label}</option>)}
            </select>
          </label>
          <label className="field">Model
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {spec.models.map((m) => <option key={m}>{m}</option>)}
            </select>
          </label>
          <label className="field">Reasoning effort
            <select value={effort} onChange={(e) => setEffort(e.target.value)}>
              {["low", "medium", "high"].map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>
          <label className="field">{spec.label} API key
            <input type="password" autoComplete="off" spellCheck={false} value={key} onChange={(e) => setKey(e.target.value)}
              placeholder={devKeys ? "Optional: dev server uses its own key" : "Used for this request only"} />
          </label>
        </div>
        <p className="tiny muted">
          The key is sent with this one request to the auditor API and on to {spec.label}. It is not stored, logged or
          saved in your browser. <a href={spec.key_url} target="_blank" rel="noreferrer">Get a {spec.label} key</a>.
        </p>
        <div className="toolbar" style={{ marginTop: 16 }}>
          <Segmented label="Method" value={mode} onChange={setMode} options={MODES.map((m) => ({ value: m, label: MODE_NAMES[m] }))} />
          <Segmented label="Conversation source" value={source} onChange={setSource}
            options={[{ value: "benchmark", label: "Benchmark chat" }, { value: "upload", label: "Upload a file" }]} />
        </div>
        {source === "benchmark" ? (
          <label className="field" style={{ maxWidth: 420 }}>Conversation
            <select value={convId} onChange={(e) => setConvId(e.target.value)}>
              <option value="">Choose a chat…</option>
              {rows.map((r) => <option key={r.id} value={r.id}>#{r.id} · {(r.subflow ?? "").replaceAll("_", " ")} · {r.turns} turns</option>)}
            </select>
          </label>
        ) : (
          <label className="field" style={{ maxWidth: 420 }}>Transcript (.srt, .vtt or .json, up to 2 MB)
            <input type="file" accept=".srt,.vtt,.json" onChange={(e) => onFile(e.target.files?.[0])} />
          </label>
        )}
        <div className="toolbar" style={{ marginTop: 18, marginBottom: 0 }}>
          <button className="button" type="button" disabled={!ready} onClick={run}>{running ? "Auditing…" : "Run audit"}</button>
          {running && <button className="button secondary" type="button" onClick={() => abort.current?.abort()}>Stop</button>}
          {!key.trim() && !devKeys && <span className="small muted">Paste an API key to run.</span>}
          {devKeys && <span className="small muted">Local dev mode: the API uses its own keys when the field is empty.</span>}
        </div>
      </div>

      {error && <p className="notice warn" style={{ marginTop: 16 }}>{error}</p>}

      {(running || calls.length > 0 || result) && (
        <div className="split" style={{ marginTop: 20 }}>
          <div className="card">
            <h2 className="headline">{running ? "Working…" : "Tool calls"}</h2>
            {mode === "agentic" ? <ToolTimeline calls={calls} /> : <p className="small muted">{MODE_NAMES[mode]} uses no tools.</p>}
            {turns && <div style={{ marginTop: 20 }}><Transcript turns={turns} marks={buildMarks(result, [], policy.categories, false)} active={active} /></div>}
          </div>
          <div className="card">
            <h2 className="headline">Result</h2>
            {result ? <AuditPanel audit={result} categories={policy.categories} onSelect={setActive} /> : <p className="small muted">Waiting for the auditor…</p>}
          </div>
        </div>
      )}
    </>
  );
}
