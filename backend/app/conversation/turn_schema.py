"""The structured turn contract returned by the LLM each turn (JSON mode).

One LLM call per turn returns a single validated TurnOutput object carrying BOTH
the client-facing reply AND the extracted facts AND the control/escalation signals.
Atomicity: the reply the client sees and the facts extracted from that same turn
come from one inference, so they can't drift apart.

This module is pure schema (pydantic). The escalation category enum is shared with
app.conversation.escalation.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.conversation.escalation import EscalationCategory


class EscalationSignal(BaseModel):
    """The model's self-classification of a reserved-advice / out-of-scope turn.

    Layer 2 of the three-layer defense: the model must decide, as DATA, whether
    this turn crossed the boundary. We don't trust it to answer correctly — only
    to raise its hand — and the prompt biases it heavily toward raising it.
    """

    triggered: bool = False
    category: Optional[EscalationCategory] = None
    client_utterance: Optional[str] = None
    reason: Optional[str] = None


class ProfileUpdate(BaseModel):
    """Sparse facts extracted this turn — only fields the model actually captured.

    Keys are Profile attribute names; the runner validates + merges (fill-only,
    overwrite only on a checkpoint correction; unknown keys dropped + logged).
    An utterance can carry a fact AND escalate — these are independent channels.
    """

    field_updates: dict[str, Any] = Field(default_factory=dict)


class TurnOutput(BaseModel):
    """The complete structured turn."""

    reply_text: str
    profile_update: ProfileUpdate = Field(default_factory=ProfileUpdate)
    addressing_rule_id: Optional[str] = None   # which condition this turn walks (advisory only)
    checkpoint: bool = False                    # true when this turn is a confirmation checkpoint
    escalation: EscalationSignal = Field(default_factory=EscalationSignal)
    conversation_complete: bool = False


# A worked example embedded in the system prompt so the model has a concrete target
# (JSON mode without an example can emit runaway whitespace). Kept here so prompt
# and schema stay in sync.
TURN_OUTPUT_EXAMPLE = {
    "reply_text": "Danke! Waren Sie das ganze Jahr über angestellt, oder nur einen Teil des Jahres?",
    "profile_update": {"field_updates": {"employed_this_year": True, "marital_status": "married"}},
    "addressing_rule_id": "r1_wages",
    "checkpoint": False,
    "escalation": {"triggered": False, "category": None, "client_utterance": None, "reason": None},
    "conversation_complete": False,
}
