"""Session + review + chat endpoints.

Everything the frontend talks to: create a session, read its snapshot, the chat
turn (POST /message, via the conversation runner), the consultant editing a profile
field (which re-runs the engine), and approval.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.config import FIRM
from app.determination.models import Profile
from app.session_engine import TrackerState, run_engine, tracker_from_result
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


# TrackerState / tracker_from_result / run_engine live in app.session_engine
# (shared with the conversation runner to avoid a circular import).


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
def create_session(background_tasks: BackgroundTasks) -> CreateSessionResponse:
    state = store.create(FIRM)
    state.messages.append(ChatMessage(role="assistant", text=OPENING_QUESTION))
    result = run_engine(state)  # all-pending at the start; drives the initial tracker
    # Warm the LLM connection while the client reads the opener and types — so the
    # first real turn isn't cold. Runs after the response is sent; never blocks.
    from app.conversation.llm_client import prewarm

    background_tasks.add_task(prewarm)
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


class MessageRequest(BaseModel):
    text: str


class MessageResponse(BaseModel):
    reply_text: str
    tracker_state: TrackerState
    escalated: bool
    complete: bool
    checkpoint: bool


@router.post("/session/{session_id}/message", response_model=MessageResponse)
def post_message(session_id: str, req: MessageRequest) -> MessageResponse:
    """The chat endpoint: run one intake turn through the conversation runner.

    The runner extracts facts, enforces the reserved-advice guardrail, re-runs the
    engine, and returns the turn result. Imported lazily so the LLM/runner deps
    aren't required for the non-chat endpoints.
    """
    state = store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")

    from app.conversation.runner import run_turn

    result = run_turn(state, req.text)
    return MessageResponse(**result)


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
