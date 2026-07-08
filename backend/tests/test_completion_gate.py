"""Completion-gate test (LLM-free): the conversation must not complete while
document conditions are still pending.

Regression guard for the bug where the model declared conversation_complete=true
early, leaving the last one or two conditions stuck in "still to clarify". The
runner now gates completion on the engine's ground truth (no pending conditions),
not the model's claim.
"""

from __future__ import annotations

import app.conversation.runner as runner
from app.conversation.turn_schema import ProfileUpdate, TurnOutput
from app.session_engine import run_engine
from app.store.memory_store import store


def _turn(field_updates=None, complete=False):
    return TurnOutput(
        reply_text="Alles erledigt, vielen Dank!",  # a premature closing-style reply
        profile_update=ProfileUpdate(field_updates=field_updates or {}),
        conversation_complete=complete,
    )


def test_completion_rejected_while_conditions_pending(monkeypatch):
    """Model says complete=true but conditions are unanswered -> NOT complete, and
    the reply is overridden to ask the next pending condition."""
    state = store.create("steuerkanzlei_mueller")
    run_engine(state)  # all 20 conditions pending

    # Model claims completion on turn 1 with nothing answered.
    monkeypatch.setattr(runner, "complete_turn", lambda *a, **k: _turn(complete=True))
    r = runner.run_turn(state, "are we done?")

    assert r["complete"] is False, "must not complete with conditions still pending"
    assert r["reply_text"] != "Alles erledigt, vielen Dank!", (
        "premature closing reply should be overridden with a next question"
    )
    # the reply should carry the next pending condition's question
    assert "?" in r["reply_text"]


def test_completion_accepted_when_no_conditions_pending(monkeypatch):
    """When every condition is answered, the model's completion is honored."""
    state = store.create("steuerkanzlei_mueller")
    # Answer every condition field False (all asked) so nothing is pending.
    from app.determination.models import Profile

    all_false = {
        f: False
        for f in Profile.model_fields
        if f not in ("tax_years", "children", "marital_status")
    }
    all_false["employed_whole_year"] = True  # avoid the r9 branch specifics
    state.profile = Profile(tax_years=[2024], marital_status="single", **all_false)
    run_engine(state)
    assert state.latest_determination.pending == []  # sanity: nothing pending

    monkeypatch.setattr(runner, "complete_turn", lambda *a, **k: _turn(complete=True))
    r = runner.run_turn(state, "that's everything")
    assert r["complete"] is True
