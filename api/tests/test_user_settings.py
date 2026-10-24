from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings

client = TestClient(app)


def get_token(email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_guest_settings_isolated_from_admin():
    settings = get_settings()
    admin_token = get_token(settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)

    import uuid
    g_email = f"guest_set_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/auth/users",
        json={"email": g_email, "password": "guestpassword1", "display_name": "Guest Settings"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    guest_token = get_token(g_email, "guestpassword1")

    # Admin configures their own key
    admin_put = client.put(
        "/api/v1/settings",
        json={"llm_api_keys": [{"key": "admin_super_secret_key_12345", "label": "admin-key"}]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_put.status_code == 200
    admin_settings = admin_put.json()
    assert any(k["label"] == "admin-key" for k in admin_settings["llm_api_keys"])

    # Guest inspects their settings: MUST NOT see admin's key
    guest_get = client.get("/api/v1/settings", headers={"Authorization": f"Bearer {guest_token}"})
    assert guest_get.status_code == 200
    guest_settings = guest_get.json()
    assert guest_settings["llm_api_keys"] == []

    # Guest sets their own key
    guest_put = client.put(
        "/api/v1/settings",
        json={"llm_api_keys": [{"key": "guest_private_key_67890", "label": "guest-key"}]},
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert guest_put.status_code == 200
    assert any(k["label"] == "guest-key" for k in guest_put.json()["llm_api_keys"])

    # Admin still sees their own key, not guest's
    admin_get = client.get("/api/v1/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert any(k["label"] == "admin-key" for k in admin_get.json()["llm_api_keys"])
    assert not any(k["label"] == "guest-key" for k in admin_get.json()["llm_api_keys"])
