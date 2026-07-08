"""Deterministic yes/no recovery test (LLM-free).

The model intermittently returns EMPTY field_updates for a plain yes/no answer (its
internal question-tracking drifts and it drops the extraction), leaving an
asked-and-answered condition stuck as "pending". The runner recovers it: a clear
yes/no answer sets the field the agent's last question was about
(state.pending_question_field).
"""

from __future__ import annotations

import app.conversation.runner as runner
from app.conversation.turn_schema import ProfileUpdate, TurnOutput
from app.session_engine import run_engine
from app.store.memory_store import store


def _empty_turn():
    # Model drops the extraction: no field_updates, no escalation.
    return TurnOutput(reply_text="Danke.", profile_update=ProfileUpdate(field_updates={}))


def test_no_answer_recovered_when_model_drops_it(monkeypatch):
    state = store.create("steuerkanzlei_mueller")
    run_engine(state)
    # Simulate the agent having just asked about pension.
    state.pending_question_field = "receives_pension"

    monkeypatch.setattr(runner, "complete_turn", lambda *a, **k: _empty_turn())
    runner.run_turn(state, "no")

    assert state.profile.receives_pension is False, "yes/no answer should be recovered"


def test_yes_answer_recovered(monkeypatch):
    state = store.create("steuerkanzlei_mueller")
    run_engine(state)
    state.pending_question_field = "made_donations"
    monkeypatch.setattr(runner, "complete_turn", lambda *a, **k: _empty_turn())
    runner.run_turn(state, "yes I do")
    assert state.profile.made_donations is True


def test_ambiguous_answer_not_recovered(monkeypatch):
    """A non-yes/no reply must NOT be force-set (avoid inventing a fact)."""
    state = store.create("steuerkanzlei_mueller")
    run_engine(state)
    state.pending_question_field = "receives_pension"
    monkeypatch.setattr(runner, "complete_turn", lambda *a, **k: _empty_turn())
    runner.run_turn(state, "well, it's complicated")
    assert state.profile.receives_pension is None  # left unset


def test_model_extraction_takes_precedence(monkeypatch):
    """If the model DID extract the field, recovery must not override it."""
    state = store.create("steuerkanzlei_mueller")
    run_engine(state)
    state.pending_question_field = "receives_pension"
    # Model says the client answered "yes" (extracted True) but the raw text is "no".
    turn = TurnOutput(
        reply_text="ok",
        profile_update=ProfileUpdate(field_updates={"receives_pension": True}),
    )
    monkeypatch.setattr(runner, "complete_turn", lambda *a, **k: turn)
    runner.run_turn(state, "no")
    # The model's own extraction wins (recovery only fills gaps).
    assert state.profile.receives_pension is True


def test_pending_question_field_advances(monkeypatch):
    """After a turn, pending_question_field points at the next unanswered condition."""
    state = store.create("steuerkanzlei_mueller")
    run_engine(state)
    monkeypatch.setattr(runner, "complete_turn", lambda *a, **k: _empty_turn())
    runner.run_turn(state, "hi")
    # something conditional should be queued up as the next target
    assert state.pending_question_field is not None
