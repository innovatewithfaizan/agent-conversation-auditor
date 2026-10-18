# agent-conversation-auditor

An agentic RAG auditor that reads call and chat transcripts and checks them against a written policy: mishandled personal data, missing required disclosures, prohibited promises and poor escalation. Every finding cites the turn (and timestamp, where the transcript has one) it is based on, and the auditor is scored against known ground truth.

Work in progress. See [AGENTS.md](AGENTS.md) for the plan and current status.
