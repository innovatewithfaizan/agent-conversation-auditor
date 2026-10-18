"""Regex detectors for sensitive data in turns, used by the find_patterns tool.

Matches are masked in the output (only the last digits are shown), so the
tool never echoes a full card number or ID back into the conversation."""

import re

from .transcripts import Turn

_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_CVV = re.compile(r"\b(?:cvv|cvc|cvv2|security code|card code)\b\D{0,25}?\b\d{3,4}\b", re.I)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
# Separators are required, so 10-digit order IDs are not mistaken for phones.
_PHONE = re.compile(r"(?<!\d)(?:\+?1[ .-])?(?:\(\d{3}\) ?|\d{3}[.-])\d{3}[ .-]\d{4}(?!\d)")
_NATIONAL_ID = re.compile(r"(?<!\d)(?:\d{3}-\d{2}-\d{4}|\d{3}[ -]\d{3}[ -]\d{3})(?!\d)")
_SECRET = re.compile(r"\b(?:password|passcode|pin|one[- ]time (?:code|password)|verification code|security answer)\b", re.I)

KINDS = ["card_number", "card_security_code", "email", "phone", "national_id", "secret_mention"]


def luhn_ok(digits: str) -> bool:
    total, double = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if double:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        double = not double
    return total % 10 == 0


def mask(value: str, keep: int = 4) -> str:
    digits = re.sub(r"\D", "", value)
    if not digits:
        return value[:2] + "***"
    shown = digits[-keep:] if keep else ""
    return "*" * (len(digits) - len(shown)) + shown


def _mask_email(value: str) -> str:
    user, _, domain = value.partition("@")
    return f"{user[:1]}***@{domain}"


def scan(text: str) -> dict[str, list[str]]:
    """Masked matches of every kind in one text."""
    found = {k: [] for k in KINDS}
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            found["card_number"].append(mask(digits))
    found["card_security_code"] = ["security code ***" for _ in _CVV.finditer(text)]
    found["email"] = [_mask_email(m.group()) for m in _EMAIL.finditer(text)]
    cards = {re.sub(r"\D", "", m.group()) for m in _CARD.finditer(text)}
    found["phone"] = [mask(m.group()) for m in _PHONE.finditer(text)
                      if not any(re.sub(r"\D", "", m.group()) in c for c in cards)]
    found["national_id"] = [mask(m.group(), 3) for m in _NATIONAL_ID.finditer(text)]
    found["secret_mention"] = [m.group().lower() for m in _SECRET.finditer(text)]
    return found


def find_patterns(turns: list[Turn], kinds: list[str] | None = None, max_examples: int = 8) -> dict:
    """Per kind: how many turns contain it, and up to max_examples turns with
    the speaker and masked matches."""
    kinds = [k for k in (kinds or KINDS) if k in KINDS]
    out = {k: {"turns_with_match": 0, "examples": []} for k in kinds}
    for turn in turns:
        found = scan(turn.text)
        for k in kinds:
            if found[k]:
                out[k]["turns_with_match"] += 1
                if len(out[k]["examples"]) < max_examples:
                    out[k]["examples"].append({"turn": turn.idx, "speaker": turn.speaker, "matches": found[k]})
    return out
