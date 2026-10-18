import { fireEvent, render, screen } from "@testing-library/react";
import { parseSSE, pct, type AuditRecord } from "./data";
import { AuditPanel } from "./components/AuditPanel";
import { outcome } from "./pages/ConversationList";
import { buildMarks } from "./pages/ConversationDetail";

const NAMES = { verification: "Identity verification", promises: "Commitments and claims" };
const AUDIT: AuditRecord = {
  conv_id: "1", mode: "agentic", provider: "groq", model: "m", effort: "medium", summary: "One problem.",
  categories: {
    verification: { severity: "major", findings: [{ turn: 3, quote: "no need to verify", explanation: "skipped" }] },
    promises: { severity: "none", findings: [] },
  },
  tool_calls: [], usage: { calls: 1, input_tokens: 10, output_tokens: 5, cost_usd: 0.001 }, seconds: 2,
};

test("parseSSE returns complete events and keeps the partial remainder", () => {
  const { events, rest } = parseSSE('data: {"type":"start","turns":3}\n\ndata: {"type":"tool","tool":"read_turns"}\n\ndata: {"ty');
  expect(events.map((e) => e.type)).toEqual(["start", "tool"]);
  expect(rest).toBe('data: {"ty');
});

test("outcome counts caught, missed and extra categories", () => {
  const row = { id: "1", turns: 9, flow: null, subflow: null, plan: "violations",
    planted: [{ kind: "violation", category: "verification", severity: "major" as const },
      { kind: "near_miss", category: "conduct", severity: "none" as const }] };
  expect(outcome(row, ["verification", "conduct"])).toEqual({ caught: 1, missed: 0, extra: 1 });
  expect(outcome(row, [])).toEqual({ caught: 0, missed: 1, extra: 0 });
});

test("buildMarks combines planted turns and findings", () => {
  const marks = buildMarks(AUDIT, [{ kind: "violation", category: "verification", turn: 3 },
    { kind: "near_miss", category: "promises", turn: 5 }], NAMES, true);
  expect(marks[3]).toEqual({ planted: "Identity verification", flagged: ["Identity verification"] });
  expect(marks[5]).toEqual({ near: "Commitments and claims" });
  expect(buildMarks(AUDIT, [], NAMES, false)[5]).toBeUndefined();
});

test("AuditPanel shows caught/missed against the truth and jumps to a finding's turn", () => {
  const onSelect = vi.fn();
  render(<AuditPanel audit={AUDIT} categories={NAMES} onSelect={onSelect}
    truth={[{ kind: "violation", category: "verification", severity: "major", subtlety: "obvious", turn: 3, inserted_turns: [3], text: "t" },
      { kind: "violation", category: "promises", severity: "minor", subtlety: "subtle", turn: 6, inserted_turns: [6], text: "t" }]} />);
  expect(screen.getByText("caught")).toBeTruthy();
  expect(screen.getByText("missed")).toBeTruthy();
  fireEvent.click(screen.getByText("no need to verify"));
  expect(onSelect).toHaveBeenCalledWith(3);
});

test("pct handles missing values", () => {
  expect(pct(0.456)).toBe("46%");
  expect(pct(Number.NaN)).toBe("—");
  expect(pct(null)).toBe("—");
});
