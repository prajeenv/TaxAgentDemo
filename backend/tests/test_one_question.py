"""One-question-per-turn test (LLM battery — needs a key).

Regression guard for the answer-misattribution bug: when the agent bundled two
questions into one turn ("Is it for 2024? And do you receive a pension?"), a single
client answer ("No") attached to the wrong question and silently recorded a wrong
fact. The fix is a firm prompt rule; this test asserts the agent asks at most one
question per turn across a representative conversation.

Skipped without a provider key (same gate as the guardrail battery).
"""

from __future__ import annotations

import pytest

from app.conversation.llm_client import ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, PROVIDER

_HAS_KEY = (PROVIDER == "anthropic" and ANTHROPIC_API_KEY) or (
    PROVIDER != "anthropic" and DEEPSEEK_API_KEY
)

pytestmark = pytest.mark.skipif(not _HAS_KEY, reason="no LLM provider key configured")


def test_at_most_one_question_per_turn():
    from app.session_engine import run_engine
    from app.conversation.runner import run_turn
    from app.store.memory_store import store

    state = store.create("steuerkanzlei_mueller")
    run_engine(state)

    convo = [
        "I work as a product manager, married with a 4 year old child",
        "2025",
        "yes employed",
        "full time all year",
        "no pension",
        "yes capital income above the allowance",
    ]
    offenders = []
    for m in convo:
        r = run_turn(state, m)
        # A rough but effective compound-question detector: more than one '?'.
        if r["reply_text"].count("?") > 1:
            offenders.append((m, r["reply_text"]))

    assert not offenders, "turns with >1 question:\n" + "\n".join(
        f"  after {m!r}: {reply!r}" for m, reply in offenders
    )
