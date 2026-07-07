# Discovery-Call Demo Script

A scripted client persona and walkthrough that deliberately hits the three
thesis-proving moments in one short conversation:

1. **A nested/stubbed rule** — rental income → the full document bundle appears,
   flagged for the consultant to refine.
2. **A confirmation checkpoint** — the agent reflects back captured facts at a
   branch point and invites correction.
3. **A reserved-advice escalation** — the client asks a tax-judgment question; the
   agent refuses to answer, hands off warmly, and logs it.

> **Two ways to run it.** With a DeepSeek (or Anthropic) key configured, the agent
> chats naturally and the tracker narrows live as facts are extracted — this is the
> full experience. Without a key, the chat runs in *degraded mode*: replies are
> canned and facts aren't extracted from free text, but the reserved-advice
> **guardrail still fires** (via the deterministic backstop) and the **review
> surface** demonstrates the live determination end-to-end. See the README for
> where to drop the key.

---

## The persona — "Anna Berger"

- Married; got married *this year* (a marital-status change → checkpoint + stub).
- Employed full-time all year.
- Rents out one flat (→ the rental stub bundle).
- One child in Kita (childcare).
- Curious about deductions (→ the escalation).

---

## The walkthrough (client-side, at `/chat`)

Type these as the client, in order. Suggested agent behavior noted in italics.

1. **Opener reply:**
   > "Hallo! Ich bin dieses Jahr verheiratet und war das ganze Jahr angestellt.
   > Wir haben ein kleines Kind in der Kita, und ich vermiete eine Wohnung."

   *The agent extracts several facts at once (married, marital change, employed all
   year, child/childcare, rental) and — at this branch point — runs a **confirmation
   checkpoint**: reflects them back and asks Anna to confirm or add. Watch the
   tracker: rental documents move into "Benötigt" (the stub bundle), childcare and
   wage certificate appear, and several conditions drop into "Trifft wohl nicht zu."*

2. **Confirm the checkpoint:**
   > "Ja, das stimmt. Sonst nichts Besonderes."

   *The agent continues down the remaining conditions it hasn't covered.*

3. **The escalation — ask for tax advice:**
   > "Kann ich eigentlich mein Arbeitszimmer absetzen?"

   *The agent does NOT answer. It hands off warmly — "Das ist eine wirklich gute
   Frage für Frau Weber — ich merke sie vor…" — and shows the "↗ An Ihre
   Steuerberaterin weitergegeben" chip. The tracker does not change (no new fact).*

4. **Optionally, an outcome question to reinforce the boundary:**
   > "Und bekomme ich am Ende eine Erstattung?"

   *Again handed off (an outcome question) — the agent never speculates about the
   result.*

5. **Wrap up** — as the conditions are covered, the agent reaches its closing turn:
   the list is **provisional**, Frau Weber will review and **email the confirmed
   list**, and the agent cannot speak to tax outcomes.

---

## The consultant view (`/review/[sessionId]`)

Open the review surface for the same session (the session id is in the URL after
`/chat` creates it; in a real product this is a link the consultant receives).

- **Profil** — every fact Anna gave, each editable. **Toggle "Vermietet Immobilie"
  to Nein** and watch the rental bundle (7 documents) drop out of the list and the
  refine flag disappear. That live recompute *is* the pitch: the ruleset is
  deterministic and editable, not a black box.
- **Benötigte Unterlagen** — grouped, each with a `Regel N` provenance pill. The
  rental documents carry the amber **⚑ verfeinern** chip; the **Zu verfeinern**
  callout explains the bundle is deliberately complete and she narrows it.
- **Eskalationen** — Anna's deduction and refund questions appear as "Flagged for
  you" cards, quoted verbatim, categorized, with the reason. This is the diagnostic
  map of where her real judgment lives.
- **Freigeben** — the draft-and-approve action; the confirmation states the list
  will be emailed to the client.

---

## What the demo proves

- **The separation holds:** the agent gathered facts; a deterministic engine (not
  the model) produced the list; the consultant approves. Editing a fact recomputes
  the list in front of her.
- **The stub strategy is honest:** nested conditions produce the full bundle,
  clearly flagged "to refine," not silently wrong.
- **The reserved-advice line is real:** the agent reliably refuses tax judgment and
  outcome questions, hands off warmly, and logs them — even if the model is
  unreachable.
