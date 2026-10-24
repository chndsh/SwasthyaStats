"""RAG /ask router."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db, set_rls_user_id
from app.security.auth import get_current_user
from app.models import User
from app.schemas import AskResponse
from app.rag.orchestrator import ask as orchestrator_ask

router = APIRouter(prefix="/api/v1", tags=["Ask"])


class AskRequest(BaseModel):
    question: str


@router.post(
    "/ask",
    response_model=AskResponse,
)
def ask_question(
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Answer patient questions based on confirmed records and hybrid search."""
    set_rls_user_id(db, current_user.id)
    result = orchestrator_ask(db, req.question, user_id=current_user.id)
    return AskResponse(answer=result.answer, citations=result.citations)
