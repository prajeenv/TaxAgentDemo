"""Load and validate a firm's rules-as-data.

Loading is the one place we assert the coupling between rules and the profile:
every predicate `field` must name a real attribute on `Profile`. Catching this at
load time (not mid-conversation) is what makes the ruleset safe for a consultant
to hand-edit — a typo'd field name fails fast with a clear message.

Pure Python + pydantic + pyyaml. No LLM import.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Document, Predicate, Profile, Rule, Ruleset

# Firm rulesets live under backend/rules/<firm>/
_RULES_ROOT = Path(__file__).resolve().parents[2] / "rules"

# The set of valid field names a predicate may reference.
_PROFILE_FIELDS = set(Profile.model_fields.keys())


class RulesetValidationError(ValueError):
    """Raised when a firm's rules-as-data is structurally invalid."""


def _validate_predicate(pred: Predicate, rule_id: str) -> None:
    """Assert a predicate references only real profile fields and is well-formed."""
    branches = [pred.field is not None, pred.any_of is not None, pred.all_of is not None]
    if sum(branches) != 1:
        raise RulesetValidationError(
            f"Rule '{rule_id}': applies_when must have exactly one of "
            f"{{field, any_of, all_of}}."
        )
    if pred.field is not None:
        if pred.field not in _PROFILE_FIELDS:
            raise RulesetValidationError(
                f"Rule '{rule_id}': applies_when.field '{pred.field}' is not a "
                f"Profile attribute. Valid fields: {sorted(_PROFILE_FIELDS)}"
            )
        return
    for sub in (pred.any_of or []) + (pred.all_of or []):
        _validate_predicate(sub, rule_id)


def _validate_rule(rule: Rule, catalog: dict[str, Document]) -> None:
    """Assert a rule's predicate and referenced document ids are valid."""
    if rule.applies_when is None:
        raise RulesetValidationError(f"Rule '{rule.id}': missing applies_when.")
    _validate_predicate(rule.applies_when, rule.id)

    # Every referenced document id must exist in the catalog.
    referenced = list(rule.documents)
    if rule.nested:
        if rule.stub_group is None:
            raise RulesetValidationError(
                f"Rule '{rule.id}': nested is true but stub_group is missing."
            )
        referenced += rule.stub_group.documents
    for doc_id in referenced:
        if doc_id not in catalog:
            raise RulesetValidationError(
                f"Rule '{rule.id}': references unknown document id '{doc_id}'."
            )


def load_ruleset(firm: str) -> Ruleset:
    """Load, parse, and validate a firm's document catalog + rules.

    Raises RulesetValidationError on any structural problem.
    """
    firm_dir = _RULES_ROOT / firm
    documents_path = firm_dir / "documents.yaml"
    rules_path = firm_dir / "rules.yaml"

    if not documents_path.exists() or not rules_path.exists():
        raise RulesetValidationError(
            f"Firm '{firm}': expected documents.yaml and rules.yaml under {firm_dir}"
        )

    documents_raw = yaml.safe_load(documents_path.read_text(encoding="utf-8"))
    rules_raw = yaml.safe_load(rules_path.read_text(encoding="utf-8"))

    # Parse documents into a keyed catalog, checking for duplicate ids.
    catalog: dict[str, Document] = {}
    for entry in documents_raw.get("documents", []):
        doc = Document(**entry)
        if doc.id in catalog:
            raise RulesetValidationError(f"Duplicate document id '{doc.id}'.")
        catalog[doc.id] = doc

    # Parse rules, checking for duplicate ids.
    rules: list[Rule] = []
    seen_rule_ids: set[str] = set()
    for entry in rules_raw.get("rules", []):
        rule = Rule(**entry)
        if rule.id in seen_rule_ids:
            raise RulesetValidationError(f"Duplicate rule id '{rule.id}'.")
        seen_rule_ids.add(rule.id)
        _validate_rule(rule, catalog)
        rules.append(rule)

    return Ruleset(firm=firm, rules=rules, documents=catalog)
