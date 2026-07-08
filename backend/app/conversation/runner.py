"""The conversation runner — one turn of the intake, with the guardrail's Layer 3.

Per client message:
  1. Build the system prompt (profile + engine status injected).
  2. Call the LLM provider (schema-validated); on failure use a safe canned turn.
  3. LAYER 3 CONTAINMENT + deterministic backstop:
     - A small inspectable regex backstop independently checks for reserved-advice
       patterns. If it fires but the model didn't self-report, we OVERRIDE: force
       an escalation and the canned handoff. We don't trust the model to answer
       correctly — only to raise its hand — and we backstop the times it doesn't.
     - For the three RESERVED categories (tax_advice / outcome_speculation /
       out_of_scope), we NEVER emit model-authored reply prose. We substitute a
       canned warm handoff. unmapped_answer keeps the model's gentle re-ask.
  4. Merge extracted facts (fill-only; overwrite only on a checkpoint correction;
     drop+log unknown fields).
  5. Re-run the determination engine on the merged profile (the seam).
  6. Append any escalation to the log; persist; return the turn result.

The engine is a pure function of the Profile, so re-running it after any turn is
always safe. An escalation never corrupts the tracker: a pure-escalation turn
carries no facts, so the engine result is unchanged.
"""

from __future__ import annotations

import re
from typing import Optional

from app.config import get_ruleset
from app.session_engine import run_engine, tracker_from_result
from app.conversation.escalation import EscalationRecord
from app.conversation.llm_client import LLMError, complete_turn
from app.conversation.prompts import (
    CONSULTANT_NAME,
    build_system_prompt,
    render_doc_status,
)
from app.conversation.turn_schema import TurnOutput
from app.determination.models import Profile
from app.store.memory_store import ChatMessage, SessionState

RESERVED_CATEGORIES = {"tax_advice", "outcome_speculation", "out_of_scope"}
_VALID_PROFILE_FIELDS = set(Profile.model_fields.keys())


# --- Deterministic backstop (Layer 3, independent of the model) -------------
# A SMALL, inspectable pattern list — not a second LLM. If any fires and the model
# returned escalation.triggered=false with a substantive answer, we override. Tuned
# for the highest-signal reserved phrases (refund/owe/deductible/how-much/tax-class).
# Kept deliberately conservative to avoid over-escalation on ordinary answers.

# NOTE: German stems appear inside compounds and inflections ("Steuererstattung",
# "nachzahlen"), so these stems intentionally omit word boundaries — substring match
# is what we want. English stems keep boundaries to avoid false hits.
_BACKSTOP_PATTERNS: list[tuple[str, str]] = [
    # outcome_speculation
    (r"(erstattung|nachzahl|zurück\s*bekomm|zurückbekomm|steuersatz)", "outcome_speculation"),
    (r"\b(refund|owe|tax\s+rate)\b", "outcome_speculation"),
    (r"wie\s*viel\s*(bekomme|kriege|zurück)", "outcome_speculation"),
    (r"how\s*much\s*(will|do)\s*i\s*(get|owe)", "outcome_speculation"),
    # tax_advice
    (r"(absetzen|abzugsf\w+|absetzbar|abziehen|geltend\s*machen|steuerklasse)", "tax_advice"),
    (r"\b(deduct|deductible|tax\s+class)\b", "tax_advice"),
    (r"should\s*i\s*(file|claim|deduct)", "tax_advice"),
]

_COMPILED_BACKSTOP = [(re.compile(p, re.IGNORECASE), cat) for p, cat in _BACKSTOP_PATTERNS]


def backstop_category(text: str) -> Optional[str]:
    """Return the reserved category if a backstop pattern fires, else None."""
    for rx, cat in _COMPILED_BACKSTOP:
        if rx.search(text):
            return cat
    return None


# --- Canned handoff copy (used whenever we suppress model prose) -------------


def render_handoff(category: str, next_question: Optional[str]) -> str:
    tail = f" {next_question}" if next_question else ""
    if category == "out_of_scope":
        return (
            f"Das ist etwas außerhalb dessen, was ich hier für Sie sammle — aber eine "
            f"gute Frage für {CONSULTANT_NAME}. Ich gebe sie weiter. Zurück zu Ihrer "
            f"Steuererklärung:{tail}"
        )
    # tax_advice / outcome_speculation
    return (
        f"Das ist eine wirklich gute Frage für {CONSULTANT_NAME} — ich merke sie vor, "
        f"damit sie das direkt mit Ihnen bespricht. Für den Moment machen wir weiter:{tail}"
    )


SAFE_FALLBACK_REPLY = (
    f"Entschuldigung, da bin ich kurz durcheinandergekommen. Können wir dort "
    f"weitermachen, wo wir waren? Erzählen Sie mir gern weiter von Ihrer Situation."
)


