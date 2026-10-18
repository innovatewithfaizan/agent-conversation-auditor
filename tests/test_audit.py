"""Prompts, schema, tools and the audit loop, with a fake LLM (no API calls)."""

import json
from types import SimpleNamespace

from auditor import audit, config, index, llm, policy
from auditor.transcripts import Conversation, Turn

TEXTS = [
    ("agent", "Hi, how can I help?"), ("customer", "I want a refund for my jeans."),
    ("agent", "I'll refund you right away, no need to verify anything."), ("customer", "Great, my card is 4111 1111 1111 1111."),
    ("agent", "Thanks, refunding to 4111 1111 1111 1111 now."), ("system", "Refund issued."),
    ("customer", "I want to speak to a manager about the delay."), ("agent", "That's not possible, sorry."),
    ("customer", "Fine."), ("agent", "Have a nice day."),
]
CONV = Conversation("c1", "test", [Turn(i, s, t) for i, (s, t) in enumerate(TEXTS)])

NONE = {"severity": "none", "findings": []}
FINAL = {
    "summary": "Refund without verification; card number repeated.",
    "categories": {**{c: NONE for c in policy.CATEGORIES},
                   "verification": {"severity": "major", "findings": [
                       {"turn": 2, "quote": "I'll refund you right away, no need to verify anything.",
                        "explanation": "Refund promised before any verification."}]}},
}


class FakeStore:
    def __init__(self):
        self.queries = []

    def search(self, key, query, k, exclude=frozenset()):
        self.queries.append(query)
        n = len(self.queries)
        hits = [{"id": f"{key}:c{n:04d}", "first": 0, "last": 1, "start": "", "text": "[0] agent: Hi"}]
        return [h for h in hits if h["id"] not in exclude]


class FakeBackend:
    provider, model, effort, max_prompt_tokens = "groq", "openai/gpt-oss-120b", "medium", 0

    def __init__(self, replies):
        self.replies = iter(replies)
        self.sent = []

    def chat(self, messages, tools, tool_choice):
        self.sent.append({"messages": list(messages), "tools": tools, "tool_choice": tool_choice})
        return next(self.replies)


def ctx():
    return index.ConversationContext(CONV, FakeStore())


def call(name, args, call_id):
    raw = args if isinstance(args, str) else json.dumps(args)
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=raw))


def reply(calls=None, content=""):
    message = SimpleNamespace(content=content, tool_calls=calls)
    usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=100)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def submit(payload=FINAL, i="s"):
    return reply([call(audit.SUBMIT, payload, i)])


def _strict_ok(schema):
    if schema.get("type") == "object":
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        for sub in schema["properties"].values():
            _strict_ok(sub)
    if schema.get("type") == "array":
        _strict_ok(schema["items"])


def test_all_tool_schemas_are_strict():
    for tool in audit.TOOLS + [audit.SUBMIT_TOOL]:
        assert tool["function"]["strict"] is True
        _strict_ok(tool["function"]["parameters"])


def test_system_prompt_carries_the_written_policy():
    assert "Identity verification (`verification`)" in audit.SYSTEM
    assert all(f"(`{c}`)" in audit.SYSTEM for c in policy.CATEGORIES)


def test_full_mode_sends_the_numbered_transcript_and_forces_submit():
    backend = FakeBackend([submit()])
    rec = audit.audit(ctx(), "full", backend)
    prompt = backend.sent[0]["messages"][1]["content"]
    assert '<transcript turns="10">' in prompt and "[4] agent: Thanks, refunding" in prompt
    assert backend.sent[0]["tool_choice"] == llm.force(audit.SUBMIT)
    assert rec["categories"]["verification"]["severity"] == "major"
    assert rec["categories"]["verification"]["findings"][0]["turn"] == 2
    assert rec["usage"]["calls"] == 1 and rec["tool_calls"] == []


