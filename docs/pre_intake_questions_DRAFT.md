# Pre-Intake Clarifying Questions — DRAFT for your review

> **Point 1 from your feedback.** Before the agent walks the 20 conditions, it should
> establish a short set of **foundational facts**. Getting these right first prevents
> the whole intake from being built on a wrong assumption (e.g. the wrong tax year).
>
> This is a DRAFT — please edit: add, remove, reorder, reword. Mark anything you want
> changed. Once you approve, I'll wire it in as an explicit opening phase (the agent
> must resolve these before moving into the 20 conditions), one question per turn.

---

## Why a pre-intake phase

The 20 conditions all assume a few things are already known — above all **which tax
year**. If the agent guesses the year (as it did in your session), every downstream
document is for the wrong year. A short, mandatory foundation phase fixes this: these
facts are ASKED, never assumed.

The agent may still **extract** these from a rich opener if the client volunteers them
(e.g. "married with a 4-year-old" → marital status + child). But any that are still
missing after the opener must be explicitly asked before the 20 conditions begin.

---

## Proposed foundational questions (edit freely)

| # | Question | Why it's foundational | Maps to profile field |
|---|----------|----------------------|----------------------|
| 1 | **Which tax year** is this return for? | Poisons everything if wrong. Must be explicit — never assumed. | `tax_years` |
| 2 | **Marital status**, and did it **change** during that year? | Branches the spousal / joint-vs-separate logic and the r6 marital-change condition. | `marital_status`, `marital_status_changed` |
| 3 | Do you have **children**? (how many, ages) | Gates childcare, child-over-18-education, and family allowances. | `children` |
| 4 | Were you **employed** during the year, and for the **whole** year? | The baseline that most work-related conditions hang off. | `employed_this_year`, `employed_whole_year` |

### Candidates you might want to add (your call)
- **Filing jointly or separately** (if married) — affects which documents/spouse data are needed. *(Not currently a profile field — would need adding if you want it.)*
- **Residency / did you live in Germany the whole year** — relevant for some income sources and the changing-workplaces/abroad condition. *(Not a field yet.)*
- **Do you (or spouse) receive any state benefits** (Elterngeld, Arbeitslosengeld, etc.) — ties to the non-employment-period condition.
- **Confirm the client's name / who the return is for** — a real intake would capture this; the prototype currently doesn't (no PII by design).

---

## Behavior rules for the pre-intake phase (proposed)

1. **Ask, don't assume.** Every foundational fact is either volunteered by the client
   or explicitly asked. The agent must NEVER fill a foundational fact (especially the
   tax year) that the client didn't provide.
2. **One question per turn** (already being fixed as Point 2).
3. **Confirm the year explicitly** before proceeding — a wrong year is high-stakes, so
   even if inferred, reflect it back for confirmation.
4. Only once the foundation is set does the agent move into the 20 conditions.

---

## Open questions for you

- Is question order right? (I put tax year first deliberately.)
- Do you want "filing jointly vs separately" and "residency" added as real fields, or
  are they out of scope for the prototype's proxy ruleset?
- Anything a Steuerberaterin always establishes up front that I've missed?
