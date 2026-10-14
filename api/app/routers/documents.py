import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Response
from sqlalchemy.orm import Session
from app.db import get_db
from app.security.auth import verify_api_key
from app.models import Document, DocumentPage
from app.schemas import DocumentRead, DocumentUploadResponse
from app.services.documents import validate_and_create_document, process_document_background

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_key)],
)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Uploads 1..n page images or 1 PDF document and enqueues normalization and OCR."""
    doc, file_payloads = validate_and_create_document(files=files, db=db)
    background_tasks.add_task(process_document_background, doc.id, file_payloads)
    return DocumentUploadResponse(id=doc.id, status=doc.status, page_count=doc.page_count)


@router.get(
    "",
    response_model=List[DocumentRead],
    dependencies=[Depends(verify_api_key)],
)
def list_documents(db: Session = Depends(get_db)):
    """Lists all documents for the primary patient, ordered by creation date descending."""
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    dependencies=[Depends(verify_api_key)],
)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Retrieves document details and pages."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.get(
    "/{document_id}/pages/{page_no}.png",
    dependencies=[Depends(verify_api_key)],
)
def get_document_page_image(
    document_id: int,
    page_no: int,
    db: Session = Depends(get_db),
):
    """Streams the normalized page image used for OCR and displayed in review/document view."""
    page = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document_id, DocumentPage.page_no == page_no)
        .first()
    )
    if not page or not page.image_path or not os.path.exists(page.image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page image not found")

    with open(page.image_path, "rb") as f:
        content = f.read()

    return Response(content=content, media_type="image/png")
