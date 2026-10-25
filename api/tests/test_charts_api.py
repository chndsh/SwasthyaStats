import datetime
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Patient, Document, Observation

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
def chart_test_data():
    db = SessionLocal()
    patient = db.query(Patient).filter(Patient.id == 1).first()
    if not patient:
        patient = Patient(id=1, name="Test Patient")
        db.add(patient)
        db.commit()

    doc1 = Document(
        patient_id=1,
        filename="report1.png",
        sha256="charts_test_sha1",
        status="confirmed",
        doc_date=datetime.date(2026, 1, 15),
        page_count=1,
    )
    doc2 = Document(
        patient_id=1,
        filename="report2.png",
        sha256="charts_test_sha2",
        status="confirmed",
        doc_date=datetime.date(2026, 6, 15),
        page_count=1,
    )
    db.add_all([doc1, doc2])
    db.commit()
    db.refresh(doc1)
    db.refresh(doc2)

    obs1 = Observation(
        patient_id=1,
        document_id=doc1.id,
        test_name="HbA1c",
        canonical_test_id="hba1c",
        value_num=7.1,
        unit="%",
        ref_low=4.0,
        ref_high=5.6,
        flag="high",
        collected_at=datetime.date(2026, 1, 15),
        status="confirmed",
        page_no=1,
    )
    obs2 = Observation(
        patient_id=1,
        document_id=doc2.id,
        test_name="HbA1c",
        canonical_test_id="hba1c",
        value_num=6.8,
        unit="%",
        ref_low=4.0,
        ref_high=5.6,
        flag="high",
        collected_at=datetime.date(2026, 6, 15),
        status="confirmed",
        page_no=1,
    )
    obs3 = Observation(
        patient_id=1,
        document_id=doc1.id,
        test_name="Glucose",
        canonical_test_id="glucose_fasting",
        value_num=95.0,
        unit="mg/dL",
        ref_low=70.0,
        ref_high=99.0,
        flag="normal",
        collected_at=None,  # Null date to test exclusion
        status="confirmed",
        page_no=1,
    )
    obs_pending = Observation(
        patient_id=1,
        document_id=doc1.id,
        test_name="PendingTest",
        value_num=10.0,
        unit="mg/L",
        status="pending",  # Pending should NOT be listed
    )
    db.add_all([obs1, obs2, obs3, obs_pending])
    db.commit()

    yield {
        "doc1_id": doc1.id,
        "doc2_id": doc2.id,
    }

    # Cleanup
    db.query(Observation).filter(Observation.document_id.in_([doc1.id, doc2.id])).delete()
    db.query(Document).filter(Document.id.in_([doc1.id, doc2.id])).delete()
    db.commit()
    db.close()


def test_list_tests_empty():
    # Calling /tests when no observations match or before data
    r = client.get("/api/v1/tests", headers=auth_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_tests_with_confirmed_obs(chart_test_data):
    r = client.get("/api/v1/tests", headers=auth_headers())
    assert r.status_code == 200
    items = r.json()
    names = [t["test_name"] for t in items]
    assert "HbA1c" in names
    assert "PendingTest" not in names  # Pending must be excluded

    hba1c = next(t for t in items if t["test_name"] == "HbA1c")
    assert hba1c["count"] == 2
    assert hba1c["latest_value"] == 6.8
    assert hba1c["latest_unit"] == "%"
    assert hba1c["latest_date"] == "2026-06-15"
    assert hba1c["previous_value"] == 7.1
    assert hba1c["delta_value"] is not None
    assert hba1c["is_abnormal"] is True


def test_charts_lab_no_data():
    r = client.get("/api/v1/charts/lab?test=NonExistentTestXYZ", headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == []
    assert body["ref_low"] is None
    assert body["ref_high"] is None
    assert body["unit"] is None


def test_charts_lab_returns_points(chart_test_data):
    r = client.get("/api/v1/charts/lab?test=HbA1c", headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["test_name"] == "HbA1c"
    assert len(body["points"]) == 2
    # Verify chronological ordering
    assert body["points"][0]["value"] == 7.1
    assert body["points"][0]["date"] == "2026-01-15"
    assert body["points"][1]["value"] == 6.8
    assert body["points"][1]["date"] == "2026-06-15"
    assert body["unit"] == "%"
    assert body["ref_low"] == 4.0
    assert body["ref_high"] == 5.6


def test_charts_lab_excludes_null_dates(chart_test_data):
    r = client.get("/api/v1/charts/lab?test=Glucose", headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == []  # Excluded because collected_at is None


def test_charts_lab_date_filter(chart_test_data):
    r = client.get("/api/v1/charts/lab?test=HbA1c&from=2026-05-01&to=2026-12-31", headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == 1
    assert body["points"][0]["date"] == "2026-06-15"


def test_charts_merges_name_variations_into_single_entry(chart_test_data):
    db = SessionLocal()
    try:
        doc = db.query(Document).first()
        # Create observations with slight name variations
        obs1 = Observation(
            user_id=1,
            document_id=doc.id,
            test_name="TOTAL LEUCOCYTE COUNT(TC)",
            value_num=7280.0,
            unit="cell/uL",
            status="confirmed",
            collected_at=datetime.date(2025, 4, 22),
            page_no=1,
        )
        obs2 = Observation(
            user_id=1,
            document_id=doc.id,
            test_name="TOTAL LEUCOCYTE COUNT (TC)",
            value_num=5050.0,
            unit="cell/uL",
            status="confirmed",
            collected_at=datetime.date(2026, 7, 21),
            page_no=1,
        )
        db.add_all([obs1, obs2])
        db.commit()

        # Check /api/v1/tests has exactly 1 entry for white blood cell count / total leucocyte count
        r = client.get("/api/v1/tests", headers=auth_headers())
        assert r.status_code == 200
        tests = r.json()
        wbc_entries = [t for t in tests if "leucocyte" in t["test_name"].lower() or "white blood cell" in t["test_name"].lower()]
        assert len(wbc_entries) == 1
        assert wbc_entries[0]["count"] >= 2

        # Check /api/v1/charts/lab returns both points
        r_chart = client.get(f"/api/v1/charts/lab?test={wbc_entries[0]['test_name']}", headers=auth_headers())
        assert r_chart.status_code == 200
        chart_data = r_chart.json()
        assert len(chart_data["points"]) >= 2
    finally:
        db.close()

