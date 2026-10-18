import { useEffect, useState, type ReactNode } from "react";
import type { Severity } from "../data";

export function SeverityPill({ severity }: { severity: Severity }) {
  return <span className={`pill sev-${severity}`}>{severity === "none" ? "no issue" : severity}</span>;
}

export function StatusPill({ kind, children }: { kind: "hit" | "miss" | "false" | "planted" | "near"; children: ReactNode }) {
  return <span className={`pill st-${kind}`}>{children}</span>;
}

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function MetricTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {sub && <div className="tile-sub">{sub}</div>}
    </div>
  );
}

/** Load data once; returns [data, error]. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[] = []): [T | undefined, string | undefined] {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  useEffect(() => {
    let alive = true;
    setData(undefined);
    setError(undefined);
    load().then((d) => alive && setData(d)).catch((e: Error) => alive && setError(e.message));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return [data, error];
}

export function Loading({ error }: { error?: string }) {
  return error
    ? <p className="notice warn">Could not load data: {error}</p>
    : <p className="muted">Loading…</p>;
}