def test_rag_mode_shows_deduplicated_excerpts_from_every_category_query():
    store = FakeStore()
    backend = FakeBackend([submit()])
    audit.audit(index.ConversationContext(CONV, store), "rag", backend)
    assert store.queries == list(policy.CATEGORY_QUERIES.values())
    prompt = backend.sent[0]["messages"][1]["content"]
    assert "The conversation has 10 turns (0-9)" in prompt and prompt.count("--- turns") == len(policy.CATEGORIES)


def test_agentic_tools_run_and_are_traced():
    calls = [
        call("read_turns", {"first": 3, "last": 4}, "t1"),
        call("find_patterns", {"kinds": ["card_number"]}, "t2"),
        call("find_words", {"words": ["manager"], "speaker": "customer"}, "t3"),
        call("search_transcript", {"query": "refund without verification"}, "t4"),
    ]
    backend = FakeBackend([reply(calls), submit()])
    steps = []
    rec = audit.audit(ctx(), "agentic", backend, on_step=steps.append)
    tool_msgs = [m for m in backend.sent[1]["messages"] if m["role"] == "tool"]
    assert "[3] customer: Great, my card is" in tool_msgs[0]["content"]
    found = json.loads(tool_msgs[1]["content"])
    assert found["card_number"]["turns_with_match"] == 2
    assert "4111 1111 1111 1111" not in tool_msgs[1]["content"]  # masked
    assert json.loads(tool_msgs[2]["content"])["counts"] == {"manager": 1}
    assert [t["tool"] for t in rec["tool_calls"]] == ["read_turns", "find_patterns", "find_words", "search_transcript"]
    assert steps == rec["tool_calls"]


def test_tool_budget_is_enforced_within_one_response(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MAX_TOOL_CALLS", 2)
    calls = [call("read_turns", {"first": 0, "last": 1}, f"t{i}") for i in range(3)]
    backend = FakeBackend([reply(calls), submit()])
    rec = audit.audit(ctx(), "agentic", backend)
    assert [t.get("error") for t in rec["tool_calls"]] == [None, None, "budget"]
    assert backend.sent[1]["tool_choice"] == llm.force(audit.SUBMIT)


def test_invalid_audits_are_sent_back_for_a_retry():
    no_findings = {**FINAL, "categories": {**FINAL["categories"], "promises": {"severity": "major", "findings": []}}}
    bad_turn = {**FINAL, "categories": {**FINAL["categories"], "conduct": {
        "severity": "minor", "findings": [{"turn": 99, "quote": "x", "explanation": "y"}]}}}
    backend = FakeBackend([submit(no_findings, "s1"), submit(bad_turn, "s2"), submit(FINAL, "s3")])
    rec = audit.audit(ctx(), "full", backend)
    assert rec["categories"]["promises"] == NONE
    assert "use severity 'none' exactly when" in backend.sent[1]["messages"][-1]["content"]
    assert "between 0 and 9" in backend.sent[2]["messages"][-1]["content"]


def test_plain_text_json_answer_is_accepted():
    backend = FakeBackend([reply(None, content="Audit: " + json.dumps(FINAL))])
    assert audit.audit(ctx(), "full", backend)["summary"] == FINAL["summary"]


def test_prompt_size_guard_forces_submit():
    backend = FakeBackend([reply([call("read_turns", {"first": 0, "last": 2}, "t1")]), submit()])
    backend.max_prompt_tokens = 10  # any real prompt is bigger
    rec = audit.audit(ctx(), "agentic", backend)
    assert backend.sent[0]["tool_choice"] == llm.force(audit.SUBMIT)
    assert rec["tool_calls"][0]["error"] == "budget"


def test_read_turns_is_clamped():
    text, info = audit.run_tool(ctx(), "read_turns", {"first": -5, "last": 500})
    assert info == {"turns": 10} and text.startswith("[0] agent")
    assert audit.run_tool(ctx(), "read_turns", {"first": 20, "last": 25})[1] == {"turns": 0}
