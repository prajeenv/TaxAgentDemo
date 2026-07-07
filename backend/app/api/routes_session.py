"""Session + review endpoints.

Phase 1 wires everything that does NOT need the LLM: creating a session, reading
its snapshot, the consultant editing a profile field (which re-runs the engine),
and approval. The chat endpoint (POST /session/{id}/message) is added in Phase 3
with the conversation runner.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import FIRM, get_ruleset
from app.determination.engine import determine
from app.determination.models import DeterminationResult, Profile
from app.store.memory_store import ChatMessage, SessionState, store

router = APIRouter()

# The fixed, warm opening turn. The first turn is not LLM-generated — it's a
# constant open question; extraction begins on the client's reply (Phase 3).
OPENING_QUESTION = (
    "Hi! I'm here to help you get ready for your income-tax return. "
    "To start, tell me a bit about your situation — your work, your family, "
    "anything you think might be relevant. No need to be exhaustive; we'll walk "
    "through the details together."
)


class TrackerState(BaseModel):
    """The engine result, shaped for the frontend tracker + review surface."""

    required: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    pending: list[dict[str, Any]]
    refine_flags: list[dict[str, Any]]


def tracker_from_result(result: Optional[DeterminationResult]) -> TrackerState:
    if result is None:
        return TrackerState(required=[], excluded=[], pending=[], refine_flags=[])
    return TrackerState(
        required=[d.model_dump() for d in result.required_documents],
        excluded=[t.model_dump() for t in result.excluded],
        pending=[t.model_dump() for t in result.pending],
        refine_flags=[f.model_dump() for f in result.refine_flags],
    )


def run_engine(state: SessionState) -> DeterminationResult:
    """Run the determination engine on a session's current profile and store it."""
    ruleset = get_ruleset(state.firm)
    result = determine(state.profile, ruleset)
    state.latest_determination = result
    return result


# --- Responses --------------------------------------------------------------


class CreateSessionResponse(BaseModel):
    session_id: str
    opening_turn: str
    tracker_state: TrackerState


class SessionSnapshot(BaseModel):
    session_id: str
    firm: str
    profile: dict[str, Any]
    messages: list[dict[str, Any]]
    tracker_state: TrackerState
    escalation_log: list[dict[str, Any]]
    approved: bool
    complete: bool


def snapshot(state: SessionState) -> SessionSnapshot:
    return SessionSnapshot(
        session_id=state.session_id,
        firm=state.firm,
        profile=state.profile.model_dump(),
        messages=[m.model_dump() for m in state.messages],
        tracker_state=tracker_from_result(state.latest_determination),
        escalation_log=[e.model_dump() for e in state.escalation_log],
        approved=state.approved,
        complete=state.complete,
    )


# --- Endpoints --------------------------------------------------------------


@router.post("/session", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    state = store.create(FIRM)
    state.messages.append(ChatMessage(role="assistant", text=OPENING_QUESTION))
    result = run_engine(state)  # all-pending at the start; drives the initial tracker
    return CreateSessionResponse(
        session_id=state.session_id,
        opening_turn=OPENING_QUESTION,
        tracker_state=tracker_from_result(result),
    )


@router.get("/session/{session_id}", response_model=SessionSnapshot)
def get_session(session_id: str) -> SessionSnapshot:
    state = store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return snapshot(state)


class ProfilePatch(BaseModel):
    """A consultant edit: a sparse set of profile field updates."""

    field_updates: dict[str, Any]


@router.patch("/session/{session_id}/profile", response_model=SessionSnapshot)
def patch_profile(session_id: str, patch: ProfilePatch) -> SessionSnapshot:
    """Consultant edits profile fields on the review surface; the engine re-runs.

    This is what proves the ruleset is live and editable: change a fact, watch the
    document list recompute. Validates the merged profile against the Profile schema.
    """
    state = store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")

    merged = state.profile.model_dump()
    merged.update(patch.field_updates)
    try:
        state.profile = Profile(**merged)
    except Exception as exc:  # pydantic ValidationError -> 422 with the detail
        raise HTTPException(status_code=422, detail=f"invalid profile update: {exc}")

    run_engine(state)
    return snapshot(state)


@router.post("/session/{session_id}/approve", response_model=SessionSnapshot)
def approve_session(session_id: str) -> SessionSnapshot:
    """Draft-and-approve: the consultant marks the draft final."""
    state = store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    state.approved = True
    return snapshot(state)
