"""The policy the auditor checks against: categories, severity scale and the
written policy text (policy/support_policy.md, the single source of truth)."""

from functools import lru_cache

from . import config

SEVERITIES = ["none", "minor", "major", "critical"]
LEVEL = {s: i for i, s in enumerate(SEVERITIES)}

CATEGORIES = {
    "personal_data": "Personal and payment data",
    "verification": "Identity verification",
    "promises": "Commitments and claims",
    "escalation": "Complaints and escalation",
    "conduct": "Honesty and conduct",
}

# Fixed retrieval queries for the RAG baseline (and the agent's starting
# excerpts). Written like dialogue, because the index holds dialogue.
CATEGORY_QUERIES = {
    "personal_data": "what is your card number, security code, password, PIN, one-time code, date of birth, home address",
    "verification": "can I get your full name, account ID, order ID, username, email to verify your identity; "
                    "refund, return, change address, cancel order, update payment method",
    "promises": "I guarantee, I promise, definitely, for sure, full refund, free, compensation, discount, it will arrive by",
    "escalation": "I want to speak to a manager, supervisor, complaint, this is unacceptable, cancel, lawyer, frustrated",
    "conduct": "are you a bot, are you a real person, that's your problem, calm down, not my fault, stupid",
}


@lru_cache(maxsize=1)
def policy_text() -> str:
    return (config.ROOT / "policy" / "support_policy.md").read_text(encoding="utf-8")


def worst(severities: list[str]) -> str:
    return max(severities, key=LEVEL.__getitem__, default="none")
