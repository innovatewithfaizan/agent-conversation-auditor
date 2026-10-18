"""Command line entry point: python -m auditor <command>.

    download   fetch ABCD and/or a CallCenterEN domain into data/raw/
    show       print one conversation as the auditor will see it
    stats      turn counts per dataset
"""

import argparse
import statistics

from . import config, datasets, transcripts


def load(source: str, domain: str, split: str) -> list[transcripts.Conversation]:
    if source == "abcd":
        return transcripts.load_abcd(split=split)
    return transcripts.load_callcenter(config.CALLCENTER_DIR / datasets.CALLCENTER_DOMAINS[domain])


def cmd_download(args) -> None:
    if args.source in ("abcd", "all"):
        for path in datasets.download_abcd():
            print(f"{path.relative_to(config.ROOT)} ({path.stat().st_size / 1e6:.1f} MB)")
    if args.source in ("callcenter", "all"):
        path = datasets.download_callcenter(args.domain)
        print(f"{path.relative_to(config.ROOT)} ({path.stat().st_size / 1e6:.1f} MB)")
        print("CallCenterEN is CC BY-NC 4.0: non-commercial use, and never commit the raw files.")


def cmd_show(args) -> None:
    convs = {c.conv_id: c for c in load(args.source, args.domain, args.split)}
    conv = convs.get(args.conv_id) if args.conv_id else next(iter(convs.values()))
    if conv is None:
        raise SystemExit(f"no conversation {args.conv_id!r} in {args.source}")
    print(f"# {conv.source}:{conv.conv_id} {({k: v for k, v in conv.meta.items() if k != 'scenario'})}")
    print(transcripts.render(conv.turns))


def cmd_stats(args) -> None:
    convs = load(args.source, args.domain, args.split)
    lengths = [len(c.turns) for c in convs]
    speakers = {}
    for c in convs:
        for t in c.turns:
            speakers[t.speaker] = speakers.get(t.speaker, 0) + 1
    print(f"{len(convs)} conversations; turns per conversation: median {statistics.median(lengths):.0f}, "
          f"min {min(lengths)}, max {max(lengths)}; turns by speaker: {speakers}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="auditor", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def source_args(p):
        p.add_argument("source", choices=["abcd", "callcenter"])
        p.add_argument("--domain", default="medical_equipment_outbound", choices=list(datasets.CALLCENTER_DOMAINS))
        p.add_argument("--split", default="test", choices=["train", "dev", "test"], help="ABCD split")

    p = sub.add_parser("download")
    p.add_argument("source", choices=["abcd", "callcenter", "all"])
    p.add_argument("--domain", default="medical_equipment_outbound", choices=list(datasets.CALLCENTER_DOMAINS))
    p.set_defaults(fn=cmd_download)
    p = sub.add_parser("show")
    source_args(p)
    p.add_argument("conv_id", nargs="?", help="default: the first conversation")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("stats")
    source_args(p)
    p.set_defaults(fn=cmd_stats)
    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
