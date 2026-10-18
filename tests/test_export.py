"""The static export the web app reads without an API."""

import json

from auditor import export
from test_api import client  # noqa: F401  (fixture: a tiny benchmark with one saved audit)


def test_export_writes_the_same_shapes_as_the_api(client, tmp_path):  # noqa: F811
    out = tmp_path / "data"
    assert export.export(out) == 1
    rows = json.loads((out / "conversations.json").read_text())
    assert rows == client.get("/api/conversations").json()
    detail = json.loads((out / "conversations" / "501.json").read_text())
    assert detail == client.get("/api/conversations/501").json()
    assert json.loads((out / "metrics.json").read_text())["m"]["conversations_compared"] == 1
    assert "categories" in json.loads((out / "policy.json").read_text())
    assert "groq" in json.loads((out / "providers.json").read_text())
    export.export(out)  # a rerun replaces the folder cleanly
    assert sorted(p.name for p in out.iterdir()) == ["conversations", "conversations.json", "metrics.json",
                                                     "policy.json", "providers.json"]


def test_export_can_take_explicit_files_and_a_note(client, tmp_path):  # noqa: F811
    from auditor import benchmark

    metrics = tmp_path / "pilot_metrics.json"
    metrics.write_text(json.dumps({"model": "gpt-5-mini", "conversations_compared": 1}))
    out = tmp_path / "data2"
    export.export(out, conversations=benchmark.CONVERSATIONS, manifest=benchmark.MANIFEST, metrics=metrics,
                  note="Pilot")
    assert json.loads((out / "metrics.json").read_text()) == {
        "gpt-5-mini": {"model": "gpt-5-mini", "conversations_compared": 1, "note": "Pilot"}}
