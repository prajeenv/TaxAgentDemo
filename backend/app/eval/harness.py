"""Eval harness — the evidence generator for the PRIMARY (validation) job.

Replays a past interview (a fixed profile = a client's answers) through the SAME
`determine()` function and diffs its output against the document list the consultant
actually produced. No LLM is involved — this exercises the determination seam we
most need to trust.

A case is data (eval_cases/*.yaml):
    case_id: ...
    description: ...
    profile: { ...profile fields... }
    expected_documents: [ doc_id, ... ]

Later, real redacted transcripts drop in as more case files; nothing else changes.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from app.determination.engine import determine
from app.determination.loader import load_ruleset
from app.determination.models import Profile, Ruleset

_EVAL_CASES_DIR = Path(__file__).resolve().parents[2] / "eval_cases"


class EvalCase(BaseModel):
    case_id: str
    description: str = ""
    firm: str = "steuerkanzlei_mueller"
    profile: dict
    expected_documents: list[str]


class CaseResult(BaseModel):
    case_id: str
    description: str
    match: bool
    missing: list[str]   # expected but not produced
    extra: list[str]     # produced but not expected
    produced: list[str]


def load_cases() -> list[EvalCase]:
    cases: list[EvalCase] = []
    for path in sorted(_EVAL_CASES_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases.append(EvalCase(**raw))
    return cases


def run_case(case: EvalCase, ruleset: Ruleset) -> CaseResult:
    profile = Profile(**case.profile)
    result = determine(profile, ruleset)
    produced = {doc.id for doc in result.required_documents}
    expected = set(case.expected_documents)
    missing = sorted(expected - produced)
    extra = sorted(produced - expected)
    return CaseResult(
        case_id=case.case_id,
        description=case.description,
        match=(not missing and not extra),
        missing=missing,
        extra=extra,
        produced=sorted(produced),
    )


def run_all(firm: str = "steuerkanzlei_mueller") -> list[CaseResult]:
    """Run every eval case for a firm through the engine and return per-case diffs."""
    ruleset = load_ruleset(firm)
    return [run_case(case, ruleset) for case in load_cases() if case.firm == firm]
