"""Runner resilience: a provider connection failure must degrade gracefully.

Regression test for the WinError-10054 case seen in the wild — DeepSeek dropped a
socket mid-turn and the raw APIConnectionError propagated to a 500, surfacing as
"Failed to fetch" in the browser. Now ANY provider failure yields a safe canned turn
(never a 500), and the deterministic backstop still enforces the reserved-advice
boundary even when the model call failed entirely.
"""

from __future__ import annotations

import pytest

import app.conversation.runner as runner
from app.session_engine import run_engine
from app.store.memory_store import store


@pytest.fixture()
def failing_provider(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated connection reset (WinError 10054)")

    monkeypatch.setattr(runner, "complete_turn", boom)


def test_benign_turn_degrades_gracefully(failing_provider):
    state = store.create("steuerkanzlei_mueller")
    run_engine(state)
    r = runner.run_turn(state, "Ich war das ganze Jahr angestellt.")
    assert r["reply_text"]          # a safe reply, not an exception
    assert r["escalated"] is False


def test_reserved_advice_still_caught_when_llm_fails(failing_provider):
    """The boundary must not depend on the model being reachable."""
    state = store.create("steuerkanzlei_mueller")
    run_engine(state)
    r = runner.run_turn(state, "Kann ich mein Arbeitszimmer absetzen?")
    assert r["escalated"] is True
    assert state.escalation_log[-1].category == "tax_advice"
