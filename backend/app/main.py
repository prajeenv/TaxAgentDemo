"""FastAPI application entry point.

Wires the routes and CORS. Run with:
    cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_eval, routes_rules, routes_session
from app.config import FRONTEND_ORIGIN

app = FastAPI(
    title="Tax Intake Agent — Prototype API",
    version="0.1.0",
    description=(
        "Prototype backend for a conversational tax-intake agent. The LLM extracts "
        "facts into a profile; a deterministic engine computes the document list."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_session.router, tags=["session"])
app.include_router(routes_eval.router, tags=["eval"])
app.include_router(routes_rules.router, tags=["rules"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
