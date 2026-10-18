"""Command line entry point: python -m auditor <command>.

    download   fetch ABCD and/or a CallCenterEN domain into data/raw/
    show       print one conversation as the auditor will see it
    stats      turn counts per dataset
    estimate   token and cost estimate for the audit modes (no API calls)
    audit      audit conversations with an LLM (needs an API key)

A dataset is "abcd" (with --split), "callcenter" (with --domain) or a path
to a conversations .jsonl file such as the benchmark. audit skips
conversations that are already done, so a run stopped by a provider's daily
limit continues where it left off when you rerun it.
"""

import argparse
import json
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import audit, config, datasets, index, llm, transcripts


def load(args) -> tuple[str, list[transcripts.Conversation]]:
    """(dataset name for result folders, conversations)."""
    if args.dataset == "abcd":
        return f"abcd-{args.split}", transcripts.load_abcd(split=args.split)
    if args.dataset == "callcenter":
        zip_path = config.CALLCENTER_DIR / datasets.CALLCENTER_DOMAINS[args.domain]
        return f"callcenter-{args.domain}", transcripts.load_callcenter(zip_path)
    path = Path(args.dataset)
    if path.suffix != ".jsonl" or not path.exists():
        raise SystemExit(f"dataset must be abcd, callcenter or an existing .jsonl file, not {args.dataset!r}")
    return path.stem, transcripts.load_jsonl(path)


def select(args) -> tuple[str, list[transcripts.Conversation]]:
    name, convs = load(args)
    if getattr(args, "ids", None):
        wanted = args.ids.split(",")
        by_id = {c.conv_id: c for c in convs}
        convs = [by_id[i] for i in wanted if i in by_id]
    if getattr(args, "limit", None):
        convs = convs[: args.limit]
    return name, convs


def cmd_download(args) -> None:
    if args.source in ("abcd", "all"):
        for path in datasets.download_abcd():
            print(f"{path.relative_to(config.ROOT)} ({path.stat().st_size / 1e6:.1f} MB)")
    if args.source in ("callcenter", "all"):
        path = datasets.download_callcenter(args.domain)
        print(f"{path.relative_to(config.ROOT)} ({path.stat().st_size / 1e6:.1f} MB)")
        print("CallCenterEN is CC BY-NC 4.0: non-commercial use, and never commit the raw files.")


def cmd_show(args) -> None:
    _, convs = load(args)
    by_id = {c.conv_id: c for c in convs}
    conv = by_id.get(args.conv_id) if args.conv_id else convs[0]
    if conv is None:
        raise SystemExit(f"no conversation {args.conv_id!r} in {args.dataset}")
    print(f"# {conv.source}:{conv.conv_id} {({k: v for k, v in conv.meta.items() if k != 'scenario'})}")
    print(transcripts.render(conv.turns))


def cmd_stats(args) -> None:
    _, convs = load(args)
    lengths = [len(c.turns) for c in convs]
    speakers = {}
    for c in convs:
        for t in c.turns:
            speakers[t.speaker] = speakers.get(t.speaker, 0) + 1
    print(f"{len(convs)} conversations; turns per conversation: median {statistics.median(lengths):.0f}, "
          f"min {min(lengths)}, max {max(lengths)}; turns by speaker: {speakers}")


def cmd_estimate(args) -> None:
    """Rough token counts (chars / 4) and list-price cost per mode, without
    calling any API. RAG excerpts are approximated as the whole transcript, and
    output tokens and the agent's extra turns are assumptions: replace them
    with measured numbers from a pilot before a full run."""
    _, convs = select(args)
    out_tokens, agent_calls, tool_tokens = 1500, 2, 600
    system = len(audit.SYSTEM) // 4
    price_in, price_out = llm.PRICES.get(args.model, (0.0, 0.0))
    print(f"{len(convs)} conversations, {args.model} at ${price_in}/${price_out} per M tokens (approximate)")
    grand = 0.0
    for mode in audit.MODES:
        inp = out = 0
        for c in convs:
            body = len(transcripts.render(c.turns)) // 4
            if mode == "agentic":
                base = system + len(audit.AGENT_ADDENDUM) // 4 + body
                inp += agent_calls * base + (agent_calls - 1) * tool_tokens
                out += agent_calls * out_tokens
            else:
                inp += system + body
                out += out_tokens
        cost = (inp * price_in + out * price_out) / 1e6
        grand += cost
        print(f"  {mode:<8} {inp:>10,} in {out:>9,} out  ${cost:.2f}")
    print(f"  {'total':<8} ${grand:.2f}")


