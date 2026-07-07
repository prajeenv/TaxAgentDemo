"""Loader / rules-as-data validation tests."""

from __future__ import annotations

import pytest

from app.determination.loader import RulesetValidationError, load_ruleset
from app.determination.models import Profile

FIRM = "steuerkanzlei_mueller"


def test_loads_all_20_rules():
    ruleset = load_ruleset(FIRM)
    assert len(ruleset.rules) == 20
    assert ruleset.firm == FIRM


def test_every_rule_field_maps_to_a_profile_attribute():
    """The one coupling between rules-as-data and the profile: predicate fields exist."""
    ruleset = load_ruleset(FIRM)
    profile_fields = set(Profile.model_fields.keys())

    def fields_in(pred):
        if pred.field is not None:
            return {pred.field}
        subs = (pred.any_of or []) + (pred.all_of or [])
        out: set[str] = set()
        for s in subs:
            out |= fields_in(s)
        return out

    for rule in ruleset.rules:
        assert rule.applies_when is not None
        for field in fields_in(rule.applies_when):
            assert field in profile_fields, f"{rule.id}: unknown field {field}"


def test_every_referenced_document_exists_in_catalog():
    ruleset = load_ruleset(FIRM)
    for rule in ruleset.rules:
        referenced = list(rule.documents)
        if rule.nested and rule.stub_group:
            referenced += rule.stub_group.documents
        for doc_id in referenced:
            assert doc_id in ruleset.documents, f"{rule.id}: unknown doc {doc_id}"


def test_nested_rules_have_stub_groups():
    ruleset = load_ruleset(FIRM)
    for rule in ruleset.rules:
        if rule.nested:
            assert rule.stub_group is not None, f"{rule.id} nested but no stub_group"


def test_unknown_firm_raises():
    with pytest.raises(RulesetValidationError):
        load_ruleset("no_such_firm")
