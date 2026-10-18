"""Build and load the benchmark (data/benchmark/benchmark.jsonl + manifest.json).

Planting is resumable: each finished chat is cached in .cache/benchmark/, so a
run stopped by a provider limit continues where it left off.
"""

import datetime
import hashlib
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config, plant, transcripts

BENCH_DIR = config.DATA_DIR / "benchmark"
CONVERSATIONS = BENCH_DIR / "benchmark.jsonl"
MANIFEST = BENCH_DIR / "manifest.json"
CACHE = config.CACHE_DIR / "benchmark"
MIN_TURNS = 24


def _rng(seed: int, conv_id: str) -> random.Random:
    """A per-chat RNG, so results do not depend on thread order."""
    digest = hashlib.sha256(f"{seed}:{conv_id}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def build(n: int, seed: int, backend, verify: bool = True, workers: int = 2, log=None) -> dict:
    log = log or (lambda msg: print(msg, flush=True))
    convs = transcripts.load_abcd(split="test")
    rng = random.Random(seed)
    chosen = plant.select_chats(convs, n, MIN_TURNS, rng)
    plans = plant.make_plan([c.conv_id for c in chosen], rng)
    by_id = {c.conv_id: c for c in chosen}
    CACHE.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    def work(cid):
        cached = CACHE / f"{seed}-{cid}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        conv, planned = by_id[cid], plans[cid]
        if planned:
            new, items, stats = plant.plant(conv, planned, backend, _rng(seed, cid), verify=verify)
        else:
            meta = {**{k: v for k, v in conv.meta.items() if k != "scenario"}, "abcd_id": conv.conv_id}
            new, items, stats = transcripts.Conversation(cid, "benchmark", conv.turns, meta), [], {}
        rec = {"conversation": transcripts.to_dict(new), "planned": planned, "items": items, "stats": stats}
        with lock:
            cached.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return rec

    results, failed = {}, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, cid): cid for cid in plans}
        for k, fut in enumerate(as_completed(futures), 1):
            cid = futures[fut]
            try:
                results[cid] = fut.result()
                items = results[cid]["items"]
                log(f"[{k}/{len(plans)}] {cid}: {plant.plan_label(items)} "
                    + " ".join(f"{i['category']}/{i['severity']}@{i['turn']}" for i in items))
            except Exception as exc:  # report and keep going; a rerun resumes
                failed.append(cid)
                log(f"[{k}/{len(plans)}] {cid}: ERROR {exc!r}")
    if failed:
        raise SystemExit(f"{len(failed)} chats failed; rerun the same command to resume")

    order = sorted(results, key=int)
    transcripts.save_jsonl([transcripts.from_dict(results[c]["conversation"]) for c in order], CONVERSATIONS)
    totals = {"generated": 0, "rejected": 0, "dropped": 0}
    for r in results.values():
        for k in totals:
            totals[k] += r["stats"].get(k, 0)
    manifest = {
        "version": 1,
        "created": datetime.date.today().isoformat(),
        "source": "ABCD v1.1 test split (ASAPP, MIT licence)",
        "selection": f"{len(order)} chats with at least {MIN_TURNS} turns, seed {seed}",
        "generator": {"provider": backend.provider, "model": backend.model, "verified": verify},
        "stats": totals,
        "conversations": {c: {"plan": plant.plan_label(results[c]["items"]), "planned": len(results[c]["planned"]),
                              "items": results[c]["items"]} for c in order},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def load_manifest(path=None) -> dict:
    return json.loads((path or MANIFEST).read_text(encoding="utf-8"))
