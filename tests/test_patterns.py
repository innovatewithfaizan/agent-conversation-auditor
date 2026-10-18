"""Sensitive-data detectors: what they catch, what they ignore, and masking."""

from auditor import patterns
from auditor.transcripts import Turn


def kinds(text):
    return {k for k, v in patterns.scan(text).items() if v}


def test_card_numbers_need_a_valid_checksum_and_are_masked():
    assert patterns.scan("card 4111 1111 1111 1111 exp 12/27")["card_number"] == ["************1111"]
    assert patterns.scan("4111-1111-1111-1112")["card_number"] == []  # fails Luhn
    assert kinds("order 3348917502") == set()  # ABCD order ids are not cards or phones


def test_security_codes_are_never_echoed():
    found = patterns.scan("the CVV is 123 and the security code: 4567")
    assert found["card_security_code"] == ["security code ***", "security code ***"]
    assert "123" not in str(found) and "4567" not in str(found)


def test_contact_details_ids_and_secrets():
    assert patterns.scan("call me at (977) 625-2661")["phone"] == ["******2661"]
    assert patterns.scan("email cminh730@email.com")["email"] == ["c***@email.com"]
    assert patterns.scan("SSN 123-45-6789, SIN 046 454 286")["national_id"] == ["******789", "******286"]
    assert patterns.scan("What's your password or the one-time code?")["secret_mention"] == ["password", "one-time code"]


def test_find_patterns_reports_turns_and_speakers():
    turns = [Turn(0, "customer", "My card is 4111 1111 1111 1111"), Turn(1, "agent", "Got it."),
             Turn(2, "agent", "Charging 4111111111111111 now.")]
    out = patterns.find_patterns(turns, ["card_number", "not_a_kind"])
    assert list(out) == ["card_number"]
    assert out["card_number"]["turns_with_match"] == 2
    assert [(e["turn"], e["speaker"]) for e in out["card_number"]["examples"]] == [(0, "customer"), (2, "agent")]
