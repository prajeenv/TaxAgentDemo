"""Escalation records — the diagnostic log of the reserved-advice boundary.

When the agent hits something outside its lane (a tax-judgment question, an
out-of-scope ask, an answer that doesn't fit the ruleset) it does NOT improvise:
it hands off and logs what it escalated and why. This module is the record shape
plus a thin append helper. It is pure data — no LLM import — so the store can
depend on it without pulling in the model layer.

The log is diagnostic: it maps where the consultant's real judgment lives.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

EscalationCategory = Literal[
    "tax_advice",            # "can I deduct X?", "should I..."
    "outcome_speculation",   # "will I get a refund?", "will I owe money?"
    "out_of_scope",          # outside the intake's lane entirely
    "unmapped_answer",       # an answer that doesn't fit the ruleset
]


class EscalationRecord(BaseModel):
    turn_index: int              # which conversation turn triggered it
    category: EscalationCategory
    client_utterance: str        # what the client actually said
    reason: str                  # why the agent escalated rather than answered


def append_escalation(
    log: list[EscalationRecord],
    *,
    turn_index: int,
    category: EscalationCategory,
    client_utterance: str,
    reason: str,
) -> EscalationRecord:
    record = EscalationRecord(
        turn_index=turn_index,
        category=category,
        client_utterance=client_utterance,
        reason=reason,
    )
    log.append(record)
    return record
