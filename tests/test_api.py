"""The HTTP API: read endpoints, uploads and the streamed live audit (no API calls)."""

import json

import pytest
from fastapi.testclient import TestClient

from auditor import api, benchmark, config, transcripts
from auditor.transcripts import Conversation, Turn

CONV = Conversation("501", "benchmark", [Turn(0, "customer", "I want a refund."),
                                         Turn(1, "agent", "Done, no need to verify.")],
                    {"flow": "product_defect", "subflow": "return_size", "abcd_id": "501"})
ITEM = {"kind": "violation", "category": "verification", "severity": "major", "subtlety": "obvious",
        "turn": 1, "inserted_turns": [1], "text": "Done, no need to verify."}


@pytest.fixture
def client(monkeypatch, tmp_path):
    bench_dir = tmp_path / "benchmark"
    monkeypatch.setattr(benchmark, "CONVERSATIONS", bench_dir / "benchmark.jsonl")
    monkeypatch.setattr(benchmark, "MANIFEST", bench_dir / "manifest.json")
    transcripts.save_jsonl([CONV], benchmark.CONVERSATIONS)
    benchmark.MANIFEST.write_text(json.dumps({"conversations": {"501": {"plan": "violations", "items": [ITEM]}}}))
    monkeypatch.setattr(config, "AUDITS_DIR", tmp_path / "audits")
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "results")
    saved = tmp_path / "audits" / "m" / "full" / "benchmark"
    saved.mkdir(parents=True)
    cats = {c: {"severity": "none", "findings": []} for c in ("personal_data", "verification")}
    cats["verification"] = {"severity": "major", "findings": [{"turn": 1, "quote": "q", "explanation": "e"}]}
    (saved / "501.json").write_text(json.dumps({"model": "m", "mode": "full", "conv_id": "501", "categories": cats}))
    metrics = tmp_path / "results" / "metrics" / "m"
    metrics.mkdir(parents=True)
    (metrics / "metrics.json").write_text(json.dumps({"model": "m", "conversations_compared": 1}))
    api.bench.cache_clear()
    monkeypatch.setattr(api, "DEV_ENV_KEYS", False)
    yield TestClient(api.app)
    api.bench.cache_clear()


def test_read_endpoints(client):
    assert client.get("/api/health").json() == {"ok": True, "benchmark_conversations": 1}
    pol = client.get("/api/policy").json()
    assert "verification" in pol["categories"] and "Identity verification" in pol["text"]
    assert "groq" in client.get("/api/providers").json()
    rows = client.get("/api/conversations").json()
    assert rows == [{"id": "501", "turns": 2, "flow": "product_defect", "subflow": "return_size",
                     "plan": "violations", "planted": [{"kind": "violation", "category": "verification",
                                                         "severity": "major"}],
                     "audits": {"m": {"full": ["verification"]}}}]
    detail = client.get("/api/conversations/501").json()
    assert detail["ground_truth"]["items"][0]["turn"] == 1 and detail["audits"]["m"]["full"]["conv_id"] == "501"
    assert client.get("/api/conversations/999").status_code == 404
    assert client.get("/api/metrics").json()["m"]["conversations_compared"] == 1


def test_parse_upload(client):
    srt = b"1\n00:00:01,000 --> 00:00:02,000\nAgent: Hello\n\n2\n00:00:03,000 --> 00:00:04,000\nCaller: Hi\n"
    conv = client.post("/api/parse", files={"file": ("call.srt", srt)}).json()
    assert [t["speaker"] for t in conv["turns"]] == ["agent", "customer"]
    assert client.post("/api/parse", files={"file": ("notes.txt", b"x")}).status_code == 422
    big = b"x" * (api.MAX_UPLOAD_BYTES + 10)
    assert client.post("/api/parse", files={"file": ("call.srt", big)}).status_code == 413


def test_audit_needs_a_key_and_a_listed_model(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "server-key")
    body = {"conversation_id": "501", "mode": "full", "provider": "groq", "model": "openai/gpt-oss-120b"}
    assert client.post("/api/audit", json=body).status_code == 400  # no header, dev mode off
    assert client.post("/api/audit", json={**body, "model": "some/other"},
                       headers={"X-Provider-Key": "k"}).status_code == 422
    assert client.post("/api/audit", json={**body, "mode": "fast"}, headers={"X-Provider-Key": "k"}).status_code == 422
    assert api.resolve_key("groq", "", dev=True) == "server-key"
    assert api.resolve_key("groq", " visitor ", dev=True) == "visitor"


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_audit_streams_tool_calls_then_the_result(client, monkeypatch):
    seen = {}

    def fake_audit(ctx, mode, backend, on_step=None):
        seen["key"] = backend.api_key
        on_step({"tool": "read_turns", "input": {"first": 0, "last": 1}, "turns": 2})
        return {"conv_id": ctx.conv.conv_id, "mode": mode, "categories": {}}

    monkeypatch.setattr(api.audit, "audit", fake_audit)
    body = {"conversation_id": "501", "mode": "agentic", "provider": "groq", "model": "openai/gpt-oss-120b"}
    r = client.post("/api/audit", json=body, headers={"X-Provider-Key": "visitor-key"})
    assert r.headers["content-type"].startswith("text/event-stream")
    evs = events(r)
    assert [e["type"] for e in evs] == ["start", "tool", "result"]
    assert evs[1]["tool"] == "read_turns" and evs[2]["audit"]["conv_id"] == "501"
    assert seen["key"] == "visitor-key" and "visitor-key" not in r.text


def test_uploaded_turns_are_audited_and_errors_hide_the_key(client, monkeypatch):
    def failing_audit(ctx, mode, backend, on_step=None):
        raise RuntimeError(f"upstream said: bad key {backend.api_key}")

    monkeypatch.setattr(api.audit, "audit", failing_audit)
    body = {"turns": [{"speaker": "agent", "text": "Hi"}, {"speaker": "user", "text": "Card 4111 1111 1111 1111"}],
            "mode": "full", "provider": "openai", "model": "gpt-5-mini"}
    evs = events(client.post("/api/audit", json=body, headers={"X-Provider-Key": "sk-secret-123"}))
    assert evs[0]["conversation_id"].startswith("upload-") and evs[0]["turns"] == 2
    assert evs[-1]["type"] == "error" and "sk-secret-123" not in evs[-1]["message"] and "[key]" in evs[-1]["message"]
