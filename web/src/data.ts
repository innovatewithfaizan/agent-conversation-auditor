// Data access. With VITE_API_URL set, everything comes from the FastAPI
// service and live audits are possible. Without it, the app reads the static
// JSON written by `python -m auditor export-web` (works on GitHub Pages).

export type Severity = "none" | "minor" | "major" | "critical";
export type Mode = "full" | "rag" | "agentic";

export interface Turn { idx: number; speaker: string; text: string; start: string }
export interface Conversation { conv_id: string; source: string; meta: Record<string, unknown>; turns: Turn[] }
export interface Finding { turn: number; quote: string; explanation: string }
export interface CategoryResult { severity: Severity; findings: Finding[] }
export interface ToolCall { tool: string; input: Record<string, unknown>; error?: string; [k: string]: unknown }
export interface AuditRecord {
  conv_id: string; mode: Mode; provider: string; model: string; effort: string; summary: string;
  categories: Record<string, CategoryResult>; tool_calls: ToolCall[];
  usage: { calls: number; input_tokens: number; output_tokens: number; cost_usd: number }; seconds: number;
}
export interface PlantedItem {
  kind: "violation" | "near_miss"; category: string; severity: Severity; subtlety: string;
  turn: number; inserted_turns: number[]; text: string;
}
export interface GroundTruth { plan: string; items: PlantedItem[] }
export interface ConversationRow {
  id: string; turns: number; flow: string | null; subflow: string | null; plan: string;
  planted: { kind: string; category: string; severity: Severity }[];
  audits?: Record<string, Record<string, string[]>>; // model -> mode -> flagged categories
}
export interface ConversationDetail { conversation: Conversation; ground_truth: GroundTruth; audits: Record<string, Partial<Record<Mode, AuditRecord>>> }
export interface Policy { categories: Record<string, string>; severities: Severity[]; text: string }
export interface Providers { [provider: string]: { label: string; models: string[]; key_url: string } }
export interface ModeMetrics {
  conversations: number;
  overall: { recall: number; precision: number; f1: number; tp: number; fp: number; fn: number; tn: number;
    ci95: { recall: [number, number]; precision: [number, number]; f1: [number, number] } };
  categories: Record<string, { recall: number | null; precision: number | null; tp: number; fp: number; fn: number }>;
  clean_chats: number; clean_flagged: number; near_misses: number; near_miss_flagged: number; violations: number;
  localised_exact: number; localised_exchange: number; severity_exact: number; kappa_qw: number;
  recall_by_subtlety: Record<string, number>; recall_by_severity: Record<string, number>;
  quotes: number; quotes_in_cited_turn: number; mean_tool_calls: number; median_seconds: number; cost_usd: number;
}
export interface Metrics {
  model: string; note?: string; conversations_compared: number; audits_available: Record<string, number>;
  benchmark: { plans: Record<string, number>; items: Record<string, number>; generator: { provider: string; model: string } };
  modes: Partial<Record<Mode, ModeMetrics>>;
}

export const API_URL: string | undefined = import.meta.env.VITE_API_URL || undefined;
export const LIVE = Boolean(API_URL);
export const MODE_NAMES: Record<Mode, string> = { full: "Full transcript", rag: "RAG", agentic: "Agentic RAG" };
export const MODES: Mode[] = ["agentic", "rag", "full"];

async function get<T>(path: string): Promise<T> {
  const url = API_URL ? `${API_URL}/api/${path}` : `${import.meta.env.BASE_URL}data/${path}.json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json() as Promise<T>;
}

export const fetchPolicy = () => get<Policy>("policy");
export const fetchProviders = () => get<Providers>("providers");
export const fetchConversations = () => get<ConversationRow[]>("conversations");
export const fetchConversation = (id: string) => get<ConversationDetail>(`conversations/${encodeURIComponent(id)}`);
export const fetchMetrics = () => get<Record<string, Metrics>>("metrics");
export const fetchHealth = () => get<{ ok: boolean; benchmark_conversations: number; dev_keys: boolean }>("health");

export async function parseUpload(file: File): Promise<Conversation> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_URL}/api/parse`, { method: "POST", body });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `upload failed (${res.status})`);
  return res.json();
}

export type AuditEvent =
  | { type: "start"; conversation_id: string; turns: number; mode: Mode }
  | ({ type: "tool" } & ToolCall)
  | { type: "result"; audit: AuditRecord }
  | { type: "error"; message: string };

/** Split a server-sent-events buffer into complete events and the remainder. */
export function parseSSE(buffer: string): { events: AuditEvent[]; rest: string } {
  const events: AuditEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    const data = block.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n");
    if (data) events.push(JSON.parse(data) as AuditEvent);
  }
  return { events, rest };
}

export interface AuditRequest {
  mode: Mode; provider: string; model: string; effort: string;
  conversation_id?: string; turns?: { speaker: string; text: string; start?: string }[];
}

/** Run a live audit. The key goes only in this request's header; it is never stored. */
export async function streamAudit(req: AuditRequest, key: string, onEvent: (e: AuditEvent) => void, signal?: AbortSignal) {
  const res = await fetch(`${API_URL}/api/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Provider-Key": key },
    body: JSON.stringify(req),
    signal,
  });
  if (!res.ok || !res.body) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : `request failed (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSSE(buffer);
    buffer = rest;
    events.forEach(onEvent);
  }
}

export function pct(x: number | null | undefined): string {
  return x === null || x === undefined || Number.isNaN(x) ? "—" : `${Math.round(x * 100)}%`;
}
