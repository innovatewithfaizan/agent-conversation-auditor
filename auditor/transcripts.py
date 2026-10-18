"""Load conversations from every supported source into one shape.

A Conversation is a list of Turns. Each turn has its position (idx), a
speaker (agent, customer, system or unknown), its text and, when the source
has timing, a start time. Findings cite turns by idx, so every parser must
number turns 0, 1, 2... in conversation order.

Sources:
* ABCD (ASAPP): customer-service chats, JSON. "action" turns log what the
  agent did in its tools and become speaker "system".
* CallCenterEN (AIxBlock): real call transcripts as timed words with no
  speaker labels, zipped per domain. Turns are split on pauses.
* SRT and WebVTT subtitle-style transcripts, optionally with "Agent:" style
  prefixes or WebVTT <v Name> voice tags.
* A generic JSON list of {"speaker", "text", "start"?} objects (what the API
  and app accept).
"""

import gzip
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import config

SPEAKERS = ("agent", "customer", "system", "unknown")
_SPEAKER_ALIASES = {
    "agent": "agent", "rep": "agent", "representative": "agent", "assistant": "agent", "bot": "agent",
    "customer": "customer", "caller": "customer", "client": "customer", "user": "customer",
    "action": "system", "system": "system",
}


@dataclass
class Turn:
    idx: int
    speaker: str
    text: str
    start: str = ""  # "HH:MM:SS" when the source has timing


@dataclass
class Conversation:
    conv_id: str
    source: str
    turns: list[Turn]
    meta: dict = field(default_factory=dict)


def speaker(name: str | None) -> str:
    return _SPEAKER_ALIASES.get((name or "").strip().lower(), "unknown")


def hms(ms: int) -> str:
    s = int(ms) // 1000
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _numbered(raw: list[tuple[str, str, str]]) -> list[Turn]:
    """(speaker, text, start) tuples -> Turns numbered from 0, empty text dropped."""
    turns = []
    for spk, text, start in raw:
        text = re.sub(r"\s+", " ", text or "").strip()
        if text:
            turns.append(Turn(len(turns), spk, text, start))
    return turns


# ABCD -----------------------------------------------------------------------

def parse_abcd(record: dict) -> Conversation:
    turns = _numbered([(speaker(spk), text, "") for spk, text in record["original"]])
    scenario = record.get("scenario", {})
    meta = {"flow": scenario.get("flow"), "subflow": scenario.get("subflow"), "scenario": scenario}
    return Conversation(str(record["convo_id"]), "abcd", turns, meta)


def load_abcd(path: Path | None = None, split: str = "test") -> list[Conversation]:
    """Read abcd_v1.1.json(.gz): a dict of train/dev/test lists, or a plain list
    (the repo's sample file)."""
    path = path or config.ABCD_DIR / "abcd_v1.1.json.gz"
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    records = data if isinstance(data, list) else data[split]
    return [parse_abcd(r) for r in records]


# CallCenterEN ---------------------------------------------------------------

def parse_callcenter(record: dict, conv_id: str, domain: str = "", gap_ms: int = config.TURN_GAP_MS) -> Conversation:
    """Split timed words into turns at pauses longer than gap_ms. The source has
    no speaker labels, so every turn's speaker is "unknown"."""
    words = [w for w in record.get("words", []) if (w.get("text") or "").strip()]
    groups, current = [], []
    for w in words:
        if current and w["start"] - current[-1]["end"] > gap_ms:
            groups.append(current)
            current = []
        current.append(w)
    if current:
        groups.append(current)
    turns = _numbered([("unknown", " ".join(w["text"] for w in g), hms(g[0]["start"])) for g in groups])
    meta = {"domain": domain, "audio_seconds": record.get("audio_duration")}
    return Conversation(conv_id, "callcenteren", turns, meta)


def load_callcenter(zip_path: Path, limit: int | None = None) -> list[Conversation]:
    """Read one domain zip. Entries are read in memory, never extracted, and
    macOS metadata entries (__MACOSX/) are skipped."""
    domain = Path(zip_path).stem
    out = []
    with zipfile.ZipFile(zip_path) as z:
        names = sorted(n for n in z.namelist() if n.endswith(".json") and "__MACOSX" not in n)
        for name in names[:limit]:
            record = json.loads(z.read(name))
            out.append(parse_callcenter(record, Path(name).stem, domain))
    return out


# SRT / WebVTT / generic JSON ------------------------------------------------

