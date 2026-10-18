"""Write the static JSON the web app reads when no API is configured
(web/public/data/), using the API's own functions so both serve the same shapes."""

import json
import shutil
from pathlib import Path

from . import api, benchmark, config

WEB_DATA = config.ROOT / "web" / "public" / "data"


def _write(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def export(out_dir=WEB_DATA, conversations: Path | None = None, manifest: Path | None = None,
           metrics: Path | None = None, note: str | None = None) -> int:
    """Write every file the app reads. By default the benchmark and all saved
    metrics; pass explicit files to export a subset such as the pilot. Returns
    the number of conversations written."""
    saved = benchmark.CONVERSATIONS, benchmark.MANIFEST
    try:
        if conversations and manifest:
            benchmark.CONVERSATIONS, benchmark.MANIFEST = conversations, manifest
        api.bench.cache_clear()
        if out_dir.exists():
            shutil.rmtree(out_dir)
        _write(out_dir / "policy.json", api.get_policy())
        _write(out_dir / "providers.json", api.providers())
        if metrics:
            rec = json.loads(Path(metrics).read_text(encoding="utf-8"))
            all_metrics = {rec["model"]: rec}
        else:
            all_metrics = api.metrics()
        if note:
            for rec in all_metrics.values():
                rec["note"] = note
        _write(out_dir / "metrics.json", all_metrics)
        rows = api.list_conversations()
        _write(out_dir / "conversations.json", rows)
        for row in rows:
            _write(out_dir / "conversations" / f"{row['id']}.json", api.get_conversation(row["id"]))
        return len(rows)
    finally:
        benchmark.CONVERSATIONS, benchmark.MANIFEST = saved
        api.bench.cache_clear()
