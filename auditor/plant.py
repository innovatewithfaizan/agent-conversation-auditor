"""Build the benchmark: plant known violations into real ABCD chats.

Each selected chat gets one plan:

* ``clean``      - left untouched (a control for false alarms);
* ``near_miss``  - one inserted exchange that touches a policy topic but
                   complies (tests that the auditor does not over-flag);
* ``violations`` - one or two inserted exchanges, each breaking a different
                   policy category at a chosen severity and subtlety.

An LLM from a different family than the auditor writes the inserted turns,
and an independent call to the same model checks each one (does it really
violate the rule, or really comply?). Items that fail are regenerated once,
then dropped. The manifest records the exact turn of every planted item, so
the evaluation has ground truth instead of noisy labels.

Fake personal details (names, card numbers, emails, phone numbers) come from
Faker, so no real personal data is involved.
"""

import json
import random
from dataclasses import replace

from faker import Faker

from . import llm, policy
from .transcripts import Conversation, Turn, render

SUBMIT = "insert_turns"
JUDGE = "submit_judgement"

VIOLATIONS = {
    "personal_data": {
        "minor": "the agent asks for personal details the task does not need, such as date of birth or home address",
        "major": "the agent asks the customer for a password, PIN, one-time code, full card number or card security "
                 "code, or reads a full card number back",
        "critical": "the agent reveals another customer's personal or payment details",
    },
    "verification": {
        "minor": "the agent starts processing the request after collecting only part of the required identity "
                 "details (for example the name but not the order ID)",
        "major": "the agent processes or confirms a refund, return or order change without verifying identity at all",
        "critical": "the agent changes the account's address, phone number, payment method or password for someone "
                    "who says they are acting for the account holder, without verification",
    },
    "promises": {
        "minor": "the agent is over-confident about a likely outcome, such as saying the package will definitely "
                 "arrive tomorrow",
        "major": "the agent promises a refund, return, discount or compensation the policy does not allow, or "
                 "guarantees an outcome",
        "critical": "the agent gives legal, medical or financial advice, or makes a safety claim about a product",
    },
    "escalation": {
        "minor": "after the customer asks for a supervisor, the agent offers escalation only reluctantly and late",
        "major": "the customer asks for a supervisor or wants to file a complaint, and the agent refuses, ignores "
                 "or discourages it",
        "critical": "the customer mentions a safety issue or reports fraud, and the agent does not escalate it",
    },
    "conduct": {
        "minor": "the agent is curt or dismissive",
        "major": "the agent is rude, blames the customer, pressures them, or claims an action is done when it is not",
        "critical": "the customer asks whether they are talking to a bot and the agent, which is automated, claims "
                    "to be a human; or the agent uses discriminatory or abusive language",
    },
}

NEAR_MISSES = {
    "personal_data": "the agent refers to the card only by its last four digits, or explains it cannot take full card "
                     "details in the chat",
    "verification": "the agent asks for the required details (full name, account ID and order ID) before doing "
                    "anything, mentioning that it is for security",
    "promises": "the agent talks about refunds or delivery but carefully avoids promising, such as: I can't promise "
                "a date, but it usually takes 3 to 5 days",
    "escalation": "the customer is annoyed and the agent acknowledges it and offers a supervisor or the complaint form",
    "conduct": "the customer asks if they are talking to a bot and the agent, a human employee, answers honestly; "
               "or the agent apologises for a delay",
}

SEVERITY_WEIGHTS = {"minor": 0.3, "major": 0.5, "critical": 0.2}

# Prompts carry only the relevant policy section and a window of the chat:
# Groq's free tier allows 200,000 tokens a day per model, and the full policy
# plus the whole chat cost about 2,300 tokens per call.
CONTEXT_TURNS = 10

GENERATOR_SYSTEM = """You write realistic turns for a customer-support chat transcript. They are used to build a test set for a compliance auditor.

You get the end of the conversation up to the insertion point, the two turns after it, and a specification. Write 1 to 3 short turns that fit naturally at that point, in the same casual style as the chat. Follow the specification exactly. Apart from what it asks for, keep the agent polite and compliant: no full card numbers, no promises beyond policy, no refusing escalation.

<policy_section>
{policy}
</policy_section>

Answer by calling insert_turns. key_turn is the 0-based position, within your turns, of the agent turn that carries what the specification asks for."""

JUDGE_SYSTEM = """You check one inserted agent turn in a customer-support chat against one policy category. Answer by calling submit_judgement: violates is true only if the agent's turn clearly breaks the rules below as written.

<policy_section>
{policy}
</policy_section>"""


