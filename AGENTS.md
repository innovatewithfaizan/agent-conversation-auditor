# AGENTS.md: project handoff

This is the working brief for any coding agent (Claude Code, Cursor, Codex) or person picking up this project. Read it fully before changing anything. **Update the status checklist at the end of every PR.**

## What we are building

**agent-conversation-auditor**: an agentic RAG auditor that reads customer-service call and chat transcripts and checks them against a written policy. It flags mishandled personal data, skipped identity verification, prohibited promises, poor escalation and missing disclosures. Every finding cites the turn (and timestamp, where the transcript has one) and quotes the line it is based on. The auditor is scored against **known ground truth**: violations we plant ourselves at recorded positions.

The engine is ported from an earlier project that rated films from subtitles. That project validated the same agentic RAG + strict tool-call + evaluation pipeline on 75 films: https://github.com/innovatewithfaizan/Agentic-Retrieval-Augmented-Generation-for-AI-Powered-Content-Moderation. Reuse its code and lessons; do not copy its film data here.

## Status

- [x] PR 0: repo created, `.gitignore`, README stub
- [ ] PR 1: this handoff file (`AGENTS.md`, `CLAUDE.md`)
- [ ] PR 2: engine port: `llm.py` (multi-provider client), vector store and `find_words`, transcript parsers (ABCD JSON, CallCenterEN JSON, SRT/VTT), tests
- [ ] PR 3: policy rubric and auditor: categories, severity scale, `search_transcript` / `find_words` / `find_patterns` tools, strict `submit_findings` schema, modes `rag` / `agentic` / `full`
- [ ] PR 4: ground truth: violation-planting generator with a manifest, near-misses and clean controls; evaluation (recall, precision, false-positive rate on clean chats, turn localisation, severity agreement, bootstrap CIs, evidence grounding)
- [ ] PR 5: pilot of about 10 chats to measure cost, then the full runs; commit results
- [ ] PR 6: FastAPI service: list conversations, saved audits, live `POST /audit` streaming tool calls (bring-your-own-key)
- [ ] PR 7: React frontend (Vite + React + TypeScript) following the user's Apple design skill. **Blocked: ask the user where the skill is installed**; it was not found in `~/.claude`, `~/.cursor` or `~/.agents` on 2026-10-18.
- [ ] PR 8: README for three audiences (business, newcomer, senior engineer), deployment (static frontend on GitHub Pages, API on Render or Hugging Face Spaces)

## Data plan

Use only public or synthetic data. Never use data from the user's employers.

| Source | What | Licence | Role |
|---|---|---|---|
| [ABCD](https://github.com/asappresearch/abcd) (ASAPP) | 10k+ human-to-human customer-service chats, 55 intents, `action` turns logging what the agent did, original and delexicalised versions | MIT | backbone; its `data/guidelines.json` is the **written agent policy** the rubric is built from |
| Planted violations | an LLM (different family from the auditor) inserts 0–3 violating agent turns into real ABCD chats; a manifest records chat id, turn, category, severity, subtlety. Also near-misses (look like violations, are not) and untouched controls | ours | **exact ground truth** for recall, precision and localisation |
| [Faker](https://github.com/joke2k/faker) | fake names, cards, emails, phone numbers for planted personal-data violations | MIT | no real personal data |
| [CallCenterEN](https://huggingface.co/datasets/AIxBlock/91706-real-world-call-center-scripts-english) ([paper](https://arxiv.org/abs/2507.02958)) | 91,706 real English call-centre transcripts, PII removed, word-level timestamps | CC BY-NC 4.0 (non-commercial) | reality check on real voice calls; the user hand-labels about 40. **Commit a download script and our labels, never the raw transcripts.** |

Raw downloads go in `data/raw/` (gitignored).

## Draft policy categories (to finalise in PR 3)

| Category | Violation examples |
|---|---|
| `personal_data` | reading back a full card number, asking for a password, revealing another customer's details |
| `verification` | refunding or changing an account before verifying identity as `guidelines.json` requires |
| `promises` | promising refunds or outcomes the policy does not allow, guaranteeing timelines, giving legal or medical advice |
| `escalation` | ignoring a request for a supervisor, or repeated complaints without offering escalation |
| `disclosure` | an automated agent denying it is automated when asked; missing a recording notice on voice calls |

Severity: `none`, `minor`, `major`, `critical`.

## Decisions already made

- **Auditor model:** `gpt-5-mini` at reasoning effort `medium` (OpenAI). In the film project, low effort made the agent almost never use its tools.
- **Generators and labelers come from a different model family than the auditor** (for example Qwen or gpt-oss on Groq's free tier), so no model grades its own output.
- **Three modes**, as in the film project: fixed-query RAG, agentic RAG with search tools, full transcript.
- **Strict tool-call schemas** for all structured output; one OpenAI-compatible client for OpenAI, Groq, Together AI and OpenRouter.
- **Frontend:** React (Vite + TypeScript) with a FastAPI backend. No Streamlit. Saved audits ship with the frontend so it works with no server; live auditing needs the API.
- **Bring-your-own-key:** a visitor's key is used for one request only. It is never logged, stored, cached or read from the server's environment; a dev-only env flag may allow `.env` keys locally.
- **Honest reporting:** real metrics only. Report intervals and baselines; say what is not proven.

## Working rules

- **Small PRs against `main`**, each branched from an up-to-date `main` after the previous PR merges. Never stack PRs on unmerged branches.
- **The user reviews and merges every PR.** Do not merge yourself.
- **Before every push**, run the tests on a clean checkout: `git worktree add --detach <scratch dir> HEAD`, run pytest there, then remove the worktree.
- **After every push**, list each pushed commit as `sha — message — https://github.com/innovatewithfaizan/agent-conversation-auditor/commit/<sha>`.
- **Secrets:** API keys live in `.env` (gitignored). Never print, log, echo or commit them; check key names only (`cut -d= -f1 .env`).
- **Paid runs:** estimate first, run a small pilot, and confirm with the user before any full paid run.
- **Never use or mention the user's employers or their repositories.**
- Keep usage lean: no exploratory paid calls, no large downloads without need.

## Environment

- Python 3.11, virtualenv in `.venv/` (`python3.11 -m venv .venv`). Use `.venv/bin/python`.
- `.env` holds `GROQ_API_KEY` and `OPENAI_API_KEY`. Copy `.env.example` once it exists.
- Commands (tests, CLI, app) are listed here as each PR adds them.

## Commands

```bash
.venv/bin/python -m pytest -q
```
