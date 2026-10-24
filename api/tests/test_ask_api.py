import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.rag.orchestrator import AskResult
from app.schemas import CitationRef

from app.config import get_settings

client = TestClient(app)


def auth_headers():
    settings = get_settings()
    token = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_ask_endpoint_requires_api_key():
    r = client.post("/api/v1/ask", json={"question": "What is my HbA1c?"})
    assert r.status_code == 401


def test_ask_endpoint_returns_answer(monkeypatch):
    from app.routers import ask

    def fake_ask(db, question, user_id=None):
        return AskResult(
            answer="Your HbA1c is 7.2% [obs:101].",
            citations=[CitationRef(type="obs", id=101)],
        )

    monkeypatch.setattr(ask, "orchestrator_ask", fake_ask)

    r = client.post("/api/v1/ask", json={"question": "What is my HbA1c?"}, headers=auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert "Your HbA1c is 7.2%" in data["answer"]
    assert len(data["citations"]) == 1
    assert data["citations"][0]["type"] == "obs"
    assert data["citations"][0]["id"] == 101
