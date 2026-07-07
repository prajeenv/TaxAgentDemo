# Tax Intake Agent — Prototype

A **prototype** of a client-facing conversational intake agent for a solo German
tax consultant (*Steuerberaterin*) who prepares income-tax returns
(*Einkommensteuererklärung*). It runs the structured intake interview
conversationally — the kind a consultant would do by phone — and produces a
**personalized list of documents** the client must submit, narrowed
**interactively during the conversation**.

> This is a prototype built to demo to a specific consultant and gather feedback —
> not a product. It runs on a **proxy ruleset** (a realistic stand-in), to be
> replaced by the consultant's real rules after the discovery call.

## The core principle

> **The LLM handles language. A deterministic, inspectable, editable ruleset handles
> the document determination. The two are cleanly separated.**

The agent converses and extracts facts into a structured profile. It does **not**
decide which documents are required — it hands the facts to a pure-Python
determination engine, which computes the list from rules-as-data. This is what keeps
the determination **testable**, **editable**, and within the reserved-advice legal
boundary (§33 StBerG). A test (`tests/test_separation.py`) structurally forbids the
engine from importing any LLM code.

## Architecture

```
Client chat (/chat)  ──►  POST /session/{id}/message  ──►  Conversation runner (LLM)
   ▲   ▲                                                     │ extract facts -> Profile
   │   │ tracker (engine result)                            ▼
   │   └───────────────────────  determine(Profile, Ruleset)  ◄── rules.yaml + documents.yaml
   │                              [PURE PYTHON — no LLM]
   └── reply (LLM narrates FROM the engine result)               │
                                                                 ▼
Consultant review (/review/[id])  ──►  edit a fact -> engine re-runs live -> approve
Eval harness  ──►  replays a fixed profile through the SAME engine, diffs vs expected
```

- **Backend** (`backend/`): Python — FastAPI + the determination engine + eval
  harness + the conversation runner and reserved-advice guardrail.
- **Frontend** (`frontend/`): Next.js (App Router) + Tailwind — the client chat with
  a live document tracker, and the consultant review surface.
- **LLM**: DeepSeek V4 Flash (primary) or Claude Sonnet 5 (fallback), behind a
  swappable provider seam. The determination engine and eval harness use **no LLM**.

See [`docs/intake_agent_prototype_spec.md`](docs/intake_agent_prototype_spec.md) for
the build spec, [`docs/design_frontend_and_guardrail.md`](docs/design_frontend_and_guardrail.md)
for the frontend + guardrail design, and [`docs/demo_script.md`](docs/demo_script.md)
for a discovery-call walkthrough.

## The reserved-advice guardrail

The one guardrail that matters. The agent must never answer substantive tax
questions ("can I deduct X?", "will I owe money?") — it recognizes them, does **not**
answer, hands off warmly to the consultant, and logs the escalation. It's a
three-layer defense:

1. a positive-framing system prompt,
2. structured self-classification (the model raises its hand as data), and
3. a deterministic runner backstop that escalates **even if the model misses it**.

Because of layer 3, the boundary holds **even with no LLM key configured** — a
reserved-advice question is caught, handed off, and logged by the backstop alone.

---

## Running it

### Prerequisites
- **Python 3.10+** (the machine this was built on has 3.10; the code targets it).
- **Node 18+** (built with Node 24).

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"     # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux

# Run the tests (the primary validation — no LLM needed):
.venv/Scripts/python.exe -m pytest -q

# Start the API:
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

**LLM key (optional but recommended for the full chat experience):** copy
`backend/.env.example` to `backend/.env` and set `DEEPSEEK_API_KEY` (default
provider). Without a key the chat runs in *degraded mode* — canned replies, no
free-text fact extraction — but the guardrail and the whole determination/review
story still work. To use Claude instead, set `LLM_PROVIDER=anthropic` and
`ANTHROPIC_API_KEY`.

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local        # NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev                             # http://localhost:3000
```

Open **http://localhost:3000/chat** for the client intake. The session id is created
on load; the consultant review surface is at **/review/[sessionId]**.

### Run the eval harness

```bash
# via the API:
curl -X POST http://localhost:8000/eval/run -H "Content-Type: application/json" -d '{}'
# or as part of the test suite (tests/test_engine.py asserts every case matches).
```

## Editing the ruleset

The whole point: a non-programmer consultant can edit the rules as data.

- `backend/rules/steuerkanzlei_mueller/rules.yaml` — the 20 conditions
  (condition → triggering question → documents). Add a rule block, change a
  `documents` list, or promote a stubbed sub-condition into a live rule.
- `backend/rules/steuerkanzlei_mueller/documents.yaml` — the document catalog.

The loader validates every rule's predicate field against the profile at load time,
so a typo fails fast with a clear message.

## What's intentionally out of scope

Real messaging/WhatsApp, async document-chasing, DATEV integration, real client
data/upload, the production control layer, multi-tenant, DSGVO/security machinery.
This is a prototype with no real data. See the spec's §2 for the full list.