# --- The turn ---------------------------------------------------------------


def run_turn(state: SessionState, user_message: str) -> dict:
    """Process one client message end to end and return the turn result."""
    ruleset = get_ruleset(state.firm)

    # Record the client message.
    state.messages.append(ChatMessage(role="user", text=user_message))
    turn_index = len(state.messages) - 1

    # Build the doc-status snapshot for the prompt from the latest engine result.
    latest = state.latest_determination
    doc_status = (
        render_doc_status(latest.required_documents, latest.excluded, latest.pending)
        if latest
        else "Noch nichts gesammelt."
    )
    system = build_system_prompt(state.profile, ruleset, doc_status)

    # History as provider messages (exclude the just-appended user turn; the client
    # passes it separately).
    history = [
        {"role": m.role, "content": m.text} for m in state.messages[:-1]
    ]

    # 1-2. Call the model; on ANY failure, a safe canned turn (never a 500 to the
    #      client). LLMError is the expected path; the bare except is belt-and-
    #      suspenders so an unforeseen error still degrades gracefully. The backstop
    #      below still runs on the fallback turn, so a reserved-advice question is
    #      caught even when the model call failed entirely.
    try:
        turn = complete_turn(system, history, user_message)
    except LLMError:
        turn = TurnOutput(reply_text=SAFE_FALLBACK_REPLY)
    except Exception:
        turn = TurnOutput(reply_text=SAFE_FALLBACK_REPLY)

    # 3. Deterministic backstop: if a reserved pattern fires but the model didn't
    #    self-report, override with an escalation (never let advice leak).
    if not turn.escalation.triggered:
        cat = backstop_category(user_message)
        if cat is not None:
            turn.escalation.triggered = True
            turn.escalation.category = cat  # type: ignore[assignment]
            turn.escalation.client_utterance = user_message
            turn.escalation.reason = (
                "Deterministic backstop matched a reserved-advice pattern the model "
                "did not self-report."
            )

    # 3b. Layer-3 containment: suppress model prose for reserved categories.
    reply = turn.reply_text
    escalated = turn.escalation.triggered
    if escalated and turn.escalation.category in RESERVED_CATEGORIES:
        # Try to preserve a fact-question the model may have appended, else no tail.
        reply = render_handoff(turn.escalation.category or "", _next_question(turn))
    # unmapped_answer keeps the model's gentle re-ask (turn.reply_text).

    # 4. Merge extracted facts (fill-only; overwrite only on a checkpoint correction).
    _merge_profile(state, turn)

    # 5. Re-run the engine on the merged profile (the seam).
    result = run_engine(state)

    # 6. Log escalation.
    if escalated:
        state.escalation_log.append(
            EscalationRecord(
                turn_index=turn_index,
                category=turn.escalation.category or "out_of_scope",  # type: ignore[arg-type]
                client_utterance=turn.escalation.client_utterance or user_message,
                reason=turn.escalation.reason or "",
            )
        )

    if turn.conversation_complete:
        state.complete = True

    state.messages.append(
        ChatMessage(
            role="assistant",
            text=reply,
            checkpoint=turn.checkpoint,
            escalated=escalated,
        )
    )

    return {
        "reply_text": reply,
        "tracker_state": tracker_from_result(result).model_dump(),
        "escalated": escalated,
        "complete": state.complete,
        "checkpoint": turn.checkpoint,
    }


# --- Helpers ----------------------------------------------------------------


def _merge_profile(state: SessionState, turn: TurnOutput) -> None:
    """Merge extracted facts. Fill-only unless this is a checkpoint correction turn.

    Unknown field names are dropped (logged via a no-op here; the runner is the
    place a real logger would hook in). Invalid values that fail Profile validation
    are dropped by re-validating the whole profile and reverting on error.
    """
    updates = turn.profile_update.field_updates
    if not updates:
        return

    current = state.profile.model_dump()
    for field, value in updates.items():
        if field not in _VALID_PROFILE_FIELDS:
            continue  # drop unknown field (would-be log point)
        already_set = current.get(field) is not None
        if already_set and not turn.checkpoint:
            continue  # fill-only: don't overwrite a set field outside a checkpoint
        current[field] = value

    try:
        state.profile = Profile(**current)
    except Exception:
        # A bad value slipped through; keep the prior profile rather than crash.
        pass


def _next_question(turn: TurnOutput) -> Optional[str]:
    """Best-effort extraction of a trailing question from the model's reply, so a
    forced handoff can still carry the conversation forward. Conservative: only use
    the model's reply tail if it ends in a question."""
    text = (turn.reply_text or "").strip()
    if text.endswith("?"):
        # take the last sentence-ish fragment ending in '?'
        parts = re.split(r"(?<=[.!?])\s+", text)
        for frag in reversed(parts):
            if frag.strip().endswith("?"):
                return frag.strip()
    return None
