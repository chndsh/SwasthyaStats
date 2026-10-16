import json
from unittest.mock import patch, MagicMock
from app.db import SessionLocal
from app.models import Patient, Document, Observation, Extraction
from app.llm.client import LlmResponse
from app.services.documents import _run_extraction_stage

MOCK_LLM_RESPONSE = json.dumps({
    "lab_name": "Test Lab",
    "report_date": "2026-10-01",
    "observations": [
        {
            "test_name": "Hemoglobin",
            "value": 13.2,
            "value_text": None,
            "unit": "g/dL",
            "ref_low": 12.0,
            "ref_high": 16.0,
            "flag": "normal",
            "line_ids": [1, 2],
        }
    ],
})


def _create_test_document_with_ocr(db):
    patient = db.query(Patient).filter(Patient.id == 1).first()
    if not patient:
        patient = Patient(id=1, name="Test Patient")
        db.add(patient)
        db.commit()

    doc = Document(
        patient_id=1,
        filename="test_ocr_report.png",
        sha256="dummy_sha256_for_extraction_test",
        status="ocr",
        ocr_text="Hemoglobin | 13.2 | g/dL | 12.0–16.0",
        ocr_lines=[
            {"id": 1, "page": 1, "text": "Hemoglobin", "bbox": [0, 0, 100, 20], "conf": 0.95, "row_id": 1},
            {"id": 2, "page": 1, "text": "13.2", "bbox": [110, 0, 160, 20], "conf": 0.94, "row_id": 1},
        ],
        page_count=1,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_pipeline_creates_pending_observations():
    db = SessionLocal()
    try:
        doc = _create_test_document_with_ocr(db)

        with patch("app.services.documents.OpenAICompatClient") as MockClient:
            instance = MockClient.return_value
            instance.chat.return_value = LlmResponse(
                content=MOCK_LLM_RESPONSE,
                prompt_tokens=50,
                completion_tokens=30,
                latency_ms=100,
                model_used="mock-model",
                key_label="k1",
            )
            _run_extraction_stage(doc.id, db)

        db.refresh(doc)
        assert doc.status == "needs_review"

        obs = db.query(Observation).filter(Observation.document_id == doc.id).all()
        assert len(obs) == 1
        assert obs[0].test_name == "Hemoglobin"
        assert obs[0].value_num == 13.2
        assert obs[0].status == "pending"

        extractions = db.query(Extraction).filter(Extraction.document_id == doc.id).all()
        assert len(extractions) == 1
        assert extractions[0].field_confidence is not None
    finally:
        db.close()


def test_pipeline_sets_rate_limited_on_exhausted_keys():
    db = SessionLocal()
    try:
        doc = _create_test_document_with_ocr(db)

        with patch("app.services.documents.OpenAICompatClient") as MockClient:
            instance = MockClient.return_value
            instance.chat.side_effect = RuntimeError("All configured API keys are currently exhausted")
            _run_extraction_stage(doc.id, db)

        db.refresh(doc)
        assert doc.status == "rate_limited"
    finally:
        db.close()