_CUE_TIME = re.compile(r"(?:(\d{1,2}):)?(\d{1,2}):(\d\d)[,.]\d+\s*-->")
_PREFIX = re.compile(r"^([A-Za-z][\w ]{0,20}?)\s*:\s+(.*)$")
_VOICE = re.compile(r"<v(?:\.[^ >]*)?\s+([^>]+)>")
_TAGS = re.compile(r"<[^>]+>|\{\\[^}]*\}")


def _cue_speaker(body: str) -> tuple[str, str]:
    voice = _VOICE.search(body)
    if voice:
        return speaker(voice.group(1)), _TAGS.sub("", body)
    body = _TAGS.sub("", body).strip()
    m = _PREFIX.match(body)
    if m and speaker(m.group(1)) != "unknown":
        return speaker(m.group(1)), m.group(2)
    return "unknown", body


def parse_cues(text: str) -> list[Turn]:
    """SRT or WebVTT text -> one turn per cue."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    raw = []
    for block in re.split(r"\n\s*\n", text):
        rows = [r.strip() for r in block.strip().split("\n")]
        times = [i for i, r in enumerate(rows) if _CUE_TIME.match(r)]
        if not times:
            continue  # WEBVTT header, NOTE or STYLE blocks, stray text
        h, m, s = _CUE_TIME.match(rows[times[0]]).groups()
        spk, body = _cue_speaker(" ".join(rows[times[0] + 1 :]))
        raw.append((spk, body, f"{int(h or 0):02d}:{int(m):02d}:{s}"))
    return _numbered(raw)


def parse_generic(items: list[dict]) -> list[Turn]:
    return _numbered([(speaker(i.get("speaker")), str(i.get("text", "")), str(i.get("start", ""))) for i in items])


def parse_upload(name: str, data: bytes, conv_id: str = "upload") -> Conversation:
    """An uploaded transcript: .srt, .vtt, or .json (generic list, one ABCD
    record or one CallCenterEN record)."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    suffix = Path(name).suffix.lower()
    if suffix in (".srt", ".vtt"):
        turns = parse_cues(text)
    elif suffix == ".json":
        obj = json.loads(text)
        if isinstance(obj, list):
            turns = parse_generic(obj)
        elif "original" in obj and "convo_id" in obj:
            turns = parse_abcd(obj).turns
        elif "words" in obj:
            turns = parse_callcenter(obj, conv_id).turns
        else:
            raise ValueError("unrecognised JSON transcript")
    else:
        raise ValueError("upload a .srt, .vtt or .json transcript")
    if not turns:
        raise ValueError("no turns found in that file")
    return Conversation(conv_id, "upload", turns, {"filename": name})


# JSONL (our own format, used for the benchmark) -----------------------------

def to_dict(conv: Conversation) -> dict:
    return {"conv_id": conv.conv_id, "source": conv.source, "meta": conv.meta,
            "turns": [{"idx": t.idx, "speaker": t.speaker, "text": t.text, "start": t.start} for t in conv.turns]}


def from_dict(d: dict) -> Conversation:
    turns = [Turn(t["idx"], t["speaker"], t["text"], t.get("start", "")) for t in d["turns"]]
    if [t.idx for t in turns] != list(range(len(turns))):
        raise ValueError(f"{d['conv_id']}: turns must be numbered 0..n-1")
    return Conversation(str(d["conv_id"]), d["source"], turns, d.get("meta", {}))


def save_jsonl(convs: list[Conversation], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for c in convs:
            fh.write(json.dumps(to_dict(c), ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[Conversation]:
    with open(path, encoding="utf-8") as fh:
        return [from_dict(json.loads(line)) for line in fh if line.strip()]


# Rendering and chunking -----------------------------------------------------

def turn_line(t: Turn) -> str:
    """How a turn appears to the model and in evidence: "[12 00:01:02] agent: text"."""
    where = f"{t.idx} {t.start}" if t.start else str(t.idx)
    return f"[{where}] {t.speaker}: {t.text}"


def render(turns: list[Turn]) -> str:
    return "\n".join(turn_line(t) for t in turns)


@dataclass
class Chunk:
    chunk_id: str
    first: int  # idx of the first and last turn in the chunk
    last: int
    start: str
    text: str


def chunk_turns(turns: list[Turn], size: int = config.CHUNK_TURNS) -> list[Chunk]:
    chunks = []
    for i in range(0, len(turns), size):
        group = turns[i : i + size]
        chunks.append(Chunk(f"c{i // size:04d}", group[0].idx, group[-1].idx, group[0].start, render(group)))
    return chunks
