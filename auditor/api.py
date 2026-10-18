"""HTTP API for the web app: browse the benchmark and saved audits, and run a
live audit with the visitor's own API key.

    uvicorn auditor.api:app --reload

Key handling: the provider key arrives in the X-Provider-Key header, is used
for that one request's client and is never logged, stored or echoed back.
The server's own environment keys are used only when AUDITOR_DEV_ENV_KEYS=1
(local development); never set that on a public deployment.
"""

import json
import os
import queue
import threading
import uuid
from functools import lru_cache

import openai
from fastapi import FastAPI, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import audit, benchmark, config, index, llm, policy, transcripts

DEV_ENV_KEYS = os.environ.get("AUDITOR_DEV_ENV_KEYS") == "1"
MAX_UPLOAD_BYTES = 2_000_000
MAX_TURNS = 400

app = FastAPI(title="agent-conversation-auditor", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("AUDITOR_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Provider-Key"],
)


# Data loaded from disk -------------------------------------------------------

@lru_cache(maxsize=1)
def bench() -> tuple[dict, dict]:
    """(conversations by id, manifest); empty when the benchmark is not built."""
    if not benchmark.CONVERSATIONS.exists() or not benchmark.MANIFEST.exists():
        return {}, {"conversations": {}}
    convs = {c.conv_id: c for c in transcripts.load_jsonl(benchmark.CONVERSATIONS)}
    return convs, benchmark.load_manifest()


def audit_summaries() -> dict[str, dict[str, dict[str, list[str]]]]:
    """conv_id -> model -> mode -> flagged categories, for every saved benchmark audit."""
    out = {}
    for path in config.AUDITS_DIR.glob("*/*/benchmark/*.json"):
        rec = json.loads(path.read_text(encoding="utf-8"))
        flagged = [c for c, v in rec["categories"].items() if v["severity"] != "none"]
        out.setdefault(rec["conv_id"], {}).setdefault(rec["model"], {})[rec["mode"]] = flagged
    return out


