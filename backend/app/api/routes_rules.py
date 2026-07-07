"""Read-only ruleset introspection — lets the review UI show provenance.

Returns the loaded rules + document catalog so the frontend can render "this
document was required because rule X applied," and show the interview script.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.config import FIRM, get_ruleset

router = APIRouter()


@router.get("/rules")
def get_rules(firm: str = FIRM) -> dict[str, Any]:
    ruleset = get_ruleset(firm)
    return {
        "firm": ruleset.firm,
        "rules": [r.model_dump() for r in ruleset.rules],
        "documents": {doc_id: doc.model_dump() for doc_id, doc in ruleset.documents.items()},
    }
