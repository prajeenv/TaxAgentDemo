"""Fact-merge tests — the extraction seam that drives tracker narrowing.

Regression guard for the bug where the model invented field names
(employed_full_year, investment_income_above_allowance, tax_year) and the runner
silently dropped them, so the tracker never narrowed. These tests are LLM-free:
they exercise the merge logic directly with crafted TurnOutputs.
"""

from __future__ import annotations

from app.conversation.runner import _merge_profile
from app.conversation.turn_schema import ProfileUpdate, TurnOutput
from app.store.memory_store import SessionState


def _state():
    return SessionState(session_id="t", firm="steuerkanzlei_mueller")


def _turn(field_updates, checkpoint=False):
    return TurnOutput(
        reply_text="ok",
        profile_update=ProfileUpdate(field_updates=field_updates),
        checkpoint=checkpoint,
    )


def test_correct_field_names_merge():
    s = _state()
    dropped = _merge_profile(s, _turn({"employed_this_year": True, "receives_pension": False}))
    assert dropped == []
    assert s.profile.employed_this_year is True
    assert s.profile.receives_pension is False


def test_aliased_field_names_merge():
    """The invented names we saw in the wild are aliased to the real fields."""
    s = _state()
    dropped = _merge_profile(
        s,
        _turn({
            "employed_full_year": True,               # -> employed_whole_year
            "investment_income_above_allowance": True,  # -> investment_income
            "tax_year": 2024,                          # -> tax_years (scalar -> list)
        }),
    )
    assert dropped == []
    assert s.profile.employed_whole_year is True
    assert s.profile.investment_income is True
    assert s.profile.tax_years == [2024]


def test_truly_unknown_field_is_dropped_and_reported():
    s = _state()
    dropped = _merge_profile(s, _turn({"totally_made_up_field": True, "made_donations": True}))
    assert dropped == ["totally_made_up_field"]
    assert s.profile.made_donations is True  # the valid one still merged


def test_fill_only_does_not_overwrite_outside_checkpoint():
    s = _state()
    _merge_profile(s, _turn({"marital_status": "single"}))
    _merge_profile(s, _turn({"marital_status": "married"}))  # not a checkpoint
    assert s.profile.marital_status == "single"  # unchanged


def test_checkpoint_correction_overwrites():
    s = _state()
    _merge_profile(s, _turn({"marital_status": "single"}))
    _merge_profile(s, _turn({"marital_status": "married"}, checkpoint=True))
    assert s.profile.marital_status == "married"


def test_bad_value_does_not_crash_and_keeps_prior_profile():
    s = _state()
    _merge_profile(s, _turn({"marital_status": "single"}))
    # an invalid enum value should be rejected without crashing
    _merge_profile(s, _turn({"marital_status": "not_a_real_status"}, checkpoint=True))
    assert s.profile.marital_status in ("single", "married", "divorced", "widowed", "separated")
