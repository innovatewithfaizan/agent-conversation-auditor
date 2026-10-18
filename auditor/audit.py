"""Audit one conversation against the policy.

Three modes, so the README can compare them on the same conversations:

* ``rag``     - one fixed query per policy category; the union of the top
                chunks is shown to the model in one call.
* ``agentic`` - the same starting excerpts plus tools (read turns, semantic
                search, exact word counts, sensitive-data patterns). The model
                decides what else to look at, within a fixed budget.
* ``full``    - the whole transcript in one call (long-context baseline).

The answer always comes back through a strict ``submit_audit`` tool call: a
severity per category and findings that cite a turn number and quote it.
"""

import json
import re
import time

from . import config, llm, patterns, policy
from .index import ConversationContext, find_words
from .transcripts import render

MODES = ("rag", "agentic", "full")
SUBMIT = "submit_audit"
MAX_TURNS = config.AGENT_MAX_TOOL_CALLS + 4
READ_LIMIT = 12  # turns per read_turns call

SYSTEM = f"""You are a compliance auditor for customer-support conversations. You check the agent's behaviour against the written policy below and report each violation with evidence.

<policy>
{policy.policy_text()}
</policy>

How to audit:
- Judge only what the agent says or does. Customers may say anything.
- Each transcript line is "[turn time] speaker: text". Cite each violation by its turn number and quote the agent's words exactly as they appear in that turn.
- Report a violation only when the transcript shows it. Expected steps, such as asking for a name, account ID, order ID, username or email to verify identity, are not violations. A weak or speculative finding is worse than none.
- When speakers are "unknown", infer who is speaking from context and say so in the explanation.
- For each category give the severity of its worst violation, or "none" with no findings.
- Answer by calling {SUBMIT}."""

AGENT_ADDENDUM = f"""

You start with excerpts from fixed searches, and they can miss turns. You have tools to look further:
- read_turns reads a range of turns (at most {READ_LIMIT} per call), for example the turns around an excerpt or turns you have not seen.
- search_transcript finds passages by meaning. Phrase queries like something the agent might say ("I'll refund you right away").
- find_words counts exact words or phrases, optionally only in the agent's turns.
- find_patterns scans every turn for card numbers, card security codes, emails, phone numbers, ID numbers and mentions of passwords or codes.

Before you mark a category "none", make sure you have seen enough of the conversation to be confident. You can make at most {config.AGENT_MAX_TOOL_CALLS} tool calls in total. Then call {SUBMIT}."""


def audit_schema() -> dict:
    finding = {
        "type": "object",
        "properties": {
            "turn": {"type": "integer"},
            "quote": {"type": "string"},
            "explanation": {"type": "string"},
        },
        "required": ["turn", "quote", "explanation"],
        "additionalProperties": False,
    }
    category = {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": policy.SEVERITIES},
            "findings": {"type": "array", "items": finding},
        },
        "required": ["severity", "findings"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "categories": {
                "type": "object",
                "properties": {cat: category for cat in policy.CATEGORIES},
                "required": list(policy.CATEGORIES),
                "additionalProperties": False,
            },
        },
        "required": ["summary", "categories"],
        "additionalProperties": False,
    }


SUBMIT_TOOL = llm.function_tool(SUBMIT, "Submit the audit: a severity and findings for every policy category.",
                                audit_schema())