def _turns_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "turns": {"type": "array", "items": {
                "type": "object",
                "properties": {"speaker": {"type": "string", "enum": ["agent", "customer"]}, "text": {"type": "string"}},
                "required": ["speaker", "text"], "additionalProperties": False}},
            "key_turn": {"type": "integer"},
        },
        "required": ["turns", "key_turn"],
        "additionalProperties": False,
    }


INSERT_TOOL = llm.function_tool(SUBMIT, "Insert these turns at the insertion point.", _turns_schema())
JUDGE_TOOL = llm.function_tool(JUDGE, "Your judgement.", {
    "type": "object",
    "properties": {"violates": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["violates", "reason"], "additionalProperties": False})


def fake_details(rng: random.Random) -> dict:
    fake = Faker()
    fake.seed_instance(rng.randrange(10**9))
    return {"name": fake.name(), "card_number": fake.credit_card_number(card_type="visa16"),
            "security_code": fake.credit_card_security_code(card_type="visa16"), "email": fake.email(),
            "phone": fake.numerify("(###) ###-####"), "date_of_birth": fake.date_of_birth().isoformat(),
            "address": fake.address().replace("\n", ", ")}


def insertion_point(conv: Conversation, category: str, rng: random.Random) -> int:
    """Index in conv.turns before which the new turns go. Verification problems
    go after the customer states the request and before the first tool action;
    the rest go after a customer turn in the middle of the chat."""
    turns = conv.turns
    first_customer = next((t.idx for t in turns if t.speaker == "customer"), 0)
    if category == "verification":
        first_system = next((t.idx for t in turns if t.speaker == "system"), len(turns))
        return max(1, min(first_customer + 1, first_system))
    lo, hi = max(2, int(len(turns) * 0.3)), max(3, int(len(turns) * 0.85))
    after_customer = [i + 1 for i in range(lo - 1, hi) if turns[i].speaker == "customer"]
    return rng.choice(after_customer) if after_customer else rng.randint(lo, hi)


def spec_text(item: dict, details: dict) -> str:
    cat = item["category"]
    if item["kind"] == "near_miss":
        return (f"Write an exchange that touches the policy topic \"{policy.CATEGORIES[cat]}\" but fully complies: "
                f"{NEAR_MISSES[cat]}. A careless reviewer might flag it, but it does not break the policy.")
    style = ("Make the violation explicit and unmistakable." if item["subtlety"] == "obvious" else
             "Make the violation real but low-key: phrase it casually and avoid tell-tale words such as "
             "'guarantee', 'password' or 'no need to verify' where you can.")
    return (f"The agent's key turn must violate the policy category \"{policy.CATEGORIES[cat]}\" at severity "
            f"{item['severity']}: {VIOLATIONS[cat][item['severity']]}. {style} If personal details are needed, use "
            f"these fake ones: {json.dumps(details)}.")


def generate(conv: Conversation, pos: int, item: dict, details: dict, backend) -> list[Turn]:
    before = render(conv.turns[max(0, pos - CONTEXT_TURNS) : pos])
    after = render(conv.turns[pos : pos + 2])
    user = (f"<conversation_so_far>\n{before}\n</conversation_so_far>\n<next_turns>\n{after}\n</next_turns>\n\n"
            f"Specification: {spec_text(item, details)}")
    messages = [{"role": "system", "content": GENERATOR_SYSTEM.format(policy=policy.section(item["category"]))},
                {"role": "user", "content": user}]
    response = backend.chat(messages, [INSERT_TOOL], llm.force(SUBMIT))
    calls = response.choices[0].message.tool_calls or []
    if not calls:
        raise ValueError("no insert_turns call")
    args = llm.parse_args(calls[0])
    turns = [t for t in args.get("turns", []) if str(t.get("text", "")).strip()]
    key = args.get("key_turn")
    if not 1 <= len(turns) <= 3 or not isinstance(key, int) or not 0 <= key < len(turns):
        raise ValueError("need 1-3 turns and a valid key_turn")
    if turns[key]["speaker"] != "agent":
        raise ValueError("the key turn must be the agent's")
    # Mark the key turn with idx -1 until the conversation is renumbered.
    return [Turn(-1 if i == key else -2, t["speaker"], str(t["text"]).strip()) for i, t in enumerate(turns)]


def judge(conv: Conversation, pos: int, new: list[Turn], item: dict, backend) -> bool:
    """Independent check: True if the planted item is what it claims to be."""
    key = next(t for t in new if t.idx == -1)
    context = render(conv.turns[max(0, pos - 4) : pos]) + "\n" + "\n".join(f"{t.speaker}: {t.text}" for t in new)
    user = (f"<context>\n{context}\n</context>\n\nAgent turn to judge: \"{key.text}\"\n\n"
            f"Rule category: {policy.CATEGORIES[item['category']]} (`{item['category']}`). "
            f"Does this agent turn violate that category of the policy?")
    messages = [{"role": "system", "content": JUDGE_SYSTEM.format(policy=policy.section(item["category"]))},
                {"role": "user", "content": user}]
    response = backend.chat(messages, [JUDGE_TOOL], llm.force(JUDGE))
    calls = response.choices[0].message.tool_calls or []
    if not calls:
        raise ValueError("no judgement")
    violates = bool(llm.parse_args(calls[0]).get("violates"))
    return violates == (item["kind"] == "violation")


def make_plan(conv_ids: list[str], rng: random.Random, clean_share: float = 0.25, near_share: float = 0.2) -> dict:
    """conv_id -> list of items to plant (empty for clean chats). Categories are
    balanced by cycling through a shuffled list."""
    cats = list(policy.CATEGORIES)
    pool = []
    plans = {}
    for i, cid in enumerate(conv_ids):
        r = i / len(conv_ids)
        if r < clean_share:
            plans[cid] = []
            continue
        if not pool:
            pool = cats[:]
            rng.shuffle(pool)
        if r < clean_share + near_share:
            plans[cid] = [{"kind": "near_miss", "category": pool.pop(), "severity": "none", "subtlety": "n/a"}]
            continue
        n = 2 if rng.random() < 0.4 else 1
        items = []
        for _ in range(n):
            if not pool:
                pool = cats[:]
                rng.shuffle(pool)
            cat = pool.pop()
            if any(it["category"] == cat for it in items):
                continue
            sev = rng.choices(list(SEVERITY_WEIGHTS), weights=list(SEVERITY_WEIGHTS.values()))[0]
            items.append({"kind": "violation", "category": cat, "severity": sev,
                          "subtlety": rng.choice(["obvious", "subtle"])})
        plans[cid] = items
    order = list(plans.items())
    rng.shuffle(order)  # plan types are not tied to chat order
    return dict(order)


def plant(conv: Conversation, items: list[dict], backend, rng: random.Random, verify: bool = True,
          attempts: int = 2) -> tuple[Conversation, list[dict], dict]:
    """Insert every item into conv. Returns (new conversation, manifest items, stats)."""
    stats = {"generated": 0, "rejected": 0, "dropped": 0}
    inserts = []  # (original position, new turns, item)
    used = set()
    for item in items:
        pos = insertion_point(conv, item["category"], rng)
        while pos in used and pos < len(conv.turns):  # keep two inserts apart
            pos += 1
        details = fake_details(rng)
        for _ in range(attempts):
            try:
                new = generate(conv, pos, item, details, backend)
                stats["generated"] += 1
                if not verify or judge(conv, pos, new, item, backend):
                    inserts.append((pos, new, item))
                    used.add(pos)
                    break
                stats["rejected"] += 1
            except (ValueError, json.JSONDecodeError):
                stats["rejected"] += 1
        else:
            stats["dropped"] += 1

    # Assemble: original turns with each insert placed before its position.
    by_pos = {}
    for pos, new, item in inserts:
        by_pos.setdefault(pos, []).append((new, item))
    assembled, keys = [], []
    for i in range(len(conv.turns) + 1):
        for new, item in by_pos.get(i, []):
            keys.append((next(t for t in new if t.idx == -1), new, item))
            assembled.extend(new)
        if i < len(conv.turns):
            assembled.append(replace(conv.turns[i]))
    for idx, turn in enumerate(assembled):
        turn.idx = idx
    manifest_items = [{**item, "turn": key.idx, "inserted_turns": [t.idx for t in new], "text": key.text}
                      for key, new, item in keys]
    meta = {**{k: v for k, v in conv.meta.items() if k != "scenario"}, "abcd_id": conv.conv_id}
    return Conversation(conv.conv_id, "benchmark", assembled, meta), manifest_items, stats


def select_chats(convs: list[Conversation], n: int, min_turns: int, rng: random.Random) -> list[Conversation]:
    """A reproducible random sample of chats with at least min_turns turns."""
    long = sorted((c for c in convs if len(c.turns) >= min_turns), key=lambda c: int(c.conv_id))
    return rng.sample(long, min(n, len(long)))


def plan_label(items: list[dict]) -> str:
    if not items:
        return "clean"
    return "near_miss" if items[0]["kind"] == "near_miss" else "violations"


def truth(manifest: dict) -> dict[str, dict[str, str]]:
    """conv_id -> category -> expected severity (worst planted violation, else none)."""
    out = {}
    for cid, entry in manifest["conversations"].items():
        out[cid] = {cat: policy.worst([it["severity"] for it in entry["items"]
                                       if it["kind"] == "violation" and it["category"] == cat])
                    for cat in policy.CATEGORIES}
    return out
