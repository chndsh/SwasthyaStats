from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_settings_unauthorized_without_key():
    response = client.get("/api/v1/settings")
    assert response.status_code == 401
    assert "Invalid or missing API key" in response.json()["detail"]


def test_settings_authorized_with_key():
    response = client.get("/api/v1/settings", headers={"X-API-Key": "change-me"})
    assert response.status_code == 200
    data = response.json()
    assert "llm_provider" in data
    assert "llm_key_strategy" in data
