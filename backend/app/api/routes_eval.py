"""Eval endpoint — run the harness over the seed cases and return per-case diffs.

This is the evidence generator for the primary (validation) job, exposed over HTTP
so an eval view (or CI) can trigger it. No LLM involved.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import FIRM
from app.eval.harness import CaseResult, run_all

router = APIRouter()


class EvalRunRequest(BaseModel):
    firm: Optional[str] = None


class EvalRunResponse(BaseModel):
    firm: str
    total: int
    passed: int
    results: list[CaseResult]


@router.post("/eval/run", response_model=EvalRunResponse)
def run_eval(req: EvalRunRequest) -> EvalRunResponse:
    firm = req.firm or FIRM
    results = run_all(firm)
    passed = sum(1 for r in results if r.match)
    return EvalRunResponse(firm=firm, total=len(results), passed=passed, results=results)
