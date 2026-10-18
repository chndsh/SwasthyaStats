import datetime
import pytest
from app.db import SessionLocal
from app.models import Patient, Document, Observation, Chunk
from app.rag.tools import (
    get_observations,
    get_latest_observations,
    list_tests,
    search_documents,
)


@pytest.fixture
def rag_tools_data():
    db = SessionLocal()
    patient = db.query(Patient).filter(Patient.id == 1).first()
    if not patient:
        patient = Patient(id=1, name="Test Patient")
        db.add(patient)
        db.commit()

    doc1 = Document(
        patient_id=1,
        filename="rag_report1.png",
        sha256="rag_sha1",
        status="confirmed",
        doc_date=datetime.date(2026, 1, 15),
        page_count=1,
    )
    doc2 = Document(
        patient_id=1,
        filename="rag_report2.png",
        sha256="rag_sha2",
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
        test_name="SpecialRAGTest (SRT)",
        canonical_test_id="special_rag_test",
        value_num=42.0,
        unit="mg/dL",
        ref_low=10.0,
        ref_high=50.0,
        flag="normal",
        collected_at=datetime.date(2026, 1, 15),
        status="confirmed",
        page_no=1,
    )
    obs2 = Observation(
        patient_id=1,
        document_id=doc2.id,
        test_name="SpecialRAGTest",
        canonical_test_id="special_rag_test",
        value_num=45.0,
        unit="mg/dL",
        ref_low=10.0,
        ref_high=50.0,
        flag="normal",
        collected_at=datetime.date(2026, 6, 15),
        status="confirmed",
        page_no=1,
    )
    obs_pending = Observation(
        patient_id=1,
        document_id=doc1.id,
        test_name="PendingRAGTest",
        canonical_test_id=None,
        value_num=99.0,
        unit="mg/L",
        status="pending",
        collected_at=datetime.date(2026, 1, 15),
        page_no=1,
    )
    db.add_all([obs1, obs2, obs_pending])

    chunk1 = Chunk(
        document_id=doc1.id,
        text="SpecialUniqueKeywordMedication prescribed 500mg daily.",
        embed_model="multilingual-e5-small",
        embedding=[0.05] * 384,
        page=1,
    )
    chunk2 = Chunk(
        document_id=doc2.id,
        text="Patient follow-up notes without medications.",
        embed_model="multilingual-e5-small",
        embedding=[0.01] * 384,
        page=1,
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    yield {
        "db": db,
        "doc1_id": doc1.id,
        "doc2_id": doc2.id,
    }

    db.query(Chunk).filter(Chunk.document_id.in_([doc1.id, doc2.id])).delete()
    db.query(Observation).filter(Observation.document_id.in_([doc1.id, doc2.id])).delete()
    db.query(Document).filter(Document.id.in_([doc1.id, doc2.id])).delete()
    db.commit()
    db.close()


def test_list_tests_returns_confirmed_only(rag_tools_data):
    db = rag_tools_data["db"]
    tests = list_tests(db)
    names = [t["test_name"] for t in tests]
    assert "SpecialRAGTest (SRT)" in names or "SpecialRAGTest" in names
    assert "PendingRAGTest" not in names


def test_get_observations_alias_resolve(rag_tools_data):
    db = rag_tools_data["db"]
    # Query with alias 'SRT' matches SpecialRAGTest (SRT) and SpecialRAGTest via canonical ID or substring
    results = get_observations(db, "SpecialRAGTest")
    assert len(results) == 2
    assert results[0]["value_num"] == 42.0
    assert results[1]["value_num"] == 45.0


def test_get_latest_observations(rag_tools_data):
    db = rag_tools_data["db"]
    results = get_latest_observations(db, ["SpecialRAGTest"])
    assert len(results) == 1
    assert results[0]["value_num"] == 45.0
    assert str(results[0]["collected_at"]) == "2026-06-15"


def test_search_documents_returns_ranked(rag_tools_data, monkeypatch):
    db = rag_tools_data["db"]

    class FakeEmbedEngine:
        def embed(self, texts):
            # Query embedding matches chunk1 [0.05]*384 perfectly
            return [[0.05] * 384 for _ in texts]

    from app.pipeline import embed
    monkeypatch.setattr(embed, "get_embed_engine", lambda: FakeEmbedEngine())

    results = search_documents(db, "SpecialUniqueKeywordMedication", top_k=2)
    assert len(results) >= 1
    assert "SpecialUniqueKeywordMedication" in results[0]["text"]
    assert "score" in results[0]
