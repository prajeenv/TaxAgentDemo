"""Deterministic-backstop + containment tests (no LLM required).

These exercise the parts of the reserved-advice guardrail that do NOT depend on the
model: the regex backstop (Layer 3's independent check) and the runner's containment
behavior when an escalation is present. The LLM self-classification battery
(test_guardrail_llm.py) runs separately and only when a provider key is configured.
"""

from __future__ import annotations

import pytest

from app.conversation.runner import (
    RESERVED_CATEGORIES,
    backstop_category,
    render_handoff,
)

# --- Backstop pattern coverage ---------------------------------------------

# (utterance, expected category or None)
BACKSTOP_CASES = [
    # outcome_speculation
    ("Bekomme ich eine Steuererstattung?", "outcome_speculation"),
    ("Wie viel bekomme ich ungefähr zurück?", "outcome_speculation"),
    ("Will I get a refund this year?", "outcome_speculation"),
    ("Muss ich am Ende nachzahlen?", "outcome_speculation"),
    ("Wie hoch ist mein Steuersatz?", "outcome_speculation"),
    ("How much will I owe?", "outcome_speculation"),
    # tax_advice
    ("Kann ich mein Arbeitszimmer absetzen?", "tax_advice"),
    ("Is my commute deductible?", "tax_advice"),
    ("Lohnt sich die Steuerklasse III?", "tax_advice"),
    ("Should I deduct my travel costs?", "tax_advice"),
    ("Kann ich die Fahrtkosten geltend machen?", "tax_advice"),
    # sufficiency / obligation judgments (added after a live-battery miss)
    ("Reicht es, wenn ich nur die Lohnsteuerbescheinigung schicke?", "tax_advice"),
    ("Muss ich meine Mieteinnahmen angeben?", "tax_advice"),
    ("Do I have to declare the money my aunt gave me?", "tax_advice"),
    ("Is it enough if I just send my payslips?", "tax_advice"),
    # must NOT fire (ordinary intake answers / benign)
    ("Ich war das ganze Jahr angestellt.", None),
    ("Guten Morgen, wie geht es Ihnen?", None),
    ("Ich habe eine Wohnung vermietet.", None),
    ("Danke, das ist super!", None),
    ("Ja, ich habe zwei Kinder in der Kita.", None),
    # near-boundary negatives for the new sufficiency patterns
    ("Reicht die Zeit noch bis zur Abgabefrist?", None),  # "reicht die Zeit" != submission sufficiency...
    ("Ich muss noch die Belege suchen.", None),           # "muss" but not a declaration judgment
]


@pytest.mark.parametrize("utterance,expected", BACKSTOP_CASES)
def test_backstop_category(utterance, expected):
    assert backstop_category(utterance) == expected


def test_backstop_categories_are_reserved():
    """Every category the backstop can emit is a reserved (suppress-prose) category."""
    for utterance, expected in BACKSTOP_CASES:
        if expected is not None:
            assert expected in RESERVED_CATEGORIES


# --- Handoff copy -----------------------------------------------------------


def test_handoff_never_uses_cold_language():
    """Warm-but-bounded: the handoff must not read as a refusal."""
    forbidden = ["kann ich nicht", "darf ich nicht", "nicht erlaubt", "unable", "not allowed"]
    for cat in ("tax_advice", "outcome_speculation", "out_of_scope"):
        copy = render_handoff(cat, "Waren Sie ganzjährig angestellt?").lower()
        for f in forbidden:
            assert f not in copy, f"handoff for {cat} used cold phrase '{f}'"


def test_handoff_carries_next_question_when_present():
    copy = render_handoff("tax_advice", "Haben Sie Kinder?")
    assert "Haben Sie Kinder?" in copy


def test_handoff_ok_without_next_question():
    copy = render_handoff("outcome_speculation", None)
    assert copy  # non-empty, no trailing dangling
    assert "None" not in copy
