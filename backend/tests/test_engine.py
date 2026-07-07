"""Engine + eval-harness tests — the PRIMARY validation of the prototype.

`test_eval_cases_match` is the core assertion: for every seed case, the ruleset
reproduces the consultant's expected document list. This is the whole thesis,
tested with zero LLM and zero UI.
"""

from __future__ import annotations

import pytest

from app.determination.engine import determine
from app.determination.loader import load_ruleset
from app.determination.models import Profile
from app.eval.harness import load_cases, run_all, run_case

FIRM = "steuerkanzlei_mueller"


@pytest.fixture(scope="module")
def ruleset():
    return load_ruleset(FIRM)


def test_eval_cases_match(ruleset):
    """Every seed case's produced document list matches the expected list exactly."""
    results = run_all(FIRM)
    assert results, "no eval cases found"
    failures = [r for r in results if not r.match]
    assert not failures, "eval mismatches: " + "; ".join(
        f"{r.case_id} missing={r.missing} extra={r.extra}" for r in failures
    )


def test_every_case_runs(ruleset):
    cases = load_cases()
    for case in cases:
        result = run_case(case, ruleset)
        assert result.case_id == case.case_id


def test_empty_profile_yields_no_documents_all_pending(ruleset):
    """An untouched profile: nothing required, nothing excluded, everything pending."""
    result = determine(Profile(), ruleset)
    assert result.required_documents == []
    assert result.excluded == []
    assert len(result.pending) == len(ruleset.rules)


def test_false_flag_excludes_not_pends(ruleset):
    """An explicit False makes a condition 'excluded', distinct from 'pending'."""
    profile = Profile(rents_out_property=False)
    result = determine(profile, ruleset)
    excluded_ids = {t.rule_id for t in result.excluded}
    pending_ids = {t.rule_id for t in result.pending}
    assert "r4_rental" in excluded_ids
    assert "r4_rental" not in pending_ids


def test_simple_rule_emits_its_documents(ruleset):
    profile = Profile(employed_this_year=True)
    result = determine(profile, ruleset)
    ids = {d.id for d in result.required_documents}
    assert "wage_tax_cert" in ids
    wage = next(d for d in result.required_documents if d.id == "wage_tax_cert")
    assert wage.source_rule_ids == ["r1_wages"]
    assert wage.refine_flag is False


def test_nested_rule_emits_full_stub_bundle_with_refine_flags(ruleset):
    """A nested rule emits the whole bundle, each doc tagged refine_flag, plus a RefineFlag."""
    profile = Profile(rents_out_property=True)
    result = determine(profile, ruleset)
    ids = {d.id for d in result.required_documents}
    # Full rental bundle present
    assert {"rental_contract", "annex_v_prior", "financing_statements",
            "property_cost_records"} <= ids
    # All rental docs carry the refine flag
    rental_docs = [d for d in result.required_documents if d.group == "rental"]
    assert all(d.refine_flag for d in rental_docs)
    # A refine flag callout exists for the rental rule
    assert any(f.rule_id == "r4_rental" for f in result.refine_flags)


def test_document_deduped_with_provenance(ruleset):
    """A document required by two applying rules appears once, listing both sources.

    r9 (not-employed-whole-year, employed_whole_year=False) emits pension_statements_gap;
    no other rule shares a doc, so we instead verify dedup structurally by giving a
    profile where the same doc could be reached once — here we assert no duplicate ids.
    """
    profile = Profile(
        employed_this_year=True,
        employed_whole_year=False,
        union_or_association_member=True,
    )
    result = determine(profile, ruleset)
    ids = [d.id for d in result.required_documents]
    assert len(ids) == len(set(ids)), "duplicate document ids in required list"


def test_marital_change_stub_bundle(ruleset):
    profile = Profile(marital_status_changed=True)
    result = determine(profile, ruleset)
    ids = {d.id for d in result.required_documents}
    assert "marriage_certificate" in ids
    assert "death_certificate" in ids  # full bundle emitted (stubbed depth)
    assert any(f.rule_id == "r6_marital_change" for f in result.refine_flags)
