"""RAG /ask router."""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db, set_rls_user_id
from app.security.auth import get_current_user
from app.models import User
from app.schemas import AskResponse
from app.rag.orchestrator import ask as orchestrator_ask

logger = logging.getLogger(__name__)

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
    try:
        result = orchestrator_ask(db, req.question, user_id=current_user.id)
        return AskResponse(answer=result.answer, citations=result.citations)
    except Exception as e:
        logger.exception(f"Error in ask_question: {e}")
        err_str = str(e)
        if "rate" in err_str.lower() or "limit" in err_str.lower() or "exhausted" in err_str.lower():
            return AskResponse(
                answer="The AI service is currently busy or rate-limited. Please wait a moment and try asking again, or check your API key in Settings.",
                citations=[],
            )
        return AskResponse(
            answer="Unable to process your question at this time. Please check your LLM provider settings and API key in Settings.",
            citations=[],
        )
