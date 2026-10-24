import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.config import get_settings

client = TestClient(app)


def auth_headers():
    settings = get_settings()
    token = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_document_creates_queued_doc_and_streams_page():
    img = Image.new("RGB", (1000, 800), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # 1. Upload
    response = client.post(
        "/api/v1/documents",
        headers=auth_headers(),
        files=[("files", ("test_page.png", buf.getvalue(), "image/png"))],
    )
    assert response.status_code == 202
    data = response.json()
    doc_id = data["id"]
    assert data["status"] in ["queued", "normalizing", "ocr", "needs_review"]

    # 2. Get document details
    doc_resp = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers())
    assert doc_resp.status_code == 200
    assert doc_resp.json()["filename"] == "test_page.png"

    # 3. List documents
    list_resp = client.get("/api/v1/documents", headers=auth_headers())
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert any(d["id"] == doc_id for d in docs)

    # 4. List documents sort by doctor
    sort_resp = client.get("/api/v1/documents?sort_by=doctor_asc", headers=auth_headers())
    assert sort_resp.status_code == 200


def test_upload_rejects_empty_file():
    response = client.post(
        "/api/v1/documents",
        headers=auth_headers(),
        files=[("files", ("empty.png", b"", "image/png"))],
    )
    assert response.status_code == 400


def test_upload_rejects_corrupted_file():
    response = client.post(
        "/api/v1/documents",
        headers=auth_headers(),
        files=[("files", ("corrupted.pdf", b"not-a-real-pdf-header", "application/pdf"))],
    )
    assert response.status_code == 400
