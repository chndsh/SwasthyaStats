import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Response, Query
from sqlalchemy.orm import Session
from app.db import get_db, set_rls_user_id
from app.security.auth import get_current_user
import shutil
from app.models import Document, DocumentPage, Extraction, Observation, Chunk, User
from app.schemas import DocumentRead, DocumentUploadResponse, ExtractionRead, ObservationRead, ObservationCreate
from app.services.documents import validate_and_create_document, process_document_background, get_lab_dictionary
from app.pipeline.normalize import _find_canonical_test_id

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads 1..n page images or 1 PDF document and enqueues normalization and OCR."""
    set_rls_user_id(db, current_user.id)
    doc, file_payloads = validate_and_create_document(files=files, db=db, user_id=current_user.id)
    background_tasks.add_task(process_document_background, doc.id, file_payloads, current_user.id)
    return DocumentUploadResponse(id=doc.id, status=doc.status, page_count=doc.page_count)


@router.get(
    "",
    response_model=List[DocumentRead],
)
def list_documents(
    sort_by: Optional[str] = Query("date_desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all documents for the current user, ordered by requested sort option."""
    set_rls_user_id(db, current_user.id)
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if sort_by == "doctor_asc":
        query = query.order_by(Document.doctor_name.asc().nullslast(), Document.created_at.desc())
    elif sort_by == "doctor_desc":
        query = query.order_by(Document.doctor_name.desc().nullslast(), Document.created_at.desc())
    elif sort_by == "date_asc":
        query = query.order_by(Document.created_at.asc())
    elif sort_by == "filename":
        query = query.order_by(Document.filename.asc())
    else:  # date_desc default
        query = query.order_by(Document.created_at.desc())
    return query.all()


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves document details and pages."""
    set_rls_user_id(db, current_user.id)
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.get(
    "/{document_id}/pages/{page_no}.png",
)
def get_document_page_image(
    document_id: int,
    page_no: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Streams the normalized page image used for OCR and displayed in review/document view."""
    set_rls_user_id(db, current_user.id)
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

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
)
def get_document_extraction(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves document's extracted observations, OCR lines, and confidence scores."""
    set_rls_user_id(db, current_user.id)
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    ext = (
        db.query(Extraction)
        .filter(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc())
        .first()
    )
    conf_map = ext.field_confidence if ext and ext.field_confidence else {}

    raw_obs = db.query(Observation).filter(Observation.document_id == document_id, Observation.user_id == current_user.id).all()
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
        page_count=doc.page_count or 1,
        observations=obs_list,
        ocr_lines=doc.ocr_lines or [],
    )


@router.post(
    "/{document_id}/observations",
    response_model=ObservationRead,
    status_code=status.HTTP_201_CREATED,
)
def add_manual_observation(
    document_id: int,
    obs_in: ObservationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually adds a missed observation to a document before confirmation."""
    set_rls_user_id(db, current_user.id)
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add observations to a confirmed document",
        )

    lab_dict = get_lab_dictionary()
    canon_id = _find_canonical_test_id(obs_in.test_name, lab_dict)

    obs = Observation(
        user_id=current_user.id,
        document_id=doc.id,
        test_name=obs_in.test_name,
        canonical_test_id=canon_id,
        value_num=obs_in.value_num,
        value_text=obs_in.value_text,
        unit=obs_in.unit,
        ref_low=obs_in.ref_low,
        ref_high=obs_in.ref_high,
        flag=obs_in.flag,
        page_no=obs_in.page_no,
        collected_at=obs_in.collected_at or doc.doc_date,
        source_line_ids=[],
        status="pending",
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    # Record confidence as 1.0 (human verified/entered) in extraction
    ext = (
        db.query(Extraction)
        .filter(Extraction.document_id == document_id)
        .order_by(Extraction.created_at.desc())
        .first()
    )
    if ext:
        field_conf = dict(ext.field_confidence or {})
        field_conf[str(obs.id)] = 1.0
        ext.field_confidence = field_conf
        db.commit()

    return ObservationRead(
        id=obs.id,
        test_name=obs.test_name,
        canonical_test_id=obs.canonical_test_id,
        value_num=obs.value_num,
        value_text=obs.value_text,
        unit=obs.unit,
        ref_low=obs.ref_low,
        ref_high=obs.ref_high,
        flag=obs.flag,
        collected_at=obs.collected_at,
        page_no=obs.page_no,
        source_line_ids=obs.source_line_ids,
        status=obs.status,
        confidence=1.0,
    )


@router.post(
    "/{document_id}/confirm",
)
def confirm_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirms all pending observations for a document and marks document as confirmed."""
    set_rls_user_id(db, current_user.id)
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    updated = (
        db.query(Observation)
        .filter(Observation.document_id == document_id, Observation.status == "pending")
        .update({"status": "confirmed"})
    )
    doc.status = "confirmed"
    db.commit()

    from app.pipeline.embed_worker import embed_document
    background_tasks.add_task(embed_document, doc.id)

    return {"confirmed": updated, "document_id": doc.id, "status": doc.status}


@router.post(
    "/{document_id}/retry",
)
def retry_document_extraction(
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-enqueues extraction for documents stalled in rate_limited or failed status."""
    set_rls_user_id(db, current_user.id)
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.status not in ("rate_limited", "failed", "extracting"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot retry document in status '{doc.status}'",
        )

    doc.status = "extracting"
    db.commit()

    # Define background worker wrapper with its own DB session
    def _retry_worker(d_id: int, u_id: int):
        from app.db import SessionLocal
        from app.services.documents import _run_extraction_stage
        s = SessionLocal()
        try:
            _run_extraction_stage(d_id, s)
        finally:
            s.close()

    background_tasks.add_task(_retry_worker, doc.id, current_user.id)
    return {"id": doc.id, "status": doc.status}


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes a document and all associated records and files."""
    set_rls_user_id(db, current_user.id)
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete child records in dependency order
    db.query(Chunk).filter(Chunk.document_id == document_id).delete(synchronize_session=False)
    db.query(Observation).filter(Observation.document_id == document_id).delete(synchronize_session=False)
    db.query(Extraction).filter(Extraction.document_id == document_id).delete(synchronize_session=False)
    db.query(DocumentPage).filter(DocumentPage.document_id == document_id).delete(synchronize_session=False)
    db.delete(doc)
    db.commit()

    # Remove files from disk
    from app.config import get_settings
    doc_dir = os.path.join(get_settings().STORAGE_PATH, "documents", str(document_id))
    if os.path.isdir(doc_dir):
        shutil.rmtree(doc_dir, ignore_errors=True)
