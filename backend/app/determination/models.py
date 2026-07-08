"""Data models for the determination core.

This module is PURE data + typing. It must never import the LLM/conversation
layer — the whole legal/testability rationale rests on the determination core
being independent of the model. (`tests/test_separation.py` enforces this.)

The `Profile` is the single structured artifact the conversation runner fills in
and the determination engine reads. Every condition flag is tri-state:
    True  -> condition holds
    False -> condition explicitly does not hold
    None  -> not yet asked
The engine uses this to distinguish "no" (excluded) from "unknown" (pending),
which is what powers live narrowing and the "still to ask" column.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

MaritalStatus = Literal["single", "married", "divorced", "widowed", "separated"]


class Child(BaseModel):
    age: Optional[int] = None
    in_education: Optional[bool] = None
    lives_elsewhere: Optional[bool] = None


class Profile(BaseModel):
    """The completed client profile — collected facts, nothing computed."""

    # --- Baseline questions (asked of everyone; they branch the rest) ---
    tax_years: list[int] = Field(default_factory=list)
    employed_this_year: Optional[bool] = None
    employed_whole_year: Optional[bool] = None          # False -> r9 branch
    marital_status: Optional[MaritalStatus] = None
    marital_status_changed: Optional[bool] = None        # True  -> r6 branch
    children: list[Child] = Field(default_factory=list)
    # Captured in the pre-intake phase for the consultant's benefit. NO rule consumes
    # these yet — inventing document rules for spouse income / joint filing is the
    # consultant's professional judgment, wired into her real ruleset later.
    spouse_employed: Optional[bool] = None               # if married: was the spouse working?
    filing_jointly: Optional[bool] = None                # joint (Zusammenveranlagung) vs separate
    # If not employed the whole year: did they receive wage-replacement / state
    # benefits (Elterngeld, Arbeitslosengeld, Krankengeld...). Captured detail under
    # the r9 non-employment stub; the stub already emits wage_replacement_proof, so
    # this refines context for the consultant rather than gating a new document.
    received_wage_replacement: Optional[bool] = None

    # --- Condition flags (rows 2-20; rows 1/9/6 covered by baseline fields) ---
    receives_pension: Optional[bool] = None              # r2
    investment_income: Optional[bool] = None             # r3
    rents_out_property: Optional[bool] = None            # r4  (nested/stubbed)
    holds_participations: Optional[bool] = None          # r5
    child_over18_in_education: Optional[bool] = None      # r7
    made_maintenance_payments: Optional[bool] = None      # r8
    changing_workplaces_abroad: Optional[bool] = None     # r10
    union_or_association_member: Optional[bool] = None    # r11
    self_paid_work_equipment: Optional[bool] = None       # r12
    further_education_costs: Optional[bool] = None         # r13
    pays_insurance_riester_ruerup: Optional[bool] = None   # r14
    paid_tax_advice_fees: Optional[bool] = None            # r15
    made_donations: Optional[bool] = None                  # r16
    disability_self_or_child: Optional[bool] = None        # r17
    paid_childcare: Optional[bool] = None                  # r18
    extraordinary_burdens: Optional[bool] = None           # r19 (nested/stubbed)
    household_services_craftsmen: Optional[bool] = None    # r20


# --- Rules-as-data (loaded, validated shapes) -------------------------------


class Predicate(BaseModel):
    """A tiny declarative predicate over a profile field.

    Exactly one of {field, any_of, all_of} is populated (validated by the loader).
    """

    field: Optional[str] = None
    equals: Optional[Any] = None
    any_of: Optional[list["Predicate"]] = None
    all_of: Optional[list["Predicate"]] = None


class StubGroup(BaseModel):
    label: str
    note: str = ""
    documents: list[str] = Field(default_factory=list)
    # Inert data: documents the real sub-gating for the consultant to activate later.
    # The engine NEVER reads this.
    refine_subconditions: list[dict[str, Any]] = Field(default_factory=list)


class Rule(BaseModel):
    id: str
    condition_label: str
    triggering_question: str
    applies_when: Optional[Predicate] = None
    documents: list[str] = Field(default_factory=list)
    near_universal: bool = False
    nested: bool = False
    stub_group: Optional[StubGroup] = None


class Document(BaseModel):
    id: str
    label: str
    group: str
    # do-not-foreclose flags: carried on the entity, NOT enforced by the prototype engine.
    multi_instance: bool = False
    instance_scope: Literal["all", "sample"] = "all"


class Ruleset(BaseModel):
    """A firm's loaded ruleset: the rules plus the document catalog."""

    firm: str
    rules: list[Rule]
    documents: dict[str, Document]  # keyed by document id


# --- Determination result ---------------------------------------------------

RuleStatus = Literal["applies", "excluded", "pending"]


class RuleTrace(BaseModel):
    """Per-rule outcome — the engine's explanation of why an item does/doesn't apply.

    This is the single source of truth for the live-narrowing tracker and the
    review surface. The LLM narrates from it; it must never invent applicability.
    """

    rule_id: str
    condition_label: str
    triggering_question: str
    status: RuleStatus
    reason: str                     # human-readable ("field rents_out_property is False")
    nested: bool = False


class ResolvedDocument(BaseModel):
    id: str
    label: str
    group: str
    source_rule_ids: list[str]      # provenance: which rule(s) required it
    refine_flag: bool = False       # part of a stubbed nested bundle -> consultant to refine


class RefineFlag(BaseModel):
    rule_id: str
    label: str
    note: str


class DeterminationResult(BaseModel):
    required_documents: list[ResolvedDocument]
    excluded: list[RuleTrace]       # conditions that came back False -> "does NOT apply" narrative
    pending: list[RuleTrace]        # not yet asked -> "still to ask" column
    refine_flags: list[RefineFlag]  # stubbed nested groups needing consultant depth