def daily_limit_hit(exc: Exception) -> bool:
    text = str(exc).lower()
    return "per day" in text or "(tpd)" in text or "(rpd)" in text


def run_all(items: list, key, work, workers: int) -> None:
    """Run work(item) in a small thread pool. Stops early if the provider's
    daily limit is reached; rerunning the command resumes."""
    stop = threading.Event()
    spent, failed = 0.0, []

    def guarded(item):
        return None if stop.is_set() else work(item)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(guarded, it): key(it) for it in items}
        for n, fut in enumerate(as_completed(futures), 1):
            name = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:  # keep going, report at the end
                if daily_limit_hit(exc) and not stop.is_set():
                    stop.set()
                    print(f"Daily limit reached at {name}; rerun the same command later to resume.", flush=True)
                failed.append(name)
                if not stop.is_set():
                    print(f"[{n}/{len(items)}] {name}: ERROR {exc!r}", flush=True)
                continue
            if result is None:
                continue
            summary, cost = result
            spent += cost
            print(f"[{n}/{len(items)}] {name}: {summary} (list price ${cost:.4f})", flush=True)
    print(f"estimated cost at list price: ${spent:.4f}" + (f"; not done: {len(failed)}" if failed else "; all done"))


def make_backend(args) -> llm.Backend:
    try:
        return llm.Backend(args.provider, args.model, effort=args.effort)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None


def cmd_audit(args) -> None:
    backend = make_backend(args)
    name, convs = select(args)
    out_dir = config.audits_dir(args.model, args.mode, name)
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [c for c in convs if not (out_dir / f"{c.conv_id}.json").exists()]
    print(f"auditing {len(todo)} conversations from {name}: mode={args.mode} {args.provider}/{args.model} "
          f"({len(convs) - len(todo)} already done)")
    store = index.persistent_store()

    def work(conv):
        rec = audit.audit(index.ConversationContext.build(conv, store), args.mode, backend)
        rec["dataset"] = name
        (out_dir / f"{conv.conv_id}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        flagged = " ".join(f"{c}={v['severity']}" for c, v in rec["categories"].items() if v["severity"] != "none")
        return f"{flagged or 'no violations'} tools={len(rec['tool_calls'])}", rec["usage"]["cost_usd"]

    run_all(todo, lambda c: c.conv_id, work, args.workers)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="auditor", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def dataset_args(p):
        p.add_argument("dataset", help="abcd, callcenter, or a conversations .jsonl file")
        p.add_argument("--domain", default="medical_equipment_outbound", choices=list(datasets.CALLCENTER_DOMAINS))
        p.add_argument("--split", default="test", choices=["train", "dev", "test"], help="ABCD split")

    def run_args(p):
        dataset_args(p)
        p.add_argument("--provider", default=config.PROVIDER, choices=list(llm.PROVIDERS))
        p.add_argument("--model", default=config.AUDITOR_MODEL)
        p.add_argument("--ids", help="comma-separated conversation ids")
        p.add_argument("--limit", type=int, help="only the first N conversations, for a pilot run")

    p = sub.add_parser("download")
    p.add_argument("source", choices=["abcd", "callcenter", "all"])
    p.add_argument("--domain", default="medical_equipment_outbound", choices=list(datasets.CALLCENTER_DOMAINS))
    p.set_defaults(fn=cmd_download)
    p = sub.add_parser("show")
    dataset_args(p)
    p.add_argument("conv_id", nargs="?", help="default: the first conversation")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("stats")
    dataset_args(p)
    p.set_defaults(fn=cmd_stats)
    p = sub.add_parser("estimate")
    run_args(p)
    p.set_defaults(fn=cmd_estimate)
    p = sub.add_parser("audit")
    run_args(p)
    p.add_argument("--mode", choices=audit.MODES, required=True)
    p.add_argument("--effort", default=config.EFFORT, choices=["low", "medium", "high"])
    p.add_argument("--workers", type=int, default=1)
    p.set_defaults(fn=cmd_audit)
    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
