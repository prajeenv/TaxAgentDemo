"""Shared session<->engine helpers, used by both the API routes and the runner.

Extracted into a neutral module so routes and the conversation runner can both
import them without a circular dependency. Pure orchestration glue — imports the
determination engine (allowed; the engine never imports back).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from app.config import get_ruleset
from app.determination.engine import determine
from app.determination.models import DeterminationResult
from app.store.memory_store import SessionState


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
