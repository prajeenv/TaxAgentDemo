"""API integration tests — the engine driven over HTTP (Phase 1).

Uses FastAPI's TestClient so the routes, store, and engine are exercised together
without a running server. No LLM involved (the chat endpoint is Phase 3).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_session_starts_all_pending(client):
    r = client.post("/session").json()
    assert r["opening_turn"]
    assert len(r["tracker_state"]["pending"]) == 20
    assert r["tracker_state"]["required"] == []


def test_patch_profile_recomputes_engine(client):
    sid = client.post("/session").json()["session_id"]
    snap = client.patch(
        f"/session/{sid}/profile",
        json={"field_updates": {"employed_this_year": True, "rents_out_property": True}},
    ).json()
    req_ids = {d["id"] for d in snap["tracker_state"]["required"]}
    assert "wage_tax_cert" in req_ids
    assert "rental_contract" in req_ids
    assert snap["tracker_state"]["refine_flags"]


def test_false_flag_becomes_excluded_over_http(client):
    sid = client.post("/session").json()["session_id"]
    snap = client.patch(
        f"/session/{sid}/profile",
        json={"field_updates": {"receives_pension": False}},
    ).json()
    ex = {t["rule_id"] for t in snap["tracker_state"]["excluded"]}
    pend = {t["rule_id"] for t in snap["tracker_state"]["pending"]}
    assert "r2_pension" in ex and "r2_pension" not in pend


def test_invalid_profile_update_returns_422(client):
    sid = client.post("/session").json()["session_id"]
    resp = client.patch(
        f"/session/{sid}/profile",
        json={"field_updates": {"marital_status": "not_a_valid_value"}},
    )
    assert resp.status_code == 422


def test_approve_marks_session(client):
    sid = client.post("/session").json()["session_id"]
    assert client.post(f"/session/{sid}/approve").json()["approved"] is True


def test_unknown_session_404(client):
    assert client.get("/session/deadbeef").status_code == 404
    assert client.patch(
        "/session/deadbeef/profile", json={"field_updates": {}}
    ).status_code == 404


def test_eval_run_all_pass(client):
    ev = client.post("/eval/run", json={}).json()
    assert ev["total"] >= 3           # seed cases; grows as more are added
    assert ev["passed"] == ev["total"]  # every case must match


def test_rules_introspection(client):
    ru = client.get("/rules").json()
    assert len(ru["rules"]) == 20
    assert len(ru["documents"]) >= 40
