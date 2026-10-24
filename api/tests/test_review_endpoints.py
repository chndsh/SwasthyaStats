import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Patient, Document, Observation, Extraction
from app.config import get_settings

client = TestClient(app)


def auth_headers():
    settings = get_settings()
    token = client.post(
        "/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_setup():
    db = SessionLocal()
    # Ensure patient
    patient = db.query(Patient).filter(Patient.id == 1).first()
    if not patient:
        patient = Patient(id=1, name="Test Patient")
        db.add(patient)
        db.commit()

    # Document with pending observation
    doc = Document(
        patient_id=1,
        filename="report.png",
        sha256="test_sha256_review",
        status="needs_review",
        ocr_lines=[{"id": 1, "page": 1, "text": "Hemoglobin 13.2"}],
        page_count=1,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    obs = Observation(
        patient_id=1,
        document_id=doc.id,
        test_name="Hemoglobin",
        value_num=13.2,
        unit="g/dL",
        status="pending",
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    ext = Extraction(
        document_id=doc.id,
        model="mock",
        prompt_version="v1",
        field_confidence={str(obs.id): 0.92},
    )
    db.add(ext)
    db.commit()

    yield doc.id, obs.id

    db.close()


def test_extraction_endpoint_404_on_missing():
    r = client.get("/api/v1/documents/99999/extraction", headers=auth_headers())
    assert r.status_code == 404


def test_extraction_endpoint_returns_data(test_setup):
    doc_id, obs_id = test_setup
    r = client.get(f"/api/v1/documents/{doc_id}/extraction", headers=auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["document_id"] == doc_id
    assert data["status"] == "needs_review"
    assert len(data["observations"]) == 1
    assert data["observations"][0]["id"] == obs_id
    assert data["observations"][0]["confidence"] == 0.92


def test_patch_observation_updates_value(test_setup):
    doc_id, obs_id = test_setup
    r = client.patch(
        f"/api/v1/observations/{obs_id}",
        headers=auth_headers(),
        json={"value_num": 14.5, "unit": "g/dL"},
    )
    assert r.status_code == 200
    assert r.json()["value_num"] == 14.5


def test_confirm_sets_observations_confirmed(test_setup):
    doc_id, obs_id = test_setup
    r = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["confirmed"] == 1

    # Verify status in DB
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc.status == "confirmed"
        obs = db.query(Observation).filter(Observation.id == obs_id).first()
        assert obs.status == "confirmed"
    finally:
        db.close()


def test_patch_observation_blocked_after_confirm(test_setup):
    doc_id, obs_id = test_setup
    # Confirm first
    client.post(f"/api/v1/documents/{doc_id}/confirm", headers=auth_headers())

    # Attempt to patch
    r = client.patch(
        f"/api/v1/observations/{obs_id}",
        headers=auth_headers(),
        json={"value_num": 99.0},
    )
    assert r.status_code == 409


def test_manual_add_observation_to_document(test_setup):
    doc_id, _ = test_setup
    payload = {
        "test_name": "Serum Ferritin",
        "value_num": 150.0,
        "unit": "ng/mL",
        "ref_low": 30.0,
        "ref_high": 400.0,
        "flag": "normal",
        "page_no": 1,
    }
    r = client.post(
        f"/api/v1/documents/{doc_id}/observations",
        headers=auth_headers(),
        json=payload,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["test_name"] == "Serum Ferritin"
    assert data["value_num"] == 150.0
    assert data["status"] == "pending"
