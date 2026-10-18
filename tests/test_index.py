"""Semantic search over conversation chunks and exact word counts."""

from concurrent.futures import ThreadPoolExecutor

from auditor import index
from auditor.transcripts import Conversation, Turn

TEXTS = [
    ("agent", "Thanks for contacting us, how can I help?"), ("customer", "Hi, I have a question."),
    ("agent", "Sure, go ahead."), ("customer", "Great."),
    ("customer", "I was charged twice for my order."), ("agent", "I'm sorry, let me check the payment."),
    ("agent", "I can see two charges on your card."), ("customer", "Please refund one."),
    ("customer", "Also, what's the weather like?"), ("agent", "Sunny all week."),
    ("customer", "Nice, thanks."), ("agent", "Have a great day."),
]
CONV = Conversation("42", "abcd", [Turn(i, s, t) for i, (s, t) in enumerate(TEXTS)])


def test_store_chunks_by_turns_and_skips_seen_chunks():
    store = index.memory_store()
    assert store.ensure("abcd:42", CONV.turns) == 3
    assert store.ensure("abcd:42", CONV.turns) == 0  # idempotent
    top = store.search("abcd:42", "double charge on my credit card", k=1)
    assert top[0]["id"] == "abcd:42:c0001" and (top[0]["first"], top[0]["last"]) == (4, 7)
    assert "[4] customer: I was charged twice" in top[0]["text"]
    rest = store.search("abcd:42", "double charge on my credit card", k=2, exclude={"abcd:42:c0001"})
    assert "abcd:42:c0001" not in {h["id"] for h in rest} and len(rest) == 2
    assert [h["first"] for h in rest] == sorted(h["first"] for h in rest)  # conversation order
    store.forget("abcd:42")
    assert not store.col.get(where={"conv": "abcd:42"})["ids"]


def test_context_keys_include_the_source():
    ctx = index.ConversationContext.build(CONV, index.memory_store())
    assert ctx.key == "abcd:42"
    assert ctx.store.search(ctx.key, "refund", k=1)


def test_persistent_store_is_created_once_across_threads(monkeypatch, tmp_path):
    monkeypatch.setattr(index.config, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(index, "_persistent", None)
    with ThreadPoolExecutor(max_workers=8) as pool:
        stores = list(pool.map(lambda _: index.persistent_store(), range(8)))
    assert all(s is stores[0] for s in stores)


def test_find_words_counts_endings_phrases_and_filters_by_speaker():
    turns = [
        Turn(0, "agent", "Your refund is guaranteed, I refunded it already.", "00:00:05"),
        Turn(1, "customer", "A full refund? Thanks. Nice cardigan by the way."),
        Turn(2, "agent", "Yes, a full refund to your card."),
    ]
    found = index.find_words(turns, ["refund", "guarantee", "full refund", "card", "zzz"])
    assert found["counts"] == {"refund": 4, "guarantee": 1, "full refund": 2, "card": 1, "zzz": 0}
    assert found["example_turns"][0] == "[0 00:00:05] agent: Your refund is guaranteed, I refunded it already."
    agent_only = index.find_words(turns, ["refund"], speaker="agent")
    assert agent_only["counts"] == {"refund": 3}
    assert all("customer" not in e for e in agent_only["example_turns"])
    assert index.find_words(turns, ["refund*"])["counts"]["refund*"] == 4
