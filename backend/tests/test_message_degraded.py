"""Degraded-mode safety test: the reserved-advice boundary holds even with NO LLM.

This is the containment guarantee. When the model provider is unreachable/unconfigured,
the runner uses a safe canned turn — but the DETERMINISTIC backstop still fires on a
reserved-advice utterance, forces the warm handoff, and logs the escalation. Advice
never leaks to the client, model or no model.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(monkeypatch):
    # Ensure no provider key is visible so the LLM call fails into the safe fallback,
    # isolating the deterministic backstop behavior.
    monkeypatch.setattr("app.conversation.llm_client.DEEPSEEK_API_KEY", "")
    monkeypatch.setattr("app.conversation.llm_client.ANTHROPIC_API_KEY", "")
    return TestClient(app)


def test_reserved_advice_escalates_without_llm(client):
    sid = client.post("/session").json()["session_id"]
    r = client.post(
        f"/session/{sid}/message",
        json={"text": "Kann ich mein Arbeitszimmer absetzen?"},
    ).json()
    assert r["escalated"] is True
    # warm, not cold
    low = r["reply_text"].lower()
    assert "kann ich nicht" not in low and "nicht erlaubt" not in low
    # logged with the right category
    log = client.get(f"/session/{sid}").json()["escalation_log"]
    assert len(log) == 1
    assert log[-1]["category"] == "tax_advice"


def test_outcome_question_escalates_without_llm(client):
    sid = client.post("/session").json()["session_id"]
    r = client.post(
        f"/session/{sid}/message",
        json={"text": "Bekomme ich eine Erstattung?"},
    ).json()
    assert r["escalated"] is True
    log = client.get(f"/session/{sid}").json()["escalation_log"]
    assert log[-1]["category"] == "outcome_speculation"


def test_benign_message_does_not_escalate_without_llm(client):
    sid = client.post("/session").json()["session_id"]
    r = client.post(f"/session/{sid}/message", json={"text": "Guten Morgen!"}).json()
    assert r["escalated"] is False
    assert client.get(f"/session/{sid}").json()["escalation_log"] == []