def saved_audits(conv_id: str) -> dict:
    """{model: {mode: record}} for one benchmark conversation."""
    out = {}
    for path in sorted(config.AUDITS_DIR.glob(f"*/*/benchmark/{conv_id}.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        out.setdefault(rec["model"], {})[rec["mode"]] = rec
    return out


@lru_cache(maxsize=1)
def store() -> index.Store:
    return index.memory_store()


# Read-only endpoints -----------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    convs, _ = bench()
    return {"ok": True, "benchmark_conversations": len(convs)}


@app.get("/api/policy")
def get_policy() -> dict:
    return {"categories": policy.CATEGORIES, "severities": policy.SEVERITIES, "text": policy.policy_text()}


@app.get("/api/providers")
def providers() -> dict:
    return {p: {"label": s["label"], "models": s["models"], "key_url": s["key_url"]} for p, s in llm.PROVIDERS.items()}


@app.get("/api/conversations")
def list_conversations() -> list[dict]:
    convs, manifest = bench()
    summaries = audit_summaries()
    out = []
    for cid, conv in convs.items():
        entry = manifest["conversations"].get(cid, {"plan": "unknown", "items": []})
        out.append({"id": cid, "turns": len(conv.turns), "flow": conv.meta.get("flow"),
                    "subflow": conv.meta.get("subflow"), "plan": entry["plan"],
                    "planted": [{"kind": i["kind"], "category": i["category"], "severity": i["severity"]}
                                for i in entry["items"]],
                    "audits": summaries.get(cid, {})})
    return out


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str) -> dict:
    convs, manifest = bench()
    if conv_id not in convs:
        raise HTTPException(404, "unknown conversation")
    return {"conversation": transcripts.to_dict(convs[conv_id]),
            "ground_truth": manifest["conversations"].get(conv_id, {}),
            "audits": saved_audits(conv_id)}


@app.get("/api/metrics")
def metrics() -> dict:
    out = {}
    for path in sorted((config.RESULTS_DIR / "metrics").glob("*/metrics.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        out[rec["model"]] = rec
    return out


@app.post("/api/parse")
async def parse(file: UploadFile) -> dict:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large (2 MB max)")
    try:
        conv = transcripts.parse_upload(file.filename or "upload", data)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(422, str(exc)) from None
    if len(conv.turns) > MAX_TURNS:
        raise HTTPException(422, f"{len(conv.turns)} turns; the demo accepts up to {MAX_TURNS}")
    return transcripts.to_dict(conv)


# Live audit --------------------------------------------------------------------

class TurnIn(BaseModel):
    speaker: str
    text: str = Field(max_length=4000)
    start: str = ""


class AuditRequest(BaseModel):
    mode: str = "agentic"
    provider: str = "groq"
    model: str = "openai/gpt-oss-120b"
    effort: str = "medium"
    conversation_id: str | None = None
    turns: list[TurnIn] | None = Field(default=None, max_length=MAX_TURNS)


def resolve_key(provider: str, header_key: str | None, dev: bool | None = None) -> str:
    """The visitor's key, or the environment's key in dev mode only."""
    dev = DEV_ENV_KEYS if dev is None else dev
    key = (header_key or "").strip()
    if not key and dev:
        key = os.environ.get(llm.PROVIDERS[provider]["env"], "")
    return key


def safe_error(exc: Exception, key: str) -> str:
    if isinstance(exc, openai.AuthenticationError):
        return "The provider rejected that API key."
    if isinstance(exc, openai.RateLimitError):
        return "The provider's rate limit was hit. Wait a minute, or try the RAG mode (fewer tokens)."
    text = f"{type(exc).__name__}: {exc}"
    return text.replace(key, "[key]") if key else text


def _conversation(req: AuditRequest) -> tuple[transcripts.Conversation, bool]:
    """(conversation, is_upload)."""
    if req.conversation_id:
        convs, _ = bench()
        if req.conversation_id not in convs:
            raise HTTPException(404, "unknown conversation")
        return convs[req.conversation_id], False
    if not req.turns:
        raise HTTPException(422, "send conversation_id or turns")
    turns = transcripts.parse_generic([t.model_dump() for t in req.turns])
    if not turns:
        raise HTTPException(422, "no turns with text")
    return transcripts.Conversation(f"upload-{uuid.uuid4().hex}", "upload", turns), True


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/audit")
def run_audit(req: AuditRequest, x_provider_key: str | None = Header(default=None)):
    if req.mode not in audit.MODES:
        raise HTTPException(422, f"mode must be one of {audit.MODES}")
    if req.provider not in llm.PROVIDERS or req.model not in llm.PROVIDERS[req.provider]["models"]:
        raise HTTPException(422, "unknown provider or model")
    if req.effort not in ("low", "medium", "high"):
        raise HTTPException(422, "effort must be low, medium or high")
    key = resolve_key(req.provider, x_provider_key)
    if not key:
        raise HTTPException(400, "an API key is required (X-Provider-Key header)")
    conv, is_upload = _conversation(req)
    backend = llm.Backend(req.provider, req.model, api_key=key, effort=req.effort)
    events: queue.Queue = queue.Queue()

    def worker():
        ctx = None
        try:
            ctx = index.ConversationContext.build(conv, store())
            rec = audit.audit(ctx, req.mode, backend, on_step=lambda e: events.put({"type": "tool", **e}))
            events.put({"type": "result", "audit": rec})
        except Exception as exc:  # report without the key
            events.put({"type": "error", "message": safe_error(exc, key)})
        finally:
            if ctx is not None and is_upload:
                ctx.store.forget(ctx.key)
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        yield _sse({"type": "start", "conversation_id": conv.conv_id, "turns": len(conv.turns), "mode": req.mode})
        while (event := events.get()) is not None:
            yield _sse(event)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
