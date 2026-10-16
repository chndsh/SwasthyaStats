import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Response
from sqlalchemy.orm import Session
from app.db import get_db
from app.security.auth import verify_api_key
from app.models import Document, DocumentPage, Extraction, Observation
from app.schemas import DocumentRead, DocumentUploadResponse, ExtractionRead, ObservationRead
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


@router.get(
    "/{document_id}/extraction",
    response_model=ExtractionRead,
    dependencies=[Depends(verify_api_key)],
)
def get_document_extraction(document_id: int, db: Session = Depends(get_db)):
    """Retrieves document's extracted observations, OCR lines, and confidence scores."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    ext = (
        db.query(Extraction)
        .filter(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc())
        .first()
    )
    conf_map = ext.field_confidence if ext and ext.field_confidence else {}

    raw_obs = db.query(Observation).filter(Observation.document_id == document_id).all()
    obs_list = []
    for o in raw_obs:
        obs_dict = {
            "id": o.id,
            "test_name": o.test_name,
            "canonical_test_id": o.canonical_test_id,
            "value_num": o.value_num,
            "value_text": o.value_text,
            "unit": o.unit,
            "ref_low": o.ref_low,
            "ref_high": o.ref_high,
            "flag": o.flag,
            "collected_at": o.collected_at,
            "page_no": o.page_no,
            "source_line_ids": o.source_line_ids,
            "status": o.status,
            "confidence": conf_map.get(str(o.id)),
        }
        obs_list.append(ObservationRead(**obs_dict))

    return ExtractionRead(
        document_id=doc.id,
        status=doc.status,
        observations=obs_list,
        ocr_lines=doc.ocr_lines or [],
    )


@router.post(
    "/{document_id}/confirm",
    dependencies=[Depends(verify_api_key)],
)
def confirm_document(document_id: int, db: Session = Depends(get_db)):
    """Confirms all pending observations for a document and marks document as confirmed."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    updated = (
        db.query(Observation)
        .filter(Observation.document_id == document_id, Observation.status == "pending")
        .update({"status": "confirmed"})
    )
    doc.status = "confirmed"
    db.commit()

    return {"confirmed": updated, "document_id": doc.id, "status": doc.status}


@router.post(
    "/{document_id}/retry",
    dependencies=[Depends(verify_api_key)],
)
def retry_document_extraction(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Re-enqueues extraction for documents stalled in rate_limited or failed status."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.status not in ("rate_limited", "failed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot retry document in status '{doc.status}'",
        )

    doc.status = "extracting"
    db.commit()

    # Define background worker wrapper with its own DB session
    def _retry_worker(d_id: int):
        from app.db import SessionLocal
        from app.services.documents import _run_extraction_stage
        s = SessionLocal()
        try:
            _run_extraction_stage(d_id, s)
        finally:
            s.close()

    background_tasks.add_task(_retry_worker, doc.id)
    return {"id": doc.id, "status": doc.status}
