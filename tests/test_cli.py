"""Dataset downloads (network stubbed) and the show/stats commands."""

import gzip
import json

import pytest

from auditor import __main__ as cli
from auditor import config, datasets

RECORD = {"convo_id": 7, "scenario": {"flow": "account_access", "subflow": "reset_2fa"},
          "original": [["agent", "Hello"], ["customer", "I can't log in."], ["action", "Account pulled up."]]}


def test_downloads_skip_existing_files_and_reject_unknown_domains(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ABCD_DIR", tmp_path / "abcd")
    fetched = []

    def fake_retrieve(url, dest):
        fetched.append(url)
        open(dest, "w").write("x")

    monkeypatch.setattr(datasets.urllib.request, "urlretrieve", fake_retrieve)
    paths = datasets.download_abcd()
    assert [p.name for p in paths] == datasets.ABCD_FILES and all(p.exists() for p in paths)
    assert not list((tmp_path / "abcd").glob("*.part"))
    datasets.download_abcd()
    assert len(fetched) == len(datasets.ABCD_FILES)  # second call downloads nothing
    with pytest.raises(ValueError, match="unknown domain"):
        datasets.download_callcenter("cooking")


def test_show_and_stats_on_a_small_abcd_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "ABCD_DIR", tmp_path)
    with gzip.open(tmp_path / "abcd_v1.1.json.gz", "wt", encoding="utf-8") as fh:
        json.dump({"train": [], "dev": [], "test": [RECORD]}, fh)
    cli.main(["show", "abcd", "7"])
    out = capsys.readouterr().out
    assert "# abcd:7" in out and "[2] system: Account pulled up." in out
    cli.main(["stats", "abcd"])
    assert "1 conversations" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["show", "abcd", "999"])


def test_estimate_and_audit_commands_on_a_jsonl_dataset(monkeypatch, tmp_path, capsys):
    from auditor import index, transcripts
    from test_audit import CONV, FakeBackend, submit

    path = tmp_path / "bench.jsonl"
    transcripts.save_jsonl([CONV], path)
    cli.main(["estimate", str(path), "--model", "gpt-5-mini"])
    out = capsys.readouterr().out
    assert "1 conversations" in out and "agentic" in out and "total" in out

    monkeypatch.setattr(config, "AUDITS_DIR", tmp_path / "audits")
    monkeypatch.setattr(cli, "make_backend", lambda args: FakeBackend([submit()]))
    monkeypatch.setattr(index, "persistent_store", index.memory_store)
    cli.main(["audit", str(path), "--mode", "full", "--model", "fake/model"])
    saved = tmp_path / "audits" / "fake_model" / "full" / "bench" / "c1.json"
    rec = json.loads(saved.read_text())
    assert rec["dataset"] == "bench" and rec["categories"]["verification"]["severity"] == "major"
    cli.main(["audit", str(path), "--mode", "full", "--model", "fake/model"])  # resumes: nothing to do
    assert "auditing 0 conversations" in capsys.readouterr().out
