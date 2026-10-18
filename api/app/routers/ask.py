"""RAG /ask router."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.security.auth import verify_api_key
from app.schemas import AskResponse
from app.rag.orchestrator import ask as orchestrator_ask

router = APIRouter(prefix="/api/v1", tags=["Ask"])


class AskRequest(BaseModel):
    question: str


@router.post(
    "/ask",
    response_model=AskResponse,
    dependencies=[Depends(verify_api_key)],
)
def ask_question(req: AskRequest, db: Session = Depends(get_db)):
    """Answer patient questions based on confirmed records and hybrid search."""
    result = orchestrator_ask(db, req.question)
    return AskResponse(answer=result.answer, citations=result.citations)
