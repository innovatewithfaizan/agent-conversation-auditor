"""Planting, the manifest and the evaluation metrics (fake LLMs, no API calls)."""

import json
import math
import random
from types import SimpleNamespace

import pytest

from auditor import evaluate, plant, policy, report
from auditor.transcripts import Conversation, Turn

SPEAKERS = ["agent", "customer"] * 6 + ["system"] + ["agent", "customer"] * 6
CONV = Conversation("100", "abcd", [Turn(i, s, f"turn {i} from {s}") for i, s in enumerate(SPEAKERS)],
                    {"flow": "product_defect", "subflow": "return_size", "scenario": {"personal": {}}})


def call(name, args):
    return SimpleNamespace(id="x", function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def reply(name, args):
    msg = SimpleNamespace(content="", tool_calls=[call(name, args)])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)


class ScriptedBackend:
    """Answers insert_turns and submit_judgement calls from two scripts."""

    provider, model = "groq", "qwen/qwen3.8-27b"

    def __init__(self, inserts, verdicts):
        self.inserts, self.verdicts = iter(inserts), iter(verdicts)

    def chat(self, messages, tools, tool_choice):
        name = tool_choice["function"]["name"]
        if name == plant.SUBMIT:
            return reply(name, next(self.inserts))
        return reply(name, {"violates": next(self.verdicts), "reason": "r"})


TWO_TURNS = {"turns": [{"speaker": "customer", "text": "Can I speak to a manager?"},
                       {"speaker": "agent", "text": "No, managers don't take calls."}], "key_turn": 1}
ONE_TURN = {"turns": [{"speaker": "agent", "text": "I'll refund it now, no need to check anything."}], "key_turn": 0}


def test_insertion_points_follow_the_category():
    rng = random.Random(0)
    assert plant.insertion_point(CONV, "verification", rng) == 2  # after the first customer turn, before tools
    for _ in range(20):
        pos = plant.insertion_point(CONV, "escalation", rng)
        assert CONV.turns[pos - 1].speaker == "customer" and 7 <= pos <= 22


def test_plant_inserts_turns_and_records_their_final_positions():
    items = [{"kind": "violation", "category": "verification", "severity": "major", "subtlety": "obvious"},
             {"kind": "violation", "category": "escalation", "severity": "major", "subtlety": "subtle"}]
    backend = ScriptedBackend([ONE_TURN, TWO_TURNS], [True, True])
    new, manifest_items, stats = plant.plant(CONV, items, backend, random.Random(1))
    assert len(new.turns) == len(CONV.turns) + 3 and stats == {"generated": 2, "rejected": 0, "dropped": 0}
    assert [t.idx for t in new.turns] == list(range(len(new.turns)))
    for it in manifest_items:
        assert new.turns[it["turn"]].text == it["text"] and new.turns[it["turn"]].speaker == "agent"
        assert it["turn"] in it["inserted_turns"]
    v = next(i for i in manifest_items if i["category"] == "verification")
    assert v["turn"] == 2 and v["inserted_turns"] == [2]
    assert new.source == "benchmark" and new.meta["abcd_id"] == "100" and "scenario" not in new.meta


def test_failed_checks_are_regenerated_then_dropped():
    item = [{"kind": "violation", "category": "promises", "severity": "major", "subtlety": "obvious"}]
    _, kept, stats = plant.plant(CONV, item, ScriptedBackend([ONE_TURN, ONE_TURN], [False, True]), random.Random(2))
    assert len(kept) == 1 and stats == {"generated": 2, "rejected": 1, "dropped": 0}
    new, kept, stats = plant.plant(CONV, item, ScriptedBackend([ONE_TURN, ONE_TURN], [False, False]), random.Random(2))
    assert kept == [] and stats["dropped"] == 1 and len(new.turns) == len(CONV.turns)


def test_near_misses_must_be_judged_compliant_and_key_turn_must_be_the_agents():
    near = [{"kind": "near_miss", "category": "conduct", "severity": "none", "subtlety": "n/a"}]
    _, kept, _ = plant.plant(CONV, near, ScriptedBackend([ONE_TURN], [False]), random.Random(3))
    assert kept[0]["kind"] == "near_miss"
    bad_key = {"turns": [{"speaker": "customer", "text": "hi"}], "key_turn": 0}
    _, kept, stats = plant.plant(CONV, near, ScriptedBackend([bad_key, bad_key], []), random.Random(3))
    assert kept == [] and stats["rejected"] == 2


def test_plan_mixes_clean_near_miss_and_violation_chats():
    ids = [str(i) for i in range(40)]
    plans = plant.make_plan(ids, random.Random(7))
    labels = [plant.plan_label(items) for items in plans.values()]
    assert labels.count("clean") == 10 and labels.count("near_miss") == 8 and labels.count("violations") == 22
    for items in plans.values():
        cats = [i["category"] for i in items]
        assert len(cats) == len(set(cats))  # never two items in one category


def manifest_for(entries):
    return {"generator": {"provider": "groq", "model": "q", "verified": True}, "stats": {},
            "conversations": {cid: {"plan": plant.plan_label(items), "items": items} for cid, items in entries.items()}}


