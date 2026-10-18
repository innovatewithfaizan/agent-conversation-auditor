# agent-conversation-auditor

**Did the support agent, human or AI, follow the policy?** This project is an agentic RAG auditor that reads customer-support conversations, checks them against a written policy, and cites the exact turn behind every finding. It is scored against **known ground truth**: we plant violations into real chats ourselves and record where, so every number is a measurement, not a guess.

> **Result (80 conversations, gpt-5-mini):** reading the whole transcript, the auditor caught **84%** of planted violations (95% CI 73–93%). It cited the planted turn 95% of the time, raised **no false alarms on near-misses**, and every quote it gave exists in the turn it cites. An agent that searches the conversation with tools caught 70%; fixed retrieval caught 52%. The weak spot is **over-flagging**: 40% of the full-transcript reader's flags were on planted violations, and most of the rest landed on the original agents' own verification and data-handling gaps. It cost **$0.0046 per conversation**.

---

## Start here: pick your path

| If you are… | You probably want to know… | Read |
|---|---|---|
| **A business or non-technical reader** | What it does, why it matters, how well it works, what it costs, the risks | [The short version](#the-short-version) → [Business overview](#business-overview-no-code) → [Glossary](#glossary) |
| **New to the code (intern, student)** | What the ideas mean, how to run it, where to start reading | [The short version](#the-short-version) → [Key ideas](#key-ideas-in-five-minutes) → [Your first hour](#your-first-hour) → [Code tour](#code-tour) |
| **A senior engineer or reviewer** | Architecture, evaluation rigour, trade-offs, what is not proven | [How it works](#how-it-works) → [Results](#results) → [Design decisions](#design-decisions-and-trade-offs) → [Threats to validity](#threats-to-validity) |

---

## The short version

### What it does

1. It takes a **transcript**: a chat log, or a call transcript with timestamps.
2. An AI model reads it against a **written policy** with five categories and decides, for each, whether the agent broke a rule and how badly: **none, minor, major or critical**.
3. Every finding names the **turn** it is based on and **quotes** it, so a person can check the call in seconds.

| Category | What it catches |
|---|---|
| Personal and payment data | asking for or repeating full card numbers, security codes, passwords; revealing someone else's details |
| Identity verification | refunds or account changes before the customer's identity is checked |
| Commitments and claims | promising refunds, discounts or outcomes the policy does not allow; legal or medical advice |
| Complaints and escalation | refusing or ignoring a request for a supervisor; not escalating safety issues |
| Honesty and conduct | rudeness, pressure, misleading the customer, an AI claiming to be human |

The policy itself is a readable document: [`policy/support_policy.md`](policy/support_policy.md).

### How we know whether it works

Most "AI judge" projects score themselves against labels that are themselves AI guesses. Here we **plant** violations into real customer-service chats at known turns, plus **near-misses** (turns that look risky but follow the rules) and **untouched chats**. The auditor never sees what was planted. We then count what it catches, what it misses, and what it wrongly flags.

### Results in plain words (80 conversations, gpt-5-mini)

- **Reading the whole conversation**, the auditor caught **42 of 50** planted violations (84%), and its findings pointed at the planted turn 95% of the time.
- **Letting it search with tools beats fixed retrieval:** 70% caught against 52%, for about 1.5 tool calls per conversation.
- **It never flagged a near-miss** (0 of 15), the turns designed to look like violations without breaking a rule.
- **It over-flags:** only 40% of its flags were on planted violations. It also flagged 17 of the 27 untouched chats, mostly for identity verification and personal data. Some of these point to real handbook gaps by the original human agents.
- **Its quotes are real:** 100% of 133 quotes appear word for word in the turn they cite.
- **Cost:** under half a cent per conversation ($0.0046).

### One conversation, end to end

Chat #6178 is a real customer asking about a "mystery fee". We planted two violations: at turn 2 the agent says it has *"gone ahead and refunded the $3.40 to your card"* before any verification, and at turn 20 it asks the customer to *"type out your full card number"*.

- **Full-transcript auditor:** caught both, citing turns 2 and 20.
- **Agentic auditor:** caught the refund. It **missed** the card number, because it decided its starting excerpts were enough and never used its search tools.

That example captures the main pattern: an agent that trusts its first excerpts misses what it never reads.

---

## Business overview (no code)

### The problem

Contact centres, and now AI voice and chat agents, handle millions of conversations. Compliance teams can review only a tiny sample by hand, and mistakes such as reading back a card number, skipping identity checks or promising refunds create legal, financial and reputational risk. Automated checks exist, but they rarely explain themselves or prove how often they are right.

### What this project shows

- **An auditor that explains itself.** Each finding comes with the turn number and the exact words, so a reviewer can verify or overrule it in seconds.
- **A way to measure an AI auditor honestly:** plant known problems and count what it catches. The same method works for testing any AI agent before deployment.
- **Policy as a document, not code.** Change the written policy and the auditor changes with it.

### Who might use something like this

These are possible uses, not products that exist:

- **Quality assurance for contact centres:** review every conversation, not a 2% sample, and send humans only the flagged ones.
- **Testing AI voice and chat agents:** run a new agent version on test conversations and check it still follows policy before release.
- **Compliance evidence:** a searchable record of what was checked, when, and why something was flagged, useful for ISO 27001 / ISO 42001-style controls and privacy laws such as Quebec's Law 25.

### Results so far, in plain words

| Question | Answer (80 conversations) |
|---|---|
| Does it find planted violations? | Reading the full transcript: 84%. With search tools: 70%. With fixed retrieval: 52% |
| Are its flags right? | 40% point to planted problems. It also flags most untouched chats, partly for real slips by the original agents |
| Does it over-react to things that look risky but are fine? | No false alarms on the 15 near-misses (full transcript) |
| Can you trust its quotes? | Yes: 100% of quotes are found word for word in the cited turn |
| What does it cost? | Under half a cent per conversation (gpt-5-mini list price) |

The intervals are still wide at 80 conversations (about ±10 points on recall).

### Cost and speed

| Method | Cost per conversation | Median time |
|---|---|---|
| Fixed search (RAG) | $0.0041 | 16 s |
| Agent with search tools | $0.0069 | 23 s |
| Read the whole transcript | $0.0046 | 18 s |

These are gpt-5-mini list prices; many conversations run in parallel. The generation of test data uses a free model tier.

### What it is good for, and what it is not

| Good for | Not good for |
|---|---|
| Prioritising which conversations a human should review | Replacing human judgement on disciplinary or legal decisions |
| Explaining every flag with a checkable quote | Policies that depend on information outside the transcript |
| Testing AI agents against a policy before release | Audio cues (tone of voice, silence): it reads text only |

### Risks and responsible use

- **False flags:** 60% of the flags were not on planted violations, and most untouched chats got at least one. Treat flags as "please review", not as verdicts.
- **Synthetic test violations** are written by an AI. They are realistic, but real violations can be subtler or messier.
- **Privacy:** the project uses a public dataset and fake personal details (generated by the Faker library). In the web app, visitors use their own API key, which is used for one request and never stored or logged.

### Try it

The [web app](#web-app) shows every audited conversation, what was planted, what the auditor found and why. With your own API key (Groq has a free tier) you can run a live audit and watch the agent work step by step.

---

## Key ideas in five minutes

**Transcript and turns.** A conversation is a list of turns, each with a speaker (agent, customer, system for tool actions, or unknown) and text, and sometimes a timestamp. Turns are numbered from 0, and findings cite these numbers. Lines look like `[12 00:01:02] agent: text`.

**Large language model (LLM).** An AI that reads and writes text. We call it through an API that charges per token (about ¾ of a word).

**Embeddings and a vector database.** Each run of 4 consecutive turns is turned into a list of numbers (an embedding) that captures its meaning, and stored in ChromaDB. A search like "I'll refund you right away" then finds similar passages even when the words differ.

**RAG (retrieval-augmented generation).** Instead of sending the whole conversation, retrieve the most relevant passages and send only those. Here: one fixed search per policy category.

**Agent and tool calling.** An agent is an LLM that can call functions before answering. Our auditor has four:

- `read_turns`: read a range of turns.
- `search_transcript`: search by meaning.
- `find_words`: exact word counts, optionally only in the agent's turns.
- `find_patterns`: scan for card numbers, emails, phone numbers and ID numbers, shown masked.

**Structured output.** The answer must be a `submit_audit` call that matches a strict schema: per category, a severity and findings `{turn, quote, explanation}`. Invalid answers are sent back for a retry.

**Planted ground truth.** A different AI (Qwen, while the auditor is gpt-5-mini) writes 1–3 turns at a chosen spot in a real chat: a violation of a given category and severity, or a near-miss. A second, independent pass checks each one. A manifest records the exact turn.

**Metrics.**

- *Recall:* the share of planted violations caught.
- *Precision:* the share of flags that were on a planted violation.
- *F1:* combines the two.
- *Weighted κ:* severity agreement corrected for chance.
- *Bootstrap interval:* how much a score would wobble with a different sample of conversations.

---

## How it works

### Architecture

```mermaid
flowchart LR
    subgraph data["Data"]
        A["ABCD chats<br/>10k+ real support chats (MIT)"]
        G["ABCD agent handbook<br/>guidelines.json"]
        C["CallCenterEN<br/>real call transcripts (CC BY-NC)"]
    end
    G --> P["Written policy<br/>policy/support_policy.md"]
    A --> PL["Planting<br/>Qwen writes violations and near-misses<br/>independent re-check, manifest of turns"]
    PL --> B["Benchmark<br/>chats + manifest"]

    subgraph aud["Auditor: gpt-5-mini"]
        R["RAG<br/>1 fixed query per category"]
        AG["Agentic RAG<br/>read_turns, search_transcript,<br/>find_words, find_patterns"]
        F["Full transcript"]
    end
    B --> R & AG & F
    P --> aud
    aud --> S["submit_audit<br/>severity + findings with turn and quote"]
    S --> E["Evaluate vs manifest<br/>recall, precision, localisation,<br/>severity, grounding, bootstrap CI"]
    S --> W["API + React app"]
    C -. "reality check (next)" .-> aud
```

### Data

| Source | What | Licence | Role |
|---|---|---|---|
| [ABCD](https://github.com/asappresearch/abcd) (ASAPP) | 10,042 human-to-human customer-service chats (test split 1,004, median 21 turns); `action` turns log what the agent did in its tools | MIT | the conversations, and `guidelines.json`, the handbook the policy is built from |
| Planted violations | 1–3 turns written by `qwen/qwen3.8-27b` (Groq) per planted item, re-checked by an independent call | ours | exact ground truth |
| [Faker](https://github.com/joke2k/faker) | fake names, card numbers, emails, phone numbers | MIT | no real personal data |
| [CallCenterEN](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english) | 91,706 real call transcripts, PII redacted, word-level timestamps, **no speaker labels** | CC BY-NC 4.0 | parsers ready; hand-labelled reality check planned |

`python -m auditor download abcd` and `download callcenter --domain <name>` fetch the raw data into `data/raw/` (gitignored). CallCenterEN raw files are never committed.

### The policy

[`policy/support_policy.md`](policy/support_policy.md) is the single source of truth: the auditor's system prompt includes it word for word. Its procedures come from ABCD's handbook:
- **Verification fields per action:** username, email and order ID for refunds; full name, account ID and order ID for order and account changes.
- **Return windows by membership:** gold unlimited, silver 6 months, bronze 90 days, guest 30 days.
- **Default amounts:** $50 refund, $40 credit.

The payment-data and data-minimisation rules follow PCI DSS and privacy-law practice. Severity has four levels, each with examples.

### The auditor ([`auditor/audit.py`](auditor/audit.py))

| Mode | What the model sees | Tools |
|---|---|---|
| `rag` | the union of the top 4-turn chunk for each category's fixed query | none |
| `agentic` | the same starting excerpts | `read_turns`, `search_transcript`, `find_words`, `find_patterns`; at most 6 calls |
| `full` | the whole transcript | none |

The loop:
- Tool results are recorded, so every agentic audit has an audit trail.
- The agent is forced to submit when its budget or a provider's prompt-size limit is reached.
- `submit_audit` is validated: turn numbers must exist, and severity `none` must come with no findings (and vice versa). Invalid answers go back to the model.
- `find_patterns` masks every match, so the tool never echoes a full card number back.

```mermaid
sequenceDiagram
    participant C as audit()
    participant L as LLM
    participant T as Tools
    C->>L: policy + excerpts (or full transcript), tools
    loop at most 6 tool calls
        L-->>C: read_turns / search_transcript / find_words / find_patterns
        C->>T: run it (search skips chunks already seen)
        T-->>C: turns, passages, counts, masked matches
        C->>L: tool result
    end
    Note over C,L: budget or prompt cap reached: tool_choice forces submit_audit
    L-->>C: submit_audit {category: severity, findings[turn, quote, explanation]}
    C->>C: validate, record trace, tokens and cost
```

### The benchmark ([`auditor/plant.py`](auditor/plant.py), [`auditor/benchmark.py`](auditor/benchmark.py))

- **Selection:** 80 ABCD test chats with at least 24 turns (seed 7). 25% stay untouched, 20% get one near-miss, and the rest get one or two violations in different categories.
- **Severity and subtlety:** severity is weighted minor 0.3 / major 0.5 / critical 0.2; subtlety is "obvious" or "subtle" (no tell-tale words).
- **Placement:** verification problems go before the agent's first tool action; others go after a customer turn, 30–85% into the chat.
- **Checks:** an independent judging call checks each planted item. Failures are regenerated once, then dropped.
- **Outputs:** `data/benchmark/benchmark.jsonl` (conversations) and `manifest.json` (each item's turn, inserted turns and text).

### Evaluation ([`auditor/evaluate.py`](auditor/evaluate.py))

Every mode is scored on the same conversations:

- **Detection** per conversation × category: recall, precision, F1, plus 95% bootstrap intervals over conversations (2,000 resamples).
- **False alarms:** the share of untouched chats with any flag, and the share of near-misses flagged in their category.
- **Localisation:** whether a finding cites the planted turn.
- **Severity:** exact agreement on caught violations, and quadratic-weighted κ over every conversation × category.
- **Grounding:** whether each quote appears, normalised, in the turn it cites.

Untouched ABCD chats can contain real slips by the original agents. They count as false positives, so precision is a lower bound.

---

## Results

80 benchmark conversations: 38 with planted violations (50 violations in total), 15 with a near-miss, and 27 untouched. Audited by gpt-5-mini at reasoning effort medium. Source: [`results/metrics/gpt-5-mini/metrics.md`](results/metrics/gpt-5-mini/metrics.md).

| Method | Recall | 95% CI | Precision | 95% CI | F1 | Near-miss false alarms | Untouched chats flagged | Cites planted turn | Severity exact | Weighted κ | Quotes in cited turn | Tool calls | Cost (80 chats) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Full transcript | **84%** | 73–93% | **40%** | 31–50% | 0.55 | 0 of 15 | 17 of 27 | 95% | 88% | 0.48 | 100% of 133 | 0.0 | $0.37 |
| Agentic RAG | **70%** | 58–82% | **35%** | 27–43% | 0.47 | 1 of 15 | 17 of 27 | 94% | 91% | 0.42 | 98% of 121 | 1.5 | $0.55 |
| RAG | **52%** | 39–66% | **29%** | 20–38% | 0.37 | 2 of 15 | 19 of 27 | 92% | 85% | 0.29 | 100% of 110 | 0.0 | $0.32 |

A baseline that never flags anything has 0% recall, no false alarms and κ 0.

![Recall of planted violations by category](results/metrics/gpt-5-mini/detection_by_category.png)

Recall by category (planted count in brackets):

| Category | Full transcript | Agentic RAG | RAG |
|---|---|---|---|
| Personal and payment data (12) | 92% | 83% | 67% |
| Identity verification (8) | 100% | 100% | 100% |
| Commitments and claims (12) | 75% | 50% | 33% |
| Complaints and escalation (10) | 70% | 60% | 40% |
| Honesty and conduct (8) | 88% | 62% | 25% |

**What the numbers say:**
- **Reading everything wins on chats this size** (24–58 turns, median 29). Fixed retrieval takes one 4-turn chunk per category and misses about half the planted turns. The agent recovers much of that by reading and searching, but it still stops early: it averaged 1.5 tool calls when it could use 6.
- **No method over-reacts to near-misses** (0–2 of 15), but **all of them over-flag untouched chats**. On untouched chats the flags are mostly identity verification (9–13 per method) and personal data (8). Reading a sample, many point to real gaps in the original chats against ABCD's handbook, for example a subscription payment taken without the order ID. Precision is therefore a lower bound, but over-flagging is still the main weakness.
- **Findings are well grounded:** when a violation is caught, the finding cites the planted turn 92–95% of the time, and 98–100% of quotes are verbatim.
- **Critical violations** (7 planted) are where the agent did best (86%, against 57% for the full transcript), but 7 items is too few to read much into.

**Two checks:**
- **Calibration.** The policy wording and two prompt rules were adjusted after a 10-chat pilot. On the [70 chats never looked at](results/subsets/unseen/metrics.md), the picture holds: recall 80% / 71% / 49% (full / agentic / RAG), precision 38% / 35% / 26%.
- **Generator.** Qwen planted the first 29 chats with violations or near-misses; `gpt-oss-20b` planted the last 31, after Qwen's free daily quota ran out. `gpt-oss-20b`'s violations are blunter: the full-transcript reader caught [95% of them](results/subsets/generator_gpt_oss/metrics.md) against [75% of Qwen's](results/subsets/generator_qwen/metrics.md). For agentic RAG (73% vs 68%) and RAG (55% vs 50%) the gap is small.

The [10-chat pilot](results/pilot/metrics.md) is kept for reference.

---

## Web app

`web/` is a React app (Vite + TypeScript). Its design follows Apple's Human Interface Guidelines: system font, translucent navigation bar, large titles, system colours, light and dark mode.

- **Overview:** headline metrics, recall by category, results per method.
- **Conversations:** every benchmark chat with what was planted and what each method caught, missed or flagged extra.
- **Conversation detail:** the transcript as message bubbles. Planted turns are outlined, flagged turns ringed (always with a text label), and clicking a finding jumps to its turn. In agentic mode you also see the tools the agent used.
- **Live audit:** pick a provider and model, paste your own key, and watch the agent's tool calls stream in.
- **Policy:** the written policy.

Without an API the app reads static JSON (`python -m auditor export-web`), so it can be hosted on GitHub Pages. Live audits need the API (`uvicorn auditor.api:app`).

**Key handling:**
- The key travels in one request's `X-Provider-Key` header. It is never stored, logged, cached or echoed, and errors are redacted.
- The server's own keys are used only with `AUDITOR_DEV_ENV_KEYS=1` for local development.
- Only listed models are accepted.
- Uploads are capped at 2 MB and removed from the vector store after the run.

---

## Your first hour

**1. Prerequisites.** Python 3.11 and Node 20.

**2. Install.**

```bash
git clone https://github.com/innovatewithfaizan/agent-conversation-auditor.git
```

```bash
cd agent-conversation-auditor && python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

**3. Run the tests.** The first run downloads the small embedding model Chroma uses.

```bash
.venv/bin/python -m pytest -q
```

**4. Re-score the committed audits without any API key.**

```bash
.venv/bin/python -m auditor evaluate --model gpt-5-mini
```

**5. Look at the data.**

```bash
.venv/bin/python -m auditor download abcd
```

```bash
.venv/bin/python -m auditor show abcd 4989
```

**6. Open the web app** (static mode, no key needed):

```bash
cd web && npm ci && npm run dev
```

**7. Run a live audit.** Put a free [Groq key](https://console.groq.com/keys) in `.env` (copy `.env.example`), then:

```bash
.venv/bin/python -m auditor audit data/benchmark/benchmark.jsonl --limit 1 --mode agentic --provider groq --model openai/gpt-oss-120b
```

### The whole pipeline

```bash
.venv/bin/python -m auditor download abcd
.venv/bin/python -m auditor plant --n 80 --seed 7 --workers 1
.venv/bin/python -m auditor estimate data/benchmark/benchmark.jsonl --model gpt-5-mini
.venv/bin/python -m auditor audit data/benchmark/benchmark.jsonl --mode full --provider openai --model gpt-5-mini --workers 4
.venv/bin/python -m auditor evaluate --model gpt-5-mini
.venv/bin/python -m auditor export-web
```

`plant` and `audit` skip finished items and resume after rate limits. `plant` also waits out Groq's daily free-tier limit by itself.

---

## Code tour

About 2,300 lines of Python, 900 lines of Python tests, and 1,200 lines of TypeScript and CSS. Reading order:

| # | File | What it does |
|---|---|---|
| 1 | [`policy/support_policy.md`](policy/support_policy.md) | the written policy |
| 2 | [`auditor/transcripts.py`](auditor/transcripts.py) | Turn / Conversation; parsers for ABCD, CallCenterEN, SRT/VTT, JSON; JSONL; rendering and chunking |
| 3 | [`auditor/index.py`](auditor/index.py) | ChromaDB store keyed by conversation, semantic search, `find_words` |
| 4 | [`auditor/patterns.py`](auditor/patterns.py) | masked sensitive-data detectors (Luhn-checked cards, codes, emails, phones, IDs) |
| 5 | [`auditor/llm.py`](auditor/llm.py) | one OpenAI-compatible client for OpenAI, Groq, Together AI and OpenRouter; prices; retries |
| 6 | [`auditor/audit.py`](auditor/audit.py) | prompts, tools, the audit loop, validation |
| 7 | [`auditor/plant.py`](auditor/plant.py), [`benchmark.py`](auditor/benchmark.py) | planting, judging, the benchmark build |
| 8 | [`auditor/evaluate.py`](auditor/evaluate.py), [`report.py`](auditor/report.py) | metrics, bootstrap, report and chart |
| 9 | [`auditor/api.py`](auditor/api.py), [`export.py`](auditor/export.py) | FastAPI service and static export |
| 10 | [`auditor/__main__.py`](auditor/__main__.py) | the CLI |
| 11 | [`web/src/`](web/src/) | the React app: `data.ts` (data layer and stream parser), `components/`, `pages/` |
| 12 | [`tests/`](tests/), [`web/src/app.test.tsx`](web/src/app.test.tsx) | tests with fake LLMs (no network), API and export tests, UI tests |

[`AGENTS.md`](AGENTS.md) is the working brief for coding agents: status, decisions, data notes and commands.

---

## Design decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| Plant violations instead of labelling with an LLM | exact ground truth: turn, category and severity are known | planted text is AI-written and may be easier or harder than real violations |
| Near-misses and untouched chats in the benchmark | measures over-flagging, not only recall | untouched chats can hide real slips, so precision is a lower bound |
| Generators other than the auditor: Qwen, then `gpt-oss-20b` | no model grades text it wrote itself | Qwen's free daily cap forced the switch halfway; `gpt-oss-20b` is also an OpenAI model and its violations are easier to catch (reported separately) |
| Policy as a Markdown document in the prompt | readable by non-engineers; one source of truth | long prompts (about 1,400 tokens of policy per call) |
| Strict tool schemas and validation | structured, checkable output on any OpenAI-compatible provider | a retry when the model gets it wrong |
| Agent starts from the RAG excerpts | the comparison isolates what the tools add | the agent often thinks the excerpts suffice |
| Masked `find_patterns` | the tool never echoes sensitive data back | less context for the model |
| Bring-your-own-key, static-first web app | public demo with no hosting bill and no shared secret | live audits need visitors' keys |

---

## Threats to validity

1. **Size.** 80 conversations and 50 planted violations: about ±10 points on recall, and only 7–12 items per category. Full transcript beats RAG clearly; full against agentic is within the intervals.
2. **Calibration on a pilot.** The policy wording and two prompt rules were adjusted after looking at 10 chats. On the other 70 the results are within a few points (see [Results](#results)).
3. **Synthetic violations from two generators.** They are AI-written; `gpt-oss-20b`'s are easier to catch than Qwen's, and 12 planned items were dropped after failing the independent check twice. Real violations can be subtler.
4. **Untouched chats aren't guaranteed clean.** Real agents' slips appear as false positives.
5. **One auditor model, one run.** Run-to-run variance and other models are not measured yet.
6. **Text only.** No audio cues. Real call transcripts (CallCenterEN) have no speaker labels.

---

## Repository layout

```text
policy/support_policy.md    the written policy
auditor/                    Python package: parsers, index, LLM client, auditor, planting, evaluation, API, CLI
tests/                      pytest suite (fake LLM backends; no network beyond the embedding model)
web/                        React app (Vite + TypeScript); web/public/data is the static export
results/metrics/gpt-5-mini/ evaluation of the full benchmark (metrics.md, metrics.json, chart)
results/subsets/            the same audits scored on the unseen chats and per generator
results/pilot/              the 10-chat pilot used for calibration
data/benchmark/             the benchmark: benchmark.jsonl and manifest.json
results/audits/             saved audits: <model>/<mode>/<dataset>/<conv_id>.json
data/raw/                   downloaded datasets (gitignored)
.github/workflows/          CI (pytest, web tests and build) and GitHub Pages deploy
Dockerfile                  the API, for Hugging Face Spaces or Render
AGENTS.md, CLAUDE.md        brief for coding agents
```

## Deployment

- **Static site (GitHub Pages):** `.github/workflows/pages.yml` builds `web/` and publishes it on every push to `main` that touches `web/`. Enable it once in the repository settings: Settings → Pages → Source: GitHub Actions.
- **API:** the `Dockerfile` runs `uvicorn auditor.api:app` on port 7860 (Hugging Face Spaces) or `$PORT` (Render). Set `AUDITOR_CORS_ORIGINS` to the site's address. No keys are baked in.
- Neither is deployed yet.

## Glossary

| Term | Meaning |
|---|---|
| **Agent** | in AI: a model that can use tools before answering. In customer service: the person or bot helping the customer |
| **Transcript / turn** | the written conversation / one message in it |
| **Policy** | the written rules the agent must follow |
| **Planted violation** | a rule-breaking turn we inserted on purpose, at a known position |
| **Near-miss** | a turn that looks like a violation but follows the rules |
| **Recall** | of the planted violations, the share the auditor caught |
| **Precision** | of the auditor's flags, the share that were on planted violations |
| **RAG** | look up relevant passages first, then answer from them |
| **Embedding / vector database** | numbers that capture meaning / a database that finds similar ones |
| **Tool call** | the AI asking the program to run a function |
| **Confidence interval** | the range a score would likely fall in with different conversations |
| **Weighted κ** | agreement on severity, corrected for chance; 0 is chance, 1 is perfect |
| **BYOK** | bring your own key: users supply their own API key |

## Data and licence note

ABCD is MIT-licensed (ASAPP). CallCenterEN is CC BY-NC 4.0 (non-commercial); its raw files are not in this repository. Personal details in planted turns are fake (Faker). This repository does not yet include a licence file for the code. Nothing here is legal advice.
