import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.routers.auth import bootstrap_admin
from app.config import get_settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_admin():
    with SessionLocal() as db:
        bootstrap_admin(db)


def get_admin_token():
    settings = get_settings()
    resp = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_login_success():
    settings = get_settings()
    resp = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    settings = get_settings()
    resp = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_get_me():
    token = get_admin_token()
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == get_settings().ADMIN_EMAIL
    assert data["is_admin"] is True


def test_create_user_admin_only():
    admin_token = get_admin_token()
    # Create regular user
    resp = client.post(
        "/auth/users",
        json={"email": "regular@test.com", "password": "userpass123", "display_name": "Regular User"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    user_data = resp.json()
    assert user_data["email"] == "regular@test.com"
    assert user_data["is_admin"] is False

    # Login as regular user
    user_login = client.post(
        "/auth/login",
        json={"email": "regular@test.com", "password": "userpass123"},
    )
    assert user_login.status_code == 200
    regular_token = user_login.json()["access_token"]

    # Regular user cannot create users
    forbidden = client.post(
        "/auth/users",
        json={"email": "hacker@test.com", "password": "pass"},
        headers={"Authorization": f"Bearer {regular_token}"},
    )
    assert forbidden.status_code == 403


def test_refresh_token_rotation():
    settings = get_settings()
    login = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    old_refresh = login.json()["refresh_token"]

    resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    new_refresh = resp.json()["refresh_token"]
    assert new_refresh != old_refresh

    # Old refresh token must be rejected
    rejected = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert rejected.status_code == 401


def test_logout_revokes_refresh_token():
    settings = get_settings()
    login = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    refresh_tok = login.json()["refresh_token"]
    access_tok = login.json()["access_token"]

    logout = client.post(
        "/auth/logout",
        json={"refresh_token": refresh_tok},
        headers={"Authorization": f"Bearer {access_tok}"},
    )
    assert logout.status_code == 204

    # Using refresh token should fail now
    resp = client.post("/auth/refresh", json={"refresh_token": refresh_tok})
    assert resp.status_code == 401


def test_delete_user():
    admin_token = get_admin_token()
    create = client.post(
        "/auth/users",
        json={"email": "delete_me@test.com", "password": "temp", "display_name": "Delete Me"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create.status_code == 201
    user_id = create.json()["id"]

    delete_resp = client.delete(
        f"/auth/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delete_resp.status_code == 204
