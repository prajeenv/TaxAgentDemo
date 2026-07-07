"""In-memory session store.

A prototype-grade store: a plain dict keyed by session id. Sessions are ephemeral;
a server restart clears them (fine — no real data). Each SessionState holds the
collected profile, the message history, the latest engine result, the escalation
log, and the draft-and-approve state.

Concurrency note: FastAPI runs the app in a single process; a dict is adequate for
a demo. If this ever needs multi-worker deployment it becomes a real store, but
that is explicitly product-stage.
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field

from app.conversation.escalation import EscalationRecord
from app.determination.models import DeterminationResult, Profile


class ChatMessage(BaseModel):
    role: str          # "assistant" | "user"
    text: str
    checkpoint: bool = False   # assistant turns that were confirmation checkpoints
    escalated: bool = False    # assistant turns that escalated


class SessionState(BaseModel):
    session_id: str
    firm: str
    profile: Profile = Field(default_factory=Profile)
    messages: list[ChatMessage] = Field(default_factory=list)
    latest_determination: Optional[DeterminationResult] = None
    escalation_log: list[EscalationRecord] = Field(default_factory=list)
    approved: bool = False
    complete: bool = False


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(self, firm: str) -> SessionState:
        session_id = uuid.uuid4().hex
        state = SessionState(session_id=session_id, firm=firm)
        self._sessions[session_id] = state
        return state

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> SessionState:
        state = self._sessions.get(session_id)
        if state is None:
            raise KeyError(session_id)
        return state


# Single process-wide store instance for the app.
store = SessionStore()
