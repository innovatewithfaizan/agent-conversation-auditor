"""Vector store over conversation chunks (ChromaDB + all-MiniLM-L6-v2) and the
exact word search the auditor uses next to semantic search."""

import re
import threading
from dataclasses import dataclass, field

import chromadb
from chromadb.utils import embedding_functions

from . import config
from .transcripts import Conversation, Turn, chunk_turns, turn_line

COLLECTION = "conversation_chunks"


class Store:
    """One Chroma collection holding chunks of many conversations, keyed by
    "<source>:<conv_id>" so ids from different datasets never collide."""

    def __init__(self, client):
        # Chroma's default embedder is the ONNX export of all-MiniLM-L6-v2.
        self.col = client.get_or_create_collection(
            COLLECTION,
            embedding_function=embedding_functions.DefaultEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        self._lock = threading.Lock()

    def ensure(self, key: str, turns: list[Turn]) -> int:
        """Embed a conversation's chunks unless they are already stored. Returns chunks added."""
        with self._lock:
            if self.col.get(where={"conv": key}, limit=1)["ids"]:
                return 0
            chunks = chunk_turns(turns)
            if not chunks:
                return 0
            self.col.add(
                ids=[f"{key}:{c.chunk_id}" for c in chunks],
                documents=[c.text for c in chunks],
                metadatas=[{"conv": key, "first": c.first, "last": c.last, "start": c.start} for c in chunks],
            )
            return len(chunks)

    def search(self, key: str, query: str, k: int, exclude=frozenset()) -> list[dict]:
        """Top-k chunks of one conversation by cosine similarity, skipping ids in
        exclude, returned in conversation order."""
        with self._lock:
            res = self.col.query(query_texts=[query], n_results=k + len(exclude), where={"conv": key})
        hits = []
        for cid, doc, meta in zip(res["ids"][0], res["documents"][0], res["metadatas"][0]):
            if cid in exclude:
                continue
            hits.append({"id": cid, "first": meta["first"], "last": meta["last"], "start": meta["start"], "text": doc})
            if len(hits) == k:
                break
        return sorted(hits, key=lambda h: h["first"])

    def forget(self, key: str) -> None:
        with self._lock:
            self.col.delete(where={"conv": key})


_persistent: Store | None = None
_persistent_lock = threading.Lock()


def persistent_store() -> Store:
    """One shared on-disk store. Chroma's client setup is not thread-safe, so
    parallel workers must not create it at the same time."""
    global _persistent
    with _persistent_lock:
        if _persistent is None:
            _persistent = Store(chromadb.PersistentClient(path=str(config.CHROMA_DIR)))
    return _persistent


def memory_store() -> Store:
    return Store(chromadb.EphemeralClient())


def conv_key(conv: Conversation) -> str:
    return f"{conv.source}:{conv.conv_id}"


@dataclass
class ConversationContext:
    """Everything the auditor needs about one conversation."""

    conv: Conversation
    store: Store
    seen: set = field(default_factory=set)  # chunk ids already shown to the model

    @property
    def key(self) -> str:
        return conv_key(self.conv)

    @classmethod
    def build(cls, conv: Conversation, store: Store | None = None) -> "ConversationContext":
        store = store or persistent_store()
        store.ensure(conv_key(conv), conv.turns)
        return cls(conv, store)


# Common English endings, so "refund" also finds "refunded" and "guarantee"
# finds "guaranteed", without letting "card" match "cardigan".
INFLECTIONS = r"(?:s|es|ed|d|ing|in|er|ers|y|en)?"


def find_words(turns: list[Turn], words: list[str], speaker: str | None = None, max_examples: int = 8) -> dict:
    """Case-insensitive whole-word (or phrase) counts over every turn.

    Each word also matches common endings; a trailing '*' matches any ending.
    speaker limits the search to one speaker's turns, e.g. "agent"."""
    pool = [t for t in turns if speaker is None or t.speaker == speaker]
    counts, examples = {}, []
    for word in words[:12]:
        stem = re.escape(word.strip().rstrip("*"))
        if not stem:
            continue
        tail = r"\w*" if word.strip().endswith("*") else INFLECTIONS
        pattern = re.compile(rf"\b{stem}{tail}\b", re.I)
        n = 0
        for turn in pool:
            hits = len(pattern.findall(turn.text))
            if hits:
                n += hits
                entry = turn_line(turn)
                if len(examples) < max_examples and entry not in examples:
                    examples.append(entry)
        counts[word] = n
    return {"counts": counts, "example_turns": examples}