TOOLS = [
    llm.function_tool(
        "read_turns",
        f"Read turns first..last of this conversation (inclusive, at most {READ_LIMIT}).",
        {"type": "object", "properties": {"first": {"type": "integer"}, "last": {"type": "integer"}},
         "required": ["first", "last"], "additionalProperties": False},
    ),
    llm.function_tool(
        "search_transcript",
        f"Semantic search over this conversation (all-MiniLM-L6-v2 embeddings of {config.CHUNK_TURNS}-turn "
        f"chunks). Returns up to {config.AGENT_SEARCH_K} chunks you have not seen yet.",
        {"type": "object", "properties": {"query": {"type": "string"}},
         "required": ["query"], "additionalProperties": False},
    ),
    llm.function_tool(
        "find_words",
        "Case-insensitive counts of whole words or short phrases across the conversation, with example turns. "
        "Words also match common endings; a trailing * matches any ending. At most 12 per call.",
        {"type": "object",
         "properties": {"words": {"type": "array", "items": {"type": "string"}},
                        "speaker": {"type": "string", "enum": ["agent", "customer", "any"]}},
         "required": ["words", "speaker"], "additionalProperties": False},
    ),
    llm.function_tool(
        "find_patterns",
        "Scan every turn for sensitive data. Returns, per kind, how many turns match and example turns with "
        "masked values.",
        {"type": "object",
         "properties": {"kinds": {"type": "array", "items": {"type": "string", "enum": patterns.KINDS}}},
         "required": ["kinds"], "additionalProperties": False},
    ),
]


def validate(args: dict, n_turns: int) -> tuple[str, dict]:
    """Check a submit_audit payload; returns (summary, categories) or raises ValueError."""
    cats = args.get("categories")
    if not isinstance(cats, dict):
        raise ValueError("categories must be an object")
    out = {}
    for cat in policy.CATEGORIES:
        c = cats.get(cat)
        if not isinstance(c, dict) or c.get("severity") not in policy.SEVERITIES:
            raise ValueError(f"{cat}: severity must be one of {policy.SEVERITIES}")
        findings = c.get("findings") or []
        if not isinstance(findings, list):
            raise ValueError(f"{cat}: findings must be a list")
        clean = []
        for f in findings:
            turn = f.get("turn") if isinstance(f, dict) else None
            if not isinstance(turn, int) or not 0 <= turn < n_turns:
                raise ValueError(f"{cat}: each finding needs a turn number between 0 and {n_turns - 1}")
            clean.append({"turn": turn, "quote": str(f.get("quote", "")), "explanation": str(f.get("explanation", ""))})
        if (c["severity"] == "none") != (not clean):
            raise ValueError(f"{cat}: use severity 'none' exactly when there are no findings")
        out[cat] = {"severity": c["severity"], "findings": clean}
    return str(args.get("summary", "")), out


