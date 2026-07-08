// Presentation metadata for profile fields: German labels + control types.
// Keeps the review surface declarative — it maps over these rather than hard-coding
// each field. Order here is the display order.

export type FieldControl = "tristate" | "marital" | "taxyears" | "children";

export interface FieldMeta {
  key: string;
  label: string;
  control: FieldControl;
  group: "Grunddaten" | "Bedingungen";
}

export const MARITAL_OPTIONS: { value: string; label: string }[] = [
  { value: "single", label: "ledig" },
  { value: "married", label: "verheiratet" },
  { value: "divorced", label: "geschieden" },
  { value: "widowed", label: "verwitwet" },
  { value: "separated", label: "getrennt lebend" },
];

// Baseline fields first, then the ~17 condition flags. Labels are Kanzlei-register German.
export const FIELD_META: FieldMeta[] = [
  { key: "tax_years", label: "Steuerjahre", control: "taxyears", group: "Grunddaten" },
  { key: "employed_this_year", label: "Angestellt im Jahr", control: "tristate", group: "Grunddaten" },
  { key: "employed_whole_year", label: "Ganzjährig angestellt", control: "tristate", group: "Grunddaten" },
  { key: "marital_status", label: "Familienstand", control: "marital", group: "Grunddaten" },
  { key: "marital_status_changed", label: "Familienstand geändert", control: "tristate", group: "Grunddaten" },
  { key: "spouse_employed", label: "Ehepartner berufstätig", control: "tristate", group: "Grunddaten" },
  { key: "filing_jointly", label: "Zusammenveranlagung (gemeinsam)", control: "tristate", group: "Grunddaten" },
  { key: "children", label: "Kinder", control: "children", group: "Grunddaten" },

  { key: "receives_pension", label: "Bezieht Rente/Pension", control: "tristate", group: "Bedingungen" },
  { key: "investment_income", label: "Kapitalerträge", control: "tristate", group: "Bedingungen" },
  { key: "rents_out_property", label: "Vermietet Immobilie", control: "tristate", group: "Bedingungen" },
  { key: "holds_participations", label: "Beteiligungen", control: "tristate", group: "Bedingungen" },
  { key: "child_over18_in_education", label: "Kind über 18 in Ausbildung", control: "tristate", group: "Bedingungen" },
  { key: "made_maintenance_payments", label: "Unterhaltszahlungen", control: "tristate", group: "Bedingungen" },
  { key: "changing_workplaces_abroad", label: "Wechselnde Arbeitsorte / Ausland", control: "tristate", group: "Bedingungen" },
  { key: "union_or_association_member", label: "Verband/Gewerkschaft", control: "tristate", group: "Bedingungen" },
  { key: "self_paid_work_equipment", label: "Arbeitsmittel selbst gekauft", control: "tristate", group: "Bedingungen" },
  { key: "further_education_costs", label: "Fortbildungskosten", control: "tristate", group: "Bedingungen" },
  { key: "pays_insurance_riester_ruerup", label: "Versicherungen / Riester / Rürup", control: "tristate", group: "Bedingungen" },
  { key: "paid_tax_advice_fees", label: "Steuerberatungskosten", control: "tristate", group: "Bedingungen" },
  { key: "made_donations", label: "Spenden", control: "tristate", group: "Bedingungen" },
  { key: "disability_self_or_child", label: "Behinderung (selbst/Kind)", control: "tristate", group: "Bedingungen" },
  { key: "paid_childcare", label: "Kinderbetreuungskosten", control: "tristate", group: "Bedingungen" },
  { key: "extraordinary_burdens", label: "Außergewöhnliche Belastungen", control: "tristate", group: "Bedingungen" },
  { key: "household_services_craftsmen", label: "Haushaltsnahe Dienstl. / Handwerker", control: "tristate", group: "Bedingungen" },
];

// Escalation category presentation (spec §1.7 / §4.5).
export const ESCALATION_META: Record<
  string,
  { label: string; gloss: string; className: string }
> = {
  tax_advice: {
    label: "Steuerberatung",
    gloss: "Steuerliche Einschätzung erbeten — Frage nicht beantwortet, an Sie verwiesen.",
    className: "bg-warn-tint text-warn",
  },
  outcome_speculation: {
    label: "Ergebnis-Spekulation",
    gloss: "Frage nach Ergebnis/Erstattung — nicht beantwortet, an Sie verwiesen.",
    className: "bg-amber-50 text-amber",
  },
  out_of_scope: {
    label: "Außerhalb des Umfangs",
    gloss: "Außerhalb des Intake-Umfangs — an Sie verwiesen.",
    className: "bg-slate-100 text-slate",
  },
  unmapped_answer: {
    label: "Nicht zugeordnet",
    gloss: "Antwort nicht eindeutig zuzuordnen — Feld offen gelassen, bitte prüfen.",
    className: "bg-violet-50 text-violet",
  },
};
