"""Paths and run settings shared by every stage."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # API keys and optional overrides; never committed
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"  # downloaded datasets (gitignored)
ABCD_DIR = RAW_DIR / "abcd"
CALLCENTER_DIR = RAW_DIR / "callcenteren"
RESULTS_DIR = ROOT / "results"
CACHE_DIR = ROOT / ".cache"
CHROMA_DIR = CACHE_DIR / "chroma"

# Any OpenAI-compatible provider works (see llm.PROVIDERS). The CLI default is
# an open-weight model on Groq's free tier; override with env vars or flags.
PROVIDER = os.environ.get("PROVIDER", "groq")
AUDITOR_MODEL = os.environ.get("AUDITOR_MODEL", "openai/gpt-oss-120b")
EFFORT = os.environ.get("EFFORT", "medium")  # reasoning effort: low | medium | high

# Retrieval. A chunk is CHUNK_TURNS consecutive turns of one conversation.
CHUNK_TURNS = 4
# Real call transcripts come as timed words without speakers; a pause longer
# than this starts a new turn.
TURN_GAP_MS = 700
# Stop agent searches once a request would pass this many (approximate)
# tokens. Unset: the provider's default (6500 on Groq for its free tier,
# no limit elsewhere). 0 disables it.
MAX_PROMPT_TOKENS = int(os.environ["MAX_PROMPT_TOKENS"]) if os.environ.get("MAX_PROMPT_TOKENS") else None

# Auditor retrieval and tool budget. Chats are short (ABCD median 21 turns):
# with 2 chunks per category the RAG excerpts covered almost a whole 25-turn
# chat, so the baseline takes 1 chunk (4 turns) per category and the agent
# reads further with its tools.
TOP_K_CHUNKS = 1
AGENT_SEARCH_K = 3
AGENT_MAX_TOOL_CALLS = 6
AUDITS_DIR = RESULTS_DIR / "audits"


def audits_dir(model: str, mode: str, dataset: str) -> Path:
    """results/audits/<model>/<mode>/<dataset>/, so runs never mix."""
    return AUDITS_DIR / model.replace("/", "_") / mode / dataset
