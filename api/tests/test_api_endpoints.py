from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings

client = TestClient(app)


def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_settings_unauthorized_without_token():
    response = client.get("/api/v1/settings")
    assert response.status_code == 401
    assert "authentication token" in response.json()["detail"]


def test_settings_authorized_with_bearer_token():
    settings = get_settings()
    login = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    token = login.json()["access_token"]
    response = client.get(
        "/api/v1/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "llm_provider" in data
    assert "llm_key_strategy" in data
