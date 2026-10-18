"""Write results/metrics.json, results/metrics.md and the detection figure."""

import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config, policy  # noqa: E402

MODE_NAMES = {"full": "Full transcript", "rag": "RAG (fixed queries)", "agentic": "Agentic RAG (tools)"}
# Categorical slots 1-3 of the reference palette, checked with the dataviz
# validator on the light surface; bars carry value labels because slot 3 is
# below 3:1 contrast.
COLORS = {"full": "#2a78d6", "rag": "#eb6834", "agentic": "#1baf7a"}
SURFACE, INK, MUTED = "#fcfcfb", "#0b0b0b", "#52514e"


def pct(x: float) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.0f}%"


def ci(pair) -> str:
    return f"{pct(pair[0])}–{pct(pair[1])}"


def markdown(report: dict) -> str:
    modes = report["modes"]
    b = report["benchmark"]
    out = ["# Evaluation results", "",
           f"`{report['model']}` audits of the benchmark: {report['conversations_compared']} conversations, "
           f"every mode scored on the same ones. Ground truth is the planted violations in "
           f"`data/benchmark/manifest.json`.", "",
           "## Overall", "",
           "| Method | Recall | 95% CI | Precision | 95% CI | F1 | Clean chats flagged | Near-miss false alarms | "
           "Finding cites the planted turn | Severity exact | Weighted κ | Quotes found in cited turn | "
           "Mean tool calls | Cost |",
           "|---" * 14 + "|"]
    for mode, r in modes.items():
        o = r["overall"]
        out.append(
            f"| {MODE_NAMES[mode]} | **{pct(o['recall'])}** | {ci(o['ci95']['recall'])} | **{pct(o['precision'])}** | "
            f"{ci(o['ci95']['precision'])} | {o['f1']:.2f} | {pct(r['clean_flagged'])} of {r['clean_chats']} | "
            f"{pct(r['near_miss_flagged'])} of {r['near_misses']} | {pct(r['localised_exact'])} | "
            f"{pct(r['severity_exact'])} | {r['kappa_qw']:.2f} | {pct(r['quotes_in_cited_turn'])} of {r['quotes']} | "
            f"{r['mean_tool_calls']:.1f} | ${r['cost_usd']:.2f} |")
    out += ["", "A baseline that never flags anything has 0% recall, no false alarms and κ 0.", "",
            "## Recall and precision by category", "",
            "| Category | " + " | ".join(MODE_NAMES[m] for m in modes) + " |", "|---" * (1 + len(modes)) + "|"]
    for cat, name in policy.CATEGORIES.items():
        cells = []
        for r in modes.values():
            c = r["categories"][cat]
            cells.append(f"R {pct(c['recall'])} · P {pct(c['precision'])} ({c['tp'] + c['fn']} planted)")
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    out += ["", "## Recall by subtlety and severity", "",
            "| Planted as | " + " | ".join(MODE_NAMES[m] for m in modes) + " |", "|---" * (1 + len(modes)) + "|"]
    keys = [("recall_by_subtlety", k) for k in ("obvious", "subtle")] + \
           [("recall_by_severity", k) for k in ("minor", "major", "critical")]
    for field, k in keys:
        out.append(f"| {k} | " + " | ".join(pct(r[field].get(k, float("nan"))) for r in modes.values()) + " |")
    out += ["", "## Benchmark", "",
            f"- Plans: {b['plans']}",
            f"- Planted items: {b['items']}",
            f"- Violation severities: {b['severities']}; subtlety: {b['subtlety']}",
            f"- Generator: `{b['generator']['provider']}/{b['generator']['model']}`, independently re-checked: "
            f"{b['generator']['verified']}; generation stats {b['generator_stats']}",
            "", "Unmodified chats may contain real policy slips, which count as false positives, "
            "so precision is a lower bound.", ""]
    return "\n".join(out)


def figure(report: dict, path) -> None:
    modes = report["modes"]
    cats = list(policy.CATEGORIES)
    fig, ax = plt.subplots(figsize=(11, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    width = 0.8 / len(modes)
    for k, (mode, r) in enumerate(modes.items()):
        xs = [i + (k - (len(modes) - 1) / 2) * width for i in range(len(cats))]
        vals = [r["categories"][c]["recall"] for c in cats]
        vals = [0 if math.isnan(v) else v for v in vals]
        ax.bar(xs, vals, width - 0.03, color=COLORS[mode], label=MODE_NAMES[mode], zorder=2)
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.015, f"{100 * v:.0f}", ha="center", va="bottom", fontsize=8, color=MUTED)
    ax.set_xticks(range(len(cats)), [policy.CATEGORIES[c] for c in cats], color=INK, fontsize=9)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"], color=MUTED, fontsize=8)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c9c8c2")
    ax.tick_params(length=0)
    ax.set_title(f"Planted violations detected, by category ({report['model']}, "
                 f"{report['conversations_compared']} conversations)", color=INK, fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=9, loc="upper right", ncol=len(modes))
    fig.tight_layout()
    fig.savefig(path, dpi=140, facecolor=SURFACE)
    plt.close(fig)


def write(report: dict, out_dir=None) -> None:
    out_dir = out_dir or config.RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "metrics.md").write_text(markdown(report), encoding="utf-8")
    figure(report, out_dir / "detection_by_category.png")
