"""Score audits against the benchmark's planted ground truth.

A category is "flagged" when the auditor gives it any severity above none.
Detection is scored per conversation and category: a true positive is a
flagged category that has a planted violation. On top of that:

* clean chats flagged   - share of untouched chats with any flag at all
* near-miss false alarm - share of compliant look-alikes flagged in their category
* localisation          - for detected violations, whether a finding cites the
                          planted turn (exactly, or anywhere in the inserted exchange)
* severity              - exact agreement on detected violations, and
                          quadratic-weighted kappa over every conversation x category
* grounding             - share of quotes found in the turn they cite
* 95% bootstrap intervals over conversations (2,000 resamples, seed 0)

Unmodified ABCD chats may contain real policy slips. They count as false
positives here, so precision is a lower bound.
"""

import json
import random
import re
import statistics

import numpy as np

from . import benchmark, config, policy, transcripts
from .plant import truth as planted_truth

K = len(policy.SEVERITIES)


def weighted_kappa(pairs: list[tuple[str, str]]) -> float:
    m = np.zeros((K, K))
    for t, p in pairs:
        m[policy.LEVEL[t], policy.LEVEL[p]] += 1
    n = m.sum()
    if n == 0:
        return float("nan")
    i, j = np.indices((K, K))
    w = (i - j) ** 2 / (K - 1) ** 2
    expected = np.outer(m.sum(1), m.sum(0)) / n
    denom = (w * expected).sum()
    return float(1 - (w * m).sum() / denom) if denom else float("nan")


def _ratio(a: int, b: int) -> float:
    return a / b if b else float("nan")


def detection(pairs: list[tuple[str, str]]) -> dict:
    """pairs of (true severity, predicted severity)."""
    tp = sum(t != "none" and p != "none" for t, p in pairs)
    fp = sum(t == "none" and p != "none" for t, p in pairs)
    fn = sum(t != "none" and p == "none" for t, p in pairs)
    tn = sum(t == "none" and p == "none" for t, p in pairs)
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    f1 = 2 * precision * recall / (precision + recall) if tp else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1,
            "specificity": _ratio(tn, tn + fp)}


