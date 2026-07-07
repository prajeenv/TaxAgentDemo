"""The determination engine — the heart of the prototype.

    determine(profile, ruleset) -> DeterminationResult

PURE PYTHON. No LLM import anywhere in this package. This function is the single
source of truth for which documents are required and why. The conversation runner
calls it after every turn on the merged profile; the LLM never decides documents.

The algorithm is a flat loop over rules, no per-rule branching in code — all the
branching lives in the rules-as-data. A rule's applicability is a tiny declarative
predicate over one profile field; nested rules emit a stubbed bundle.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    DeterminationResult,
    Predicate,
    Profile,
    RefineFlag,
    ResolvedDocument,
    Rule,
    Ruleset,
    RuleTrace,
)

# Result of evaluating a predicate: True (applies), False (excluded), or None (unknown).
PredResult = Optional[bool]


def _eval_predicate(pred: Predicate, profile: Profile) -> PredResult:
    """Evaluate a predicate against the profile.

    Returns True/False when determinable, or None when the underlying field(s)
    have not been collected yet (tri-state). None propagates so an unasked
    condition is reported as `pending`, not `excluded`.
    """
    if pred.field is not None:
        value = getattr(profile, pred.field)
        if value is None:
            return None
        return value == pred.equals

    if pred.any_of is not None:
        results = [_eval_predicate(sub, profile) for sub in pred.any_of]
        if any(r is True for r in results):
            return True
        if any(r is None for r in results):
            return None
        return False

    if pred.all_of is not None:
        results = [_eval_predicate(sub, profile) for sub in pred.all_of]
        if any(r is False for r in results):
            return False
        if any(r is None for r in results):
            return None
        return True

    # Loader guarantees exactly one branch is set; unreachable in practice.
    return None


def _reason(rule: Rule, result: PredResult) -> str:
    """A short, human-readable explanation of a rule's outcome."""
    if result is None:
        return f"Not yet asked: {rule.triggering_question}"
    if result is True:
        return f"Condition holds: {rule.condition_label}."
    return f"Condition does not apply: {rule.condition_label}."


def determine(profile: Profile, ruleset: Ruleset) -> DeterminationResult:
    """Compute the required-document list from a profile, by explicit rules.

    Every rule contributes exactly one RuleTrace (applies / excluded / pending).
    Applying rules add their documents (simple rules) or their stub bundle
    (nested rules, each doc tagged refine_flag=True). Documents are deduped with
    provenance so a doc required by two rules appears once, listing both.
    """
    # doc_id -> set of rule ids that required it, and whether any source was a stub bundle
    required_sources: dict[str, list[str]] = {}
    refine_docs: set[str] = set()
    excluded: list[RuleTrace] = []
    pending: list[RuleTrace] = []
    refine_flags: list[RefineFlag] = []

    for rule in ruleset.rules:
        assert rule.applies_when is not None  # guaranteed by loader
        result = _eval_predicate(rule.applies_when, profile)

        trace = RuleTrace(
            rule_id=rule.id,
            condition_label=rule.condition_label,
            triggering_question=rule.triggering_question,
            status="pending" if result is None else ("applies" if result else "excluded"),
            reason=_reason(rule, result),
            nested=rule.nested,
        )

        if result is None:
            pending.append(trace)
            continue
        if result is False:
            excluded.append(trace)
            continue

        # result is True -> the rule applies. Collect its documents.
        if rule.nested:
            assert rule.stub_group is not None  # guaranteed by loader
            for doc_id in rule.stub_group.documents:
                required_sources.setdefault(doc_id, []).append(rule.id)
                refine_docs.add(doc_id)
            refine_flags.append(
                RefineFlag(
                    rule_id=rule.id,
                    label=rule.stub_group.label,
                    note=rule.stub_group.note,
                )
            )
        else:
            for doc_id in rule.documents:
                required_sources.setdefault(doc_id, []).append(rule.id)

    # Resolve doc ids -> catalog entities, preserving catalog order for stable output.
    required_documents: list[ResolvedDocument] = []
    for doc_id, doc in ruleset.documents.items():
        if doc_id not in required_sources:
            continue
        required_documents.append(
            ResolvedDocument(
                id=doc.id,
                label=doc.label,
                group=doc.group,
                source_rule_ids=required_sources[doc_id],
                refine_flag=doc_id in refine_docs,
            )
        )

    return DeterminationResult(
        required_documents=required_documents,
        excluded=excluded,
        pending=pending,
        refine_flags=refine_flags,
    )
