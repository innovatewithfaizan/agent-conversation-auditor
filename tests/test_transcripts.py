"""Every transcript source parses into numbered turns (no downloads needed)."""

import gzip
import json
import zipfile

import pytest

from auditor import transcripts as T

ABCD_RECORD = {
    "convo_id": 3592,
    "scenario": {"flow": "product_defect", "subflow": "return_size", "personal": {"customer_name": "crystal minh"}},
    "original": [
        ["agent", "Hi!"],
        ["customer", "I need to return an item."],
        ["agent", "  may I have your   name please? "],
        ["action", "Account has been pulled up for Crystal Minh."],
        ["customer", ""],
    ],
}


def test_abcd_record_becomes_numbered_turns_with_system_actions():
    conv = T.parse_abcd(ABCD_RECORD)
    assert conv.conv_id == "3592" and conv.source == "abcd"
    assert [(t.idx, t.speaker) for t in conv.turns] == [(0, "agent"), (1, "customer"), (2, "agent"), (3, "system")]
    assert conv.turns[2].text == "may I have your name please?"
    assert conv.meta["subflow"] == "return_size"


def test_load_abcd_reads_gzipped_splits_and_plain_lists(tmp_path):
    split_file = tmp_path / "abcd.json.gz"
    with gzip.open(split_file, "wt", encoding="utf-8") as fh:
        json.dump({"train": [], "dev": [], "test": [ABCD_RECORD]}, fh)
    assert [c.conv_id for c in T.load_abcd(split_file, "test")] == ["3592"]
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps([ABCD_RECORD, {**ABCD_RECORD, "convo_id": 7}]))
    assert len(T.load_abcd(sample)) == 2


def word(text, start, end):
    return {"text": text, "start": start, "end": end, "confidence": 0.9, "speaker": None}


CALL_RECORD = {
    "audio_duration": 75,
    "words": [
        word("Hello,", 1000, 1300), word("this", 1350, 1500), word("is", 1520, 1600), word("support.", 1620, 2000),
        word("Hi.", 3000, 3200),  # 1000 ms pause -> new turn
        word("I", 61000, 61100), word("want", 61150, 61400), word("a", 61420, 61500), word("refund.", 61520, 62000),
    ],
}


def test_call_words_split_into_timed_turns_on_pauses():
    conv = T.parse_callcenter(CALL_RECORD, "call-1", "general_inbound")
    assert [t.text for t in conv.turns] == ["Hello, this is support.", "Hi.", "I want a refund."]
    assert [t.start for t in conv.turns] == ["00:00:01", "00:00:03", "00:01:01"]
    assert {t.speaker for t in conv.turns} == {"unknown"}
    assert conv.meta == {"domain": "general_inbound", "audio_seconds": 75}


def test_load_callcenter_skips_macos_metadata(tmp_path):
    path = tmp_path / "general_inbound.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("general_inbound/call-1.json", json.dumps(CALL_RECORD))
        z.writestr("__MACOSX/general_inbound/._call-1.json", b"\x00\x05\x16\x07binary")
    convs = T.load_callcenter(path)
    assert [(c.conv_id, c.meta["domain"]) for c in convs] == [("call-1", "general_inbound")]


SRT = (
    "﻿1\r\n00:00:01,000 --> 00:00:03,000\r\nAgent: Thanks for calling, how can I help?\r\n\r\n"
    "2\r\n00:01:02,500 --> 00:01:04,000\r\n<i>Caller:</i> I was double\r\ncharged.\r\n\r\n"
    "3\r\n00:01:05,000 --> 00:01:06,000\r\nNote: not a speaker\r\n"
)
VTT = (
    "WEBVTT\n\nNOTE recorded test call\n\n"
    "intro\n00:01.000 --> 00:04.000\n<v Agent>This call may be recorded.\n\n"
    "1:02:03.500 --> 1:02:05.000\n<v Customer Name>Okay.\n"
)


def test_srt_and_vtt_cues_with_speaker_prefixes_and_voice_tags():
    srt = T.parse_cues(SRT)
    assert [(t.speaker, t.text, t.start) for t in srt] == [
        ("agent", "Thanks for calling, how can I help?", "00:00:01"),
        ("customer", "I was double charged.", "00:01:02"),
        ("unknown", "Note: not a speaker", "00:01:05"),
    ]
    vtt = T.parse_cues(VTT)
    assert [(t.speaker, t.text, t.start) for t in vtt] == [
        ("agent", "This call may be recorded.", "00:00:01"),
        ("unknown", "Okay.", "01:02:03"),
    ]


def test_parse_upload_dispatches_on_format():
    generic = json.dumps([{"speaker": "Rep", "text": "Hello"}, {"speaker": "user", "text": "Hi", "start": "00:00:02"}])
    conv = T.parse_upload("call.json", generic.encode())
    assert [(t.speaker, t.start) for t in conv.turns] == [("agent", ""), ("customer", "00:00:02")]
    assert T.parse_upload("chat.json", json.dumps(ABCD_RECORD).encode()).turns[3].speaker == "system"
    assert len(T.parse_upload("call.json", json.dumps(CALL_RECORD).encode()).turns) == 3
    assert len(T.parse_upload("call.SRT", SRT.encode()).turns) == 3
    with pytest.raises(ValueError):
        T.parse_upload("notes.txt", b"hello")
    with pytest.raises(ValueError):
        T.parse_upload("x.json", b'{"something": "else"}')
    with pytest.raises(ValueError):
        T.parse_upload("empty.srt", b"no cues here")


def test_rendering_and_chunks_keep_turn_numbers():
    turns = T.parse_callcenter(CALL_RECORD, "c").turns + [T.Turn(3, "agent", "Sure.")]
    assert T.turn_line(turns[2]) == "[2 00:01:01] unknown: I want a refund."
    assert T.turn_line(turns[3]) == "[3] agent: Sure."
    chunks = T.chunk_turns(turns, size=3)
    assert [(c.chunk_id, c.first, c.last, c.start) for c in chunks] == [("c0000", 0, 2, "00:00:01"), ("c0001", 3, 3, "")]
    assert chunks[0].text.splitlines()[1].startswith("[1 00:00:03]")