def bootstrap(per_conv: dict[str, list[tuple[str, str]]], iters: int = 2000, seed: int = 0) -> dict:
    ids = list(per_conv)
    rng = random.Random(seed)
    stats = {"precision": [], "recall": [], "f1": []}
    for _ in range(iters):
        sample = [p for _ in ids for p in per_conv[rng.choice(ids)]]
        d = detection(sample)
        for k in stats:
            if not np.isnan(d[k]):
                stats[k].append(d[k])
    out = {}
    for k, vals in stats.items():
        vals.sort()
        out[k] = [vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]] if vals else [float("nan")] * 2
    return out


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def load_audits(model: str, mode: str, dataset: str = "benchmark") -> dict[str, dict]:
    out = {}
    for path in sorted(config.audits_dir(model, mode, dataset).glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        out[rec["conv_id"]] = rec
    return out


def evaluate_mode(audits: dict, ids: list[str], manifest: dict, convs: dict) -> dict:
    gold = planted_truth(manifest)
    cats = list(policy.CATEGORIES)
    per_conv = {cid: [(gold[cid][c], audits[cid]["categories"][c]["severity"]) for c in cats] for cid in ids}
    pooled = [p for pairs in per_conv.values() for p in pairs]
    by_cat = {c: detection([per_conv[cid][k] for cid in ids]) for k, c in enumerate(cats)}

    clean = [cid for cid in ids if manifest["conversations"][cid]["plan"] == "clean"]
    clean_flagged = sum(any(p != "none" for _, p in per_conv[cid]) for cid in clean)

    near, near_flagged, viol, by_subtlety, by_severity = 0, 0, [], {}, {}
    for cid in ids:
        for it in manifest["conversations"][cid]["items"]:
            pred = audits[cid]["categories"][it["category"]]
            if it["kind"] == "near_miss":
                near += 1
                near_flagged += pred["severity"] != "none"
                continue
            hit = pred["severity"] != "none"
            turns = [f["turn"] for f in pred["findings"]]
            viol.append({"hit": hit, "exact_turn": hit and it["turn"] in turns,
                         "in_exchange": hit and any(t in it["inserted_turns"] for t in turns),
                         "severity_exact": hit and pred["severity"] == it["severity"]})
            by_subtlety.setdefault(it["subtlety"], []).append(hit)
            by_severity.setdefault(it["severity"], []).append(hit)
    detected = [v for v in viol if v["hit"]]

    quotes = in_turn = anywhere = 0
    for cid in ids:
        turns = convs[cid].turns
        whole = _norm(" ".join(t.text for t in turns))
        for c in cats:
            for f in audits[cid]["categories"][c]["findings"]:
                q = _norm(f["quote"])
                if not q:
                    continue
                quotes += 1
                in_turn += q in _norm(turns[f["turn"]].text)
                anywhere += q in whole

    recs = [audits[cid] for cid in ids]
    return {
        "conversations": len(ids),
        "overall": {**detection(pooled), "ci95": bootstrap(per_conv)},
        "categories": by_cat,
        "clean_chats": len(clean),
        "clean_flagged": _ratio(clean_flagged, len(clean)),
        "near_misses": near,
        "near_miss_flagged": _ratio(near_flagged, near),
        "violations": len(viol),
        "localised_exact": _ratio(sum(v["exact_turn"] for v in detected), len(detected)),
        "localised_exchange": _ratio(sum(v["in_exchange"] for v in detected), len(detected)),
        "severity_exact": _ratio(sum(v["severity_exact"] for v in detected), len(detected)),
        "kappa_qw": weighted_kappa(pooled),
        "recall_by_subtlety": {k: _ratio(sum(v), len(v)) for k, v in sorted(by_subtlety.items())},
        "recall_by_severity": {k: _ratio(sum(by_severity[k]), len(by_severity[k]))
                               for k in policy.SEVERITIES if k in by_severity},
        "quotes": quotes,
        "quotes_in_cited_turn": _ratio(in_turn, quotes),
        "quotes_in_conversation": _ratio(anywhere, quotes),
        "mean_tool_calls": statistics.mean(len(r["tool_calls"]) for r in recs),
        "median_seconds": statistics.median(r["seconds"] for r in recs),
        "cost_usd": round(sum(r["usage"]["cost_usd"] for r in recs), 4),
        "model": recs[0]["model"],
    }


def composition(manifest: dict, ids: list[str]) -> dict:
    plans, cats, sevs, subtle = {}, {}, {}, {}
    for cid in ids:
        entry = manifest["conversations"][cid]
        plans[entry["plan"]] = plans.get(entry["plan"], 0) + 1
        for it in entry["items"]:
            key = f"{it['kind']}:{it['category']}"
            cats[key] = cats.get(key, 0) + 1
            if it["kind"] == "violation":
                sevs[it["severity"]] = sevs.get(it["severity"], 0) + 1
                subtle[it["subtlety"]] = subtle.get(it["subtlety"], 0) + 1
    return {"plans": plans, "items": cats, "severities": sevs, "subtlety": subtle,
            "generator": manifest["generator"], "generator_stats": manifest["stats"]}


def run(model: str, modes=("full", "rag", "agentic"), manifest: dict | None = None, convs_path=None) -> dict:
    """Score every mode that has audits, all on the same conversations."""
    manifest = manifest or benchmark.load_manifest()
    convs = {c.conv_id: c for c in transcripts.load_jsonl(convs_path or benchmark.CONVERSATIONS)}
    present = {m: load_audits(model, m) for m in modes}
    present = {m: a for m, a in present.items() if a}
    if not present:
        raise SystemExit(f"no audits for {model} in {config.AUDITS_DIR}")
    ids = sorted((cid for cid in manifest["conversations"] if all(cid in a for a in present.values())), key=int)
    return {
        "model": model,
        "conversations_compared": len(ids),
        "audits_available": {m: len(a) for m, a in present.items()},
        "benchmark": composition(manifest, ids),
        "modes": {m: evaluate_mode(a, ids, manifest, convs) for m, a in present.items()},
    }
