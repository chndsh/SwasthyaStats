import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.routers.auth import bootstrap_admin


client = TestClient(app)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_login() -> dict:
    with SessionLocal() as db:
        bootstrap_admin(db)
    settings = get_settings()
    response = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def create_user(admin_token: str, password: str = "temporary-123") -> tuple[int, str]:
    email = f"password-{uuid.uuid4().hex[:8]}@test.com"
    response = client.post(
        "/auth/users",
        json={"email": email, "password": password, "display_name": "Password User"},
        headers=auth_header(admin_token),
    )
    assert response.status_code == 201
    assert response.json()["must_change_password"] is True
    return response.json()["id"], email


def test_password_change_clears_flag_and_revokes_previous_refresh_token():
    admin = admin_login()
    _, email = create_user(admin["access_token"])
    login = client.post("/auth/login", json={"email": email, "password": "temporary-123"})
    assert login.status_code == 200

    response = client.put(
        "/auth/me/password",
        json={"current_password": "temporary-123", "new_password": "permanent-123"},
        headers=auth_header(login.json()["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is False

    old_refresh = client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert old_refresh.status_code == 401

    old_login = client.post("/auth/login", json={"email": email, "password": "temporary-123"})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", json={"email": email, "password": "permanent-123"})
    assert new_login.status_code == 200


def test_password_change_rejects_wrong_current_and_weak_new_password():
    admin = admin_login()
    _, email = create_user(admin["access_token"])
    login = client.post("/auth/login", json={"email": email, "password": "temporary-123"})
    token = login.json()["access_token"]

    wrong_current = client.put(
        "/auth/me/password",
        json={"current_password": "wrong-password", "new_password": "permanent-123"},
        headers=auth_header(token),
    )
    assert wrong_current.status_code == 401

    weak_new = client.put(
        "/auth/me/password",
        json={"current_password": "temporary-123", "new_password": "short"},
        headers=auth_header(token),
    )
    assert weak_new.status_code == 422


def test_reset_password_sets_flag_and_revokes_previous_refresh_token():
    admin = admin_login()
    user_id, email = create_user(admin["access_token"])
    login = client.post("/auth/login", json={"email": email, "password": "temporary-123"})

    reset = client.put(
        f"/auth/users/{user_id}/password",
        json={"password": "reset-12345"},
        headers=auth_header(admin["access_token"]),
    )
    assert reset.status_code == 204

    old_refresh = client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert old_refresh.status_code == 401
    with SessionLocal() as db:
        from app.models import User

        user = db.query(User).filter(User.id == user_id).one()
        assert user.must_change_password is True


def test_regular_user_cannot_manage_users_and_admin_cannot_delete_self():
    admin = admin_login()
    _, email = create_user(admin["access_token"])
    login = client.post("/auth/login", json={"email": email, "password": "temporary-123"})
    token = login.json()["access_token"]

    for method, path, payload in (
        ("get", "/auth/users", None),
        ("post", "/auth/users", {"email": "blocked@test.com", "password": "temporary-123"}),
    ):
        response = getattr(client, method)(
            path,
            json=payload,
            headers=auth_header(token),
        ) if payload else getattr(client, method)(path, headers=auth_header(token))
        assert response.status_code == 403

    admin_me = client.get("/auth/me", headers=auth_header(admin["access_token"]))
    assert admin_me.status_code == 200
    cannot_delete_self = client.delete(
        f"/auth/users/{admin_me.json()['id']}",
        headers=auth_header(admin["access_token"]),
    )
    assert cannot_delete_self.status_code in {400, 404}