def audit_rec(cid, flags, turns=None):
    cats = {}
    for c in policy.CATEGORIES:
        sev = flags.get(c, "none")
        turn = (turns or {}).get(c, 0)
        findings = [] if sev == "none" else [{"turn": turn, "quote": f"turn {turn} from agent", "explanation": "e"}]
        cats[c] = {"severity": sev, "findings": findings}
    return {"conv_id": cid, "categories": cats, "tool_calls": [], "seconds": 1.0,
            "usage": {"cost_usd": 0.001}, "model": "m"}


def test_evaluation_metrics_match_a_hand_count():
    v = {"kind": "violation", "category": "promises", "severity": "major", "subtlety": "obvious",
         "turn": 5, "inserted_turns": [4, 5], "text": "t"}
    nm = {"kind": "near_miss", "category": "conduct", "severity": "none", "subtlety": "n/a",
          "turn": 3, "inserted_turns": [3], "text": "t"}
    manifest = manifest_for({"1": [v], "2": [nm], "3": [], "4": [{**v, "subtlety": "subtle", "severity": "minor"}]})
    audits = {
        "1": audit_rec("1", {"promises": "major"}, {"promises": 5}),  # TP, exact turn, exact severity
        "2": audit_rec("2", {"conduct": "minor"}),                    # near-miss false alarm (FP)
        "3": audit_rec("3", {}),                                      # clean, correct
        "4": audit_rec("4", {}),                                      # missed subtle violation (FN)
    }
    convs = {c: Conversation(c, "benchmark", [Turn(i, "agent", f"turn {i} from agent") for i in range(8)])
             for c in audits}
    r = evaluate.evaluate_mode(audits, ["1", "2", "3", "4"], manifest, convs)
    o = r["overall"]
    assert (o["tp"], o["fp"], o["fn"], o["tn"]) == (1, 1, 1, 17)
    assert o["recall"] == 0.5 and o["precision"] == 0.5
    assert r["clean_flagged"] == 0 and r["near_miss_flagged"] == 1.0
    assert r["localised_exact"] == 1.0 and r["severity_exact"] == 1.0
    assert r["recall_by_subtlety"] == {"obvious": 1.0, "subtle": 0.0}
    assert r["quotes_in_cited_turn"] == 1.0 and r["quotes"] == 2
    lo, hi = o["ci95"]["recall"]
    assert 0 <= lo <= 0.5 <= hi <= 1


def test_weighted_kappa_edges():
    assert math.isclose(evaluate.weighted_kappa([("none", "none"), ("major", "major"), ("critical", "critical")]), 1.0)
    assert evaluate.weighted_kappa([("none", "none"), ("none", "none")]) != evaluate.weighted_kappa([])  # nan for empty


def test_report_markdown_and_figure(tmp_path):
    v = {"kind": "violation", "category": "promises", "severity": "major", "subtlety": "obvious",
         "turn": 1, "inserted_turns": [1], "text": "t"}
    manifest = manifest_for({"1": [v], "2": []})
    audits = {"1": audit_rec("1", {"promises": "major"}, {"promises": 1}), "2": audit_rec("2", {})}
    convs = {c: Conversation(c, "benchmark", [Turn(i, "agent", f"turn {i} from agent") for i in range(3)])
             for c in audits}
    mode = evaluate.evaluate_mode(audits, ["1", "2"], manifest, convs)
    rep = {"model": "m", "conversations_compared": 2, "audits_available": {"full": 2},
           "benchmark": evaluate.composition(manifest, ["1", "2"]), "modes": {"full": mode}}
    report.write(rep, tmp_path)
    md = (tmp_path / "metrics.md").read_text()
    assert "| Full transcript | **100%**" in md and "Commitments and claims" in md
    assert (tmp_path / "detection_by_category.png").stat().st_size > 1000
    assert json.loads((tmp_path / "metrics.json").read_text())["conversations_compared"] == 2


def test_truth_takes_the_worst_planted_severity():
    items = [{"kind": "violation", "category": "conduct", "severity": "minor"},
             {"kind": "near_miss", "category": "promises", "severity": "none"}]
    gold = plant.truth(manifest_for({"9": items}))
    assert gold["9"]["conduct"] == "minor" and gold["9"]["promises"] == "none"


def test_policy_sections_carry_one_category():
    sec = policy.section("verification")
    assert "## 2. Identity verification (`verification`)" in sec and "(`promises`)" not in sec
    assert sec.startswith("# Customer support policy")


def test_patient_backend_waits_out_daily_limits_only():
    import openai
    from auditor import benchmark

    def limit_error(msg):
        return openai.RateLimitError(msg, response=SimpleNamespace(request=None, status_code=429, headers={}), body=None)

    calls, slept = [], []

    class Flaky:
        provider, model = "groq", "q"

        def chat(self, *a):
            calls.append(1)
            if len(calls) == 1:
                raise limit_error("tokens per day (TPD) ... Please try again in 1m30.5s.")
            return "ok"

    patient = benchmark.Patient(Flaky(), log=lambda m: None, sleep=slept.append)
    assert patient.chat([], [], "auto") == "ok" and slept == [95.5]
    assert benchmark.retry_after(Exception("tokens per minute, try again in 2s")) is None

    class PerMinute(Flaky):
        def chat(self, *a):
            raise limit_error("tokens per minute (TPM): try again in 2s")

    with pytest.raises(openai.RateLimitError):
        benchmark.Patient(PerMinute(), log=lambda m: None, sleep=slept.append).chat([], [], "auto")
