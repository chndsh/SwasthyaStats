import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


client = TestClient(app)


def _login(email: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_user() -> tuple[str, str, str]:
    email = f"settings_{uuid.uuid4().hex[:10]}@test.com"
    password = "password123"
    response = client.post(
        "/auth/users",
        json={"email": email, "password": password, "display_name": "Settings User"},
        headers={"Authorization": f"Bearer {_login(get_settings().ADMIN_EMAIL, get_settings().ADMIN_PASSWORD)}"},
    )
    assert response.status_code == 201
    return email, password, _login(email, password)


def test_settings_endpoints_require_bearer_authentication():
    for path in (
        "/api/v1/settings",
        "/api/v1/settings/models",
        "/api/v1/usage",
    ):
        response = client.get(path)
        assert response.status_code == 401

    response = client.post("/api/v1/settings/test-llm")
    assert response.status_code == 401


def test_jwt_settings_endpoints_do_not_require_api_key():
    email, password, token = _create_user()
    headers = {"Authorization": f"Bearer {token}"}

    settings = client.get("/api/v1/settings", headers=headers)
    assert settings.status_code == 200

    models = client.get("/api/v1/settings/models", headers=headers)
    assert models.status_code == 200

    usage = client.get("/api/v1/usage", headers=headers)
    assert usage.status_code == 200

    probe = client.post("/api/v1/settings/test-llm", headers=headers)
    assert probe.status_code == 200


def test_settings_are_scoped_to_the_authenticated_user():
    _, _, user_token = _create_user()
    admin_token = _login(get_settings().ADMIN_EMAIL, get_settings().ADMIN_PASSWORD)

    user_headers = {"Authorization": f"Bearer {user_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    updated = client.put(
        "/api/v1/settings",
        json={"llm_model": "user-only-model"},
        headers=user_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["llm_model"] == "user-only-model"

    admin_settings = client.get("/api/v1/settings", headers=admin_headers)
    assert admin_settings.status_code == 200
    assert admin_settings.json()["llm_model"] != "user-only-model"

    user_settings = client.get("/api/v1/settings", headers=user_headers)
    assert user_settings.status_code == 200
    assert user_settings.json()["llm_model"] == "user-only-model"
