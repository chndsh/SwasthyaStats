import io
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.config import get_settings

client = TestClient(app)


def get_token(email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def create_test_image_bytes():
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_user_cannot_see_other_users_documents():
    settings = get_settings()
    admin_token = get_token(settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)

    # Create a guest user
    client.post(
        "/auth/users",
        json={"email": "guest_iso@test.com", "password": "password123", "display_name": "Guest Iso"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    guest_token = get_token("guest_iso@test.com", "password123")

    # Admin uploads document
    img_bytes = create_test_image_bytes()
    upload = client.post(
        "/api/v1/documents",
        files={"files": ("report.png", img_bytes, "image/png")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert upload.status_code == 202
    admin_doc_id = upload.json()["id"]

    # Admin sees their document
    admin_list = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_list.status_code == 200
    assert any(d["id"] == admin_doc_id for d in admin_list.json())

    # Guest user does NOT see admin's document in list
    guest_list = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {guest_token}"})
    assert guest_list.status_code == 200
    assert not any(d["id"] == admin_doc_id for d in guest_list.json())

    # Guest cannot fetch admin's document by id
    guest_doc = client.get(f"/api/v1/documents/{admin_doc_id}", headers={"Authorization": f"Bearer {guest_token}"})
    assert guest_doc.status_code == 404
