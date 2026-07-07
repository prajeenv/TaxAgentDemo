# Tax Intake Agent — Prototype Specification

> **How to read this document.** This is a build specification, not an implementation. It describes **what** to build and the constraints that bound it. It deliberately leaves **how** — data formats, evaluator design, code structure, storage, wiring — to the implementer. Nothing structural here should be treated as prescriptive code.

---

## 1. Purpose and context

A client-facing conversational intake agent for a solo German tax consultant (*Steuerberaterin*) who prepares income-tax returns (*Einkommensteuererklärung*). It conducts the structured intake interview a consultant would normally run by phone, and produces a **personalized list of documents** the client must submit — determined **interactively, during the conversation**, so the client leaves already knowing their list.

The prototype has two jobs, in priority order:

1. **Primary — validation.** Prove that an explicit, editable ruleset can reproduce a consultant's document-determination judgment.
2. **Secondary — demonstration.** Be vivid and credible enough to show a consultant in a discovery call, and to serve as the artifact she reacts to and corrects.

**On the ruleset source.** This prototype is built on a **proxy ruleset** derived from *one* consultant's document-requirements list. It is a realistic stand-in, not the target consultant's actual rules. Her real rules — and a real evaluation set — replace this content after the discovery call, ideally sourced from her recorded intake transcripts with personal details redacted.

---

## 2. Scope

**In scope — build this:**

- The conversational intake agent (the front-end that talks to the client)
- A deterministic determination engine (condition → required documents)
- The interactive-determination behaviour (narrow the list live, in-conversation)
- A thin, warm opening turn (free-text, fact-extracting)
- A draft-and-approve review surface for the consultant
- An escalation **stub** for out-of-scope questions
- An eval-harness **scaffold** (replays a past interview through the determination engine)

**Out of scope — do NOT build:**

- Any real messaging channel or WhatsApp integration (the prototype uses a web chat UI)
- The asynchronous document-chasing coordinator
- DATEV or any external-system integration
- Real client data, real document upload, or real document processing
- The production control layer (daily digest, approve-by-reply, exception routing)
- Multi-tenant / multi-firm support
- Security / DSGVO machinery (EU hosting, DPAs, retention, deletion) — unnecessary because **no real client data is used**
- Answering client sub-questions (beyond the escalation stub)
- Multi-instance / sampling logic for documents

---

## 3. Core principle

One rule governs the whole design:

> **The LLM handles language. A deterministic, inspectable ruleset handles the determination. The two are cleanly separated.**

The agent conducts the conversation and extracts facts into a structured profile. It does **not** decide which documents are required — it hands the collected facts to the determination engine, which computes the list by explicit rules. This separation is what keeps the determination **testable**, **editable**, and safely within the reserved-advice boundary (§7). It is the most important property of the system; preserve it everywhere.

---

## 4. Components

### 4.1 Conversation runner (the intake agent)
LLM-driven. Conducts the interview conversationally: asks the questions, understands messy free-text answers, extracts them into structured facts, tracks what has been collected, and does not re-ask what the client already volunteered. Runs the interactive-determination walk-through (§5). **Does not compute the document list.**

### 4.2 Profile store
The collected facts as a structured object — tax year(s), employment, marital status and any change, children and ages, and the condition flags in §6. This is the *completed client profile* artifact.