def _json_in_text(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise ValueError("no JSON object in reply")
    return json.loads(match.group(0))


def approx_tokens(messages: list[dict]) -> int:
    return len(json.dumps(messages, ensure_ascii=False)) // 4


def excerpts(ctx: ConversationContext) -> str:
    """The union of the top chunks for every category's fixed query, in
    conversation order, each labelled with the categories that retrieved it."""
    hits = {}
    for cat, query in policy.CATEGORY_QUERIES.items():
        for h in ctx.store.search(ctx.key, query, config.TOP_K_CHUNKS):
            hits.setdefault(h["id"], {**h, "cats": []})["cats"].append(cat)
    ctx.seen.update(hits)
    blocks = [f"--- turns {h['first']}-{h['last']} ({', '.join(h['cats'])}) ---\n{h['text']}"
              for h in sorted(hits.values(), key=lambda h: h["first"])]
    return "\n".join(blocks)


def build_prompt(ctx: ConversationContext, mode: str) -> str:
    n = len(ctx.conv.turns)
    if mode == "full":
        return f"<transcript turns=\"{n}\">\n{render(ctx.conv.turns)}\n</transcript>\n\nAudit this conversation."
    return (
        f"The conversation has {n} turns (0-{n - 1}). Below are excerpts retrieved for each policy category; "
        f"they are not the whole conversation.\n\n<excerpts>\n{excerpts(ctx)}\n</excerpts>\n\nAudit this conversation."
    )


def run_tool(ctx: ConversationContext, name: str, args: dict) -> tuple[str, dict]:
    turns = ctx.conv.turns
    if name == "read_turns":
        first = max(0, int(args.get("first", 0)))
        last = min(len(turns) - 1, int(args.get("last", first)), first + READ_LIMIT - 1)
        if first > last:
            return "(no turns in that range)", {"turns": 0}
        return render(turns[first : last + 1]), {"turns": last - first + 1}
    if name == "search_transcript":
        hits = ctx.store.search(ctx.key, args.get("query", ""), config.AGENT_SEARCH_K, ctx.seen)
        ctx.seen.update(h["id"] for h in hits)
        text = "\n".join(f"--- turns {h['first']}-{h['last']} ---\n{h['text']}" for h in hits)
        return text or "(no new passages)", {"new_chunks": len(hits)}
    if name == "find_words":
        spk = args.get("speaker")
        found = find_words(turns, list(args.get("words", [])), None if spk in (None, "any") else spk)
        return json.dumps(found, ensure_ascii=False), {"counts": found["counts"]}
    if name == "find_patterns":
        found = patterns.find_patterns(turns, list(args.get("kinds", [])) or None)
        return json.dumps(found, ensure_ascii=False), {"turns_with_match": {k: v["turns_with_match"] for k, v in found.items()}}
    return f"Unknown tool {name}.", {"error": "unknown tool"}


def audit(ctx: ConversationContext, mode: str, backend: llm.Backend, on_step=None) -> dict:
    """Audit one conversation. on_step(event: dict) is called for each tool call (used by the app)."""
    t0 = time.time()
    usage = llm.Usage()
    agentic = mode == "agentic"
    n_turns = len(ctx.conv.turns)
    messages = [
        {"role": "system", "content": SYSTEM + (AGENT_ADDENDUM if agentic else "")},
        {"role": "user", "content": build_prompt(ctx, mode)},
    ]
    trace, calls_made, result = [], 0, None

    for _ in range(MAX_TURNS):
        cap = backend.max_prompt_tokens
        too_big = bool(cap) and approx_tokens(messages) > cap
        can_search = agentic and calls_made < config.AGENT_MAX_TOOL_CALLS and not too_big
        tools = TOOLS + [SUBMIT_TOOL] if agentic else [SUBMIT_TOOL]
        response = backend.chat(messages, tools, "auto" if can_search else llm.force(SUBMIT))
        usage.add(response)
        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:  # some models answer in text despite the tools; accept valid JSON
            try:
                result = validate(_json_in_text(message.content), n_turns)
                break
            except (ValueError, json.JSONDecodeError):
                messages.append(llm.assistant_message(message))
                messages.append({"role": "user", "content": f"Call {SUBMIT} with your audit."})
                continue

        messages.append(llm.assistant_message(message))
        for call in tool_calls:
            name = call.function.name
            try:
                args = llm.parse_args(call)
            except json.JSONDecodeError as exc:
                args, content, info = {}, f"Arguments were not valid JSON: {exc}", {"error": "bad json"}
            else:
                if name == SUBMIT:
                    try:
                        result = validate(args, n_turns)
                        content, info = "Received.", {}
                    except ValueError as exc:
                        content, info = f"Invalid audit: {exc}. Call {SUBMIT} again.", {"error": str(exc)}
                elif not can_search or calls_made >= config.AGENT_MAX_TOOL_CALLS:
                    content, info = f"Tool budget used up. Call {SUBMIT} now.", {"error": "budget"}
                else:
                    content, info = run_tool(ctx, name, args)
                    calls_made += 1
            if name != SUBMIT:
                event = {"tool": name, "input": args, **info}
                trace.append(event)
                if on_step:
                    on_step(event)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
        if result is not None:
            break
    if result is None:
        raise RuntimeError(f"no valid audit after {MAX_TURNS} turns")

    summary, categories = result
    return {
        "conv_id": ctx.conv.conv_id,
        "source": ctx.conv.source,
        "mode": mode,
        "provider": backend.provider,
        "model": backend.model,
        "effort": backend.effort,
        "summary": summary,
        "categories": categories,
        "tool_calls": trace,
        "usage": usage.to_dict(backend.model),
        "seconds": round(time.time() - t0, 1),
    }
