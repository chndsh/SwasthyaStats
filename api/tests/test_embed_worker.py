from unittest.mock import patch
import pytest
from app.db import SessionLocal
from app.models import Patient, Document, Observation, Chunk
from app.pipeline.embed_worker import embed_document


@pytest.fixture
def sample_confirmed_document():
    db = SessionLocal()
    patient = db.query(Patient).filter(Patient.id == 1).first()
    if not patient:
        patient = Patient(id=1, name="Test Patient")
        db.add(patient)
        db.commit()

    doc = Document(
        patient_id=1,
        filename="confirmed_report.png",
        sha256="embed_worker_test_sha",
        status="confirmed",
        ocr_text="Hemoglobin 13.2 g/dL\nPlatelets 250000 /uL",
        page_count=1,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    obs1 = Observation(
        patient_id=1,
        document_id=doc.id,
        test_name="Hemoglobin",
        value_num=13.2,
        unit="g/dL",
        ref_low=12.0,
        ref_high=15.5,
        status="confirmed",
        page_no=1,
    )
    obs2 = Observation(
        patient_id=1,
        document_id=doc.id,
        test_name="Platelets",
        value_num=250000.0,
        unit="/uL",
        ref_low=150000.0,
        ref_high=450000.0,
        status="confirmed",
        page_no=1,
    )
    db.add_all([obs1, obs2])
    db.commit()

    doc_id = doc.id
    yield doc_id

    # Cleanup
    db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
    db.query(Observation).filter(Observation.document_id == doc_id).delete()
    db.query(Document).filter(Document.id == doc_id).delete()
    db.commit()
    db.close()


def test_embed_document_creates_chunks(sample_confirmed_document):
    doc_id = sample_confirmed_document
    fake_vec = [0.05] * 384

    with patch("app.pipeline.embed_worker.get_embed_engine") as mock_eng:
        mock_instance = mock_eng.return_value
        mock_instance.model_name = "multilingual-e5-small"
        mock_instance.embed.side_effect = lambda texts: [fake_vec for _ in texts]
        embed_document(doc_id)

    db = SessionLocal()
    chunks = db.query(Chunk).filter(Chunk.document_id == doc_id).all()
    assert len(chunks) >= 2  # observations + OCR page chunk
    assert all(len(c.embedding) == 384 for c in chunks)
    assert any("Hemoglobin" in c.text for c in chunks)
    db.close()


def test_embed_document_replaces_existing_chunks(sample_confirmed_document):
    doc_id = sample_confirmed_document
    fake_vec = [0.05] * 384

    with patch("app.pipeline.embed_worker.get_embed_engine") as mock_eng:
        mock_instance = mock_eng.return_value
        mock_instance.model_name = "multilingual-e5-small"
        mock_instance.embed.side_effect = lambda texts: [fake_vec for _ in texts]
        embed_document(doc_id)
        count_first = SessionLocal().query(Chunk).filter(Chunk.document_id == doc_id).count()
        embed_document(doc_id)
        count_second = SessionLocal().query(Chunk).filter(Chunk.document_id == doc_id).count()

    assert count_first == count_second
    assert count_first >= 2
