import pytest
import datetime
from app.db import SessionLocal
from app.models import Patient, Document, Observation, Chunk
from app.llm.client import LlmResponse
from app.rag.orchestrator import ask, AskResult


@pytest.fixture
def rag_orchestrator_data():
    db = SessionLocal()
    patient = db.query(Patient).filter(Patient.id == 1).first()
    if not patient:
        patient = Patient(id=1, name="Test Patient")
        db.add(patient)
        db.commit()

    doc = Document(
        patient_id=1,
        filename="orch_report.png",
        sha256="orch_sha",
        status="confirmed",
        doc_date=datetime.date(2026, 3, 14),
        page_count=1,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    obs = Observation(
        patient_id=1,
        document_id=doc.id,
        test_name="HbA1c",
        canonical_test_id="hba1c",
        value_num=7.2,
        unit="%",
        ref_low=4.0,
        ref_high=5.6,
        flag="high",
        collected_at=datetime.date(2026, 3, 14),
        status="confirmed",
        page_no=1,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    yield {"db": db, "obs_id": obs.id, "doc_id": doc.id}

    db.query(Observation).filter(Observation.document_id == doc.id).delete()
    db.query(Document).filter(Document.id == doc.id).delete()
    db.commit()
    db.close()


def test_ask_native_tools_happy_path(rag_orchestrator_data, monkeypatch):
    data = rag_orchestrator_data
    db = data["db"]
    obs_id = data["obs_id"]

    call_count = 0

    def fake_chat(self, messages, *, purpose, json_schema=None, tools=None, **kwargs):
        nonlocal call_count
        call_count += 1
        if purpose == "route":
            return LlmResponse(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_observations",
                        "arguments": '{"test": "HbA1c"}',
                    },
                }],
            )
        elif purpose == "answer":
            return LlmResponse(
                content=f"Your latest HbA1c is 7.2% [obs:{obs_id}].",
            )
        raise ValueError(f"Unexpected purpose: {purpose}")

    from app.llm.client import OpenAICompatClient
    monkeypatch.setattr(OpenAICompatClient, "chat", fake_chat)

    result = ask(db, "What is my HbA1c?")
    assert f"[obs:{obs_id}]" in result.answer
    assert len(result.citations) == 1
    assert result.citations[0].type == "obs"
    assert result.citations[0].id == obs_id


def test_ask_router_fallback(rag_orchestrator_data, monkeypatch):
    data = rag_orchestrator_data
    db = data["db"]

    from app.services.settings import SettingsService
    orig_get_read = SettingsService.get_read_settings

    class FakeSettings:
        llm_supports_tools = False

    monkeypatch.setattr(SettingsService, "get_read_settings", lambda self: FakeSettings())

    def fake_chat(self, messages, *, purpose, json_schema=None, tools=None, **kwargs):
        if purpose == "route":
            return LlmResponse(
                content='{"tool": "list_tests", "args": {}}',
            )
        elif purpose == "answer":
            return LlmResponse(
                content="I couldn't find that in your records.",
            )
        raise ValueError(f"Unexpected purpose: {purpose}")

    from app.llm.client import OpenAICompatClient
    monkeypatch.setattr(OpenAICompatClient, "chat", fake_chat)

    result = ask(db, "What was my Ferritin level?")
    assert "I couldn't find that in your records" in result.answer
    assert len(result.citations) == 0


def test_ask_unanswerable(rag_orchestrator_data, monkeypatch):
    data = rag_orchestrator_data
    db = data["db"]

    def fake_chat(self, messages, *, purpose, json_schema=None, tools=None, **kwargs):
        if purpose == "route":
            return LlmResponse(content="", tool_calls=[])
        elif purpose == "answer":
            return LlmResponse(content="I couldn't find that in your records.")
        raise ValueError(f"Unexpected purpose: {purpose}")

    from app.llm.client import OpenAICompatClient
    monkeypatch.setattr(OpenAICompatClient, "chat", fake_chat)

    result = ask(db, "What was my COVID antibody titer?")
    assert "I couldn't find that in your records" in result.answer
    assert result.citations == []


def test_ask_max_tool_calls_enforced(rag_orchestrator_data, monkeypatch):
    data = rag_orchestrator_data
    db = data["db"]

    route_rounds = 0

    def fake_chat(self, messages, *, purpose, json_schema=None, tools=None, **kwargs):
        nonlocal route_rounds
        if purpose == "route":
            route_rounds += 1
            return LlmResponse(
                content="",
                tool_calls=[{
                    "id": f"call_{route_rounds}",
                    "type": "function",
                    "function": {"name": "list_tests", "arguments": "{}"},
                }],
            )
        elif purpose == "answer":
            return LlmResponse(content="Answer after tool loop.")
        raise ValueError(f"Unexpected purpose: {purpose}")

    from app.llm.client import OpenAICompatClient
    monkeypatch.setattr(OpenAICompatClient, "chat", fake_chat)

    result = ask(db, "Infinite loop query?")
    assert route_rounds == 3  # Stopped after 3 rounds
    assert result.answer == "Answer after tool loop."
