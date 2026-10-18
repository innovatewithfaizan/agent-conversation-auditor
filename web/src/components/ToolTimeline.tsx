import type { ToolCall } from "../data";

function describe(call: ToolCall): string {
  const i = call.input as Record<string, unknown>;
  switch (call.tool) {
    case "read_turns": return `read turns ${i.first}–${i.last}`;
    case "search_transcript": return `searched “${i.query}”`;
    case "find_words": return `counted ${(i.words as string[] | undefined)?.join(", ")}${i.speaker && i.speaker !== "any" ? ` (${i.speaker} only)` : ""}`;
    case "find_patterns": return `scanned for ${(i.kinds as string[] | undefined)?.join(", ").replaceAll("_", " ")}`;
    default: return call.tool;
  }
}

/** The agent's tool calls, in order, as they happen. */
export function ToolTimeline({ calls }: { calls: ToolCall[] }) {
  if (!calls.length) return <p className="small muted">No tool calls: the auditor answered from the excerpts it was given.</p>;
  return (
    <ol className="timeline">
      {calls.map((c, i) => (
        <li key={i}>
          <code>{c.tool}</code>
          <span>{describe(c)}{c.error ? <span className="muted"> · refused ({String(c.error)})</span> : null}</span>
        </li>
      ))}
    </ol>
  );
}