### 4.3 Determination engine
A deterministic function: profile in, required-document list out, by the explicit rules in §6. **Inspectable and editable — not a model.** Represent the rules as editable data (format is the implementer's choice), not hard-coded branching. This is the *proposed document list* artifact.

### 4.4 Review surface
Shows the consultant the profile and the proposed document list to review, edit, and approve. **Draft-and-approve:** the agent produces, the consultant approves before anything is final. This surface is both the reserved-advice safeguard and the place where the consultant co-authors and corrects the rules against real cases.

### 4.5 Eval harness
Separate from the live flow. Replays a past interview (a set of client answers) through the determination engine and diffs its output against the document list the consultant actually produced. A **scaffold** for now, populated with real transcripts later. This is the evidence generator for the primary (validation) job.

---

## 5. Interaction model — interactive determination

The prototype uses the **interactive-determination** interview style. (Consultants use one of two styles; the other is *collect-then-determine*. Interactive is chosen here because it is the stronger demonstration and stresses the harder capability — if it works, the simpler style is trivially reachable.)

**Behaviour:**

- Open with a thin, warm turn (§5.1).
- Then walk the conditions. For each, ask the triggering question, and as answers arrive, determine applicability **live** — tell the client which documents apply and which do not, as you go.
- Narrow the full ~20-item list down to the client's actual set **during** the conversation, surfacing *why* an item does or does not apply where natural.
- **End state:** the client leaves already knowing their personalized document list.

### 5.1 The opening turn
- Open with one warm, open question — e.g. *"Tell me a bit about your situation."*
- Absorb whatever the client volunteers and extract structured facts from it.
- **Do not silently skip, and do not flatly assert a conclusion.** Where the opener lets the agent infer a fact or skip an upcoming question, use an **open confirmation checkpoint**: reflect back what was captured → state what it implies for the next question(s) → invite the client to confirm *or* correct/add detail. E.g. *"You mentioned you're married with a young child — so I'd normally skip the questions about spousal status and move on to childcare. Does that sound right, or is there something about your family situation I should know?"*
- The checkpoint is deliberately **open to correction**. It exists because free-text extraction sometimes misreads, and because an opener is a summary that omits nuance (a separation, a child living abroad). Naming the inference back gives the client the moment to catch a wrong reading *and* to add what they didn't think to volunteer — **before** it propagates into the document list.
- **Boundary:** the checkpoint confirms **facts and interview-flow** (what was captured; which questions come next or are skipped). It must **never** confirm a **tax outcome**. *"So I'll ask about childcare next"* is fine; *"so you'll get the married benefit"* is the reserved line (§7).
- **Do this at branch points** — where an inference is about to be acted on (a condition applied, a branch skipped). Stay **light and conversational** on ordinary collection; do not run a heavy three-part read-back after every sentence, or the intake becomes bureaucratic.
- This turn is the showcase of the agent's real intelligence: **extract-from-free-text**, **reflect-and-confirm**, **don't-re-ask**. Keep it thin, but get this behaviour right.

---

## 6. Determination rules (content)

This is **content specification.** Represent and evaluate it however the implementation prefers — the requirement is only that it be explicit, deterministic, and editable.

**Baseline questions** — asked of everyone; they branch the rest: which **tax year(s)**; **employed** during the year and whether the **whole** year; **marital status** and any **change** during the year; **children** and their **ages**.

**Conditional rules** — each is *condition → the question that establishes it → the documents that result if true*. Read top-to-bottom, this list is also the script for the interactive walk-through.

| # | Condition — *if true…* | Triggering question | Documents required |
|---|---|---|---|
| 1 | Received wages/salary | Were you employed during [year]? | Wage tax certificate(s) |
| 2 | Receives a pension | Do you receive any pension — statutory or occupational? | Pension certificates; §22 occupational certs; wage-tax certs for pension payments |
| 3 | Investment income above the allowance, or tax withheld | Did you have investment income (interest, dividends, capital gains) — above the tax-free amount, or with tax withheld? | Annual + tax certificates for all investment income |
| 4 | Owns property that is rented out | Do you rent out any property? *(+ how long rented, when purchased, financed?)* | Rental contract; **if rented longer:** Annex "V" from last return; purchase contract; notary/court/agent fees; total production costs or purchase price; debt interest + disagio (loan statements); other property costs (utilities, insurance, property tax, refuse) |
| 5 | Holds participations/shareholdings | Do you hold any business participations or shareholdings (partnership, fund)? | Provisional notifications of shareholdings |
| 6 | Marital-status change during the year | Did your marital status change — marriage, divorce, separation, a child born, or death of spouse? | Per sub-case: marriage cert / divorce decree / exact separation date / birth cert (new child) / life certificate (child living elsewhere) / death cert |
| 7 | Child over 18 in education | Do you have children over 18 — in education or training? | Proof of education / voluntary social year / service interruption |
| 8 | Made maintenance payments | Did you pay maintenance to a separated/divorced spouse, or to dependants living abroad? | Annex "U" (ex-spouse); maintenance declarations + payment proof (dependants abroad) |
| 9 | Not employed the whole year | Were there periods you were not employed? | Wage-replacement benefit proof (unemployment, sickness, parental, etc.); proof of non-employment periods (abroad, leave, cure); relative-support declaration; pension statements |
| 10 | Changing workplaces / work away or abroad | Did your workplace change often, or did you work away from home or abroad? | Employer confirmation on changing sites, work abroad, subsistence allowance / travel reimbursement |
| 11 | Professional association or union member | Are you in a professional association or union with membership fees? | Receipts for association contributions |
| 12 | Self-paid work equipment/literature | Did you buy work equipment, tools, or professional literature yourself? | Receipts for work equipment, specialist literature |
| 13 | Further education / training costs | Did you pay for further education, training, or courses? | Receipts: course/exam fees, travel, literature, materials |
| 14 | Pays insurance / Riester / Rürup | Do you pay for insurance (health, life, liability, pension)? A Riester or Rürup pension? | Insurance certificates (life, liability, accident, pension, health, nursing); Riester §92 annual cert; Rürup §10 confirmation |
| 15 | Paid tax-advice or assistance-association fees | Did you pay for tax advice or a tax-assistance association last year? | Receipts for tax consultancy / association fees |
| 16 | Made charitable donations | Did you make any charitable donations? | Donation receipts |
| 17 | Disability (self or child) | Do you or a child have a recognized disability? | Disability notice / ID card from the pension office |
| 18 | Paid childcare costs | Did you pay for childcare (Kita, daycare)? | Childcare invoice (excl. meals/play allowance) + payment/transfer proof |
| 19 | Extraordinary burdens | Any large unreimbursed medical costs, divorce costs, or funeral costs? | Medical receipts + health-insurance subsidy proof; divorce lawyer + court costs; funeral costs exceeding the estate |
| 20 | Household services / craftsmen (§35a) | Did you pay for household services or craftsmen's work at your home? | Craftsmen invoices + payment proof (bank statement); operating-cost statements (if applicable) |

**Notes on the rules:**

- **Nested sub-conditions** (rows 4, 6, 9, 19) are mini-branches, not single yes/nos. For the prototype, **wire the top-level branch and lightly stub the depth beneath it.** *Example (row 4, rental):* ask the top-level question ("do you rent out property?"); if yes, produce the rental documents as a **group** — *"for rental income you'll typically need the rental contract, purchase contract, financing statements if it's financed, cost records…"* — and flag it for the consultant to refine. The branch **exists** (rental → rental documents), but its internal depth is collapsed to "here's the rental bundle" rather than the agent walking every sub-question live and gating each sub-document on its own condition (Annex "V" only if long-term, loan docs only if financed, and so on). That full depth is deferred to the consultant's real ruleset later.
- **Near-universal items** framed as conditional (wage certificate in row 1; health/nursing insurance in row 14): the agent still *asks* — it just expects "yes" almost always. These are not true branches.

---

## 7. Constraints and guardrails

**Non-negotiable:**

- **Determination is deterministic and inspectable — never model-decided.**
- The ruleset is **editable** and **firm-owned** (a single firm for the prototype).
- **The agent must not answer substantive tax questions.** When a client asks one (*"can I deduct X?"*, *"will I owe money?"*), the agent recognizes it, does **not** answer, and routes it to the consultant. This is the reserved-advice line (§33 StBerG) and applies from the very first conversation. It is the one guardrail that is the whole reason this cannot be a generic chatbot.
- The agent must **not reassure or speculate** about outcomes (*"you'll probably get a refund"*).
- **Character: warm but bounded.** Personable and human while collecting information; reflexively *"that's a great question for [the consultant] — I'll make sure she covers it"* the moment anything drifts toward advice. Warmth is a **character**, not a dial turned to maximum — an over-eager agent is *more* likely to wander across the line.
- **Draft-and-approve.** The agent produces the profile and document list; the consultant reviews and approves before anything is treated as final.

**Escalation (stub for the prototype):** when the agent hits something outside its lane — an out-of-scope question, an answer that does not fit the ruleset, a tax-judgment ask — it does **not** improvise. It says a version of *"I'll flag that for [the consultant]"* and **logs what it escalated and why.** Keep the mechanism thin, but make the boundary-awareness real: the agent should reliably know when it does not know, and default to handing off rather than guessing. (The escalation log is diagnostic — it maps where the consultant's real judgment lives.)

**Do NOT over-invest** in general-purpose chatbot guardrails — off-topic chit-chat, prompt injection, adversarial misuse, rate-limiting. Those are product-stage. **Prototype guardrailing is the reserved-advice boundary, done well.** Nothing more.

---

## 8. Implementation freedom

This spec fixes **what** and the constraints. The implementer decides **how**: the rules' data format, the evaluator's design, code structure, storage, and how the pieces wire together. Do not treat any table or structure above as prescriptive code.

**Target stack** (settled direction; internal implementation is the implementer's choice *within* it):

- **Logic core** (determination engine, eval harness): **Python**
- **UI** (chat interface + review surface): **React / Next**
- A **simple API** between them

Storage may be minimal — in-memory or a lightweight local store. This is a prototype with no real data. Do **not** reach for an agent-orchestration framework: the design is one live conversational flow plus a deterministic function, and a plain orchestration loop is clearer and easier to debug than a framework here.

---

## 9. Do not foreclose (thin flags for the data model)

The prototype is single-firm and narrow. Build **none** of the following now — but shape the data model so they are not *blocked* later:

- A document may be **multi-instance** (multiple years/months) with an **all-vs-sample** property — do not model every document as a single item.
- **Questions, rules, and interview style are per-firm** — do not assume one global question set or one fixed interview style.
- The agent may later **answer clarifying** client sub-questions while **judgment** sub-questions escalate — do not assume the agent only ever asks and never handles inbound clarifications.

*(Full reasoning for these deferred dimensions lives in the separate design-decisions document.)*

---

## 10. Success criteria

The prototype is working when:

- The agent opens with a free-text turn, **extracts facts** from it, and does **not re-ask** what was volunteered.
- It **walks the conditions interactively** and narrows the ~20-item list to the client's actual set **live**, surfacing why.
- It **escalates** out-of-scope questions rather than answering them, and **logs** them.
- It presents the completed **profile** and proposed **document list** to the consultant for review and approval.
- The **eval harness** can replay a past interview through the determination engine and diff its output against a known document list.

Optimize for **validating the determination** (primary) and **being vivid to show** (secondary).
