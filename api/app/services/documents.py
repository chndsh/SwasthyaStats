import hashlib
import logging
import os
from typing import List, Tuple, Optional
import cv2
import numpy as np
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import SessionLocal
from app.models import Document, DocumentPage, Patient
from app.pipeline.normalize_pages import process_upload_to_pages, NormalizedPage
from app.pipeline.ocr.easyocr_engine import EasyOcrEngine

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 12 * 1024 * 1024  # 12 MB limit
MAX_PAGES = 10

_ocr_engine_instance: Optional[EasyOcrEngine] = None


def get_ocr_engine() -> EasyOcrEngine:
    global _ocr_engine_instance
    if _ocr_engine_instance is None:
        _ocr_engine_instance = EasyOcrEngine(languages=["en"], model_storage_directory="/root/.EasyOCR")
    return _ocr_engine_instance


def validate_and_create_document(
    files: List[UploadFile],
    db: Session,
    patient_id: int = 1,
) -> Tuple[Document, List[Tuple[str, bytes]]]:
    """Validates uploaded files, computes SHA256, and creates queued Document record."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")

    # Ensure patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        patient = Patient(id=patient_id, name="Primary Patient")
        db.add(patient)
        db.commit()

    file_payloads: List[Tuple[str, bytes]] = []
    total_bytes = 0
    hasher = hashlib.sha256()

    for f in files:
        content = f.file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File {f.filename} is empty")
        total_bytes += len(content)
        if total_bytes > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total upload size exceeds 12 MB limit",
            )
        hasher.update(content)
        file_payloads.append((f.filename or "upload.png", content))

    # Preliminary validation check (first file)
    first_name, first_bytes = file_payloads[0]
    is_pdf = first_name.lower().endswith(".pdf") or first_bytes.startswith(b"%PDF")
    if is_pdf and not first_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Corrupted or invalid PDF header")

    sha256_hash = hasher.hexdigest()
    primary_filename = file_payloads[0][0] if len(file_payloads) == 1 else f"{file_payloads[0][0]} (+{len(file_payloads)-1} files)"

    doc = Document(
        patient_id=patient_id,
        filename=primary_filename,
        sha256=sha256_hash,
        status="queued",
        page_count=len(file_payloads),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return doc, file_payloads


def process_document_background(doc_id: int, file_payloads: List[Tuple[str, bytes]]) -> None:
    """Asynchronous background worker executing page normalization and EasyOCR."""
    settings = get_settings()
    db = SessionLocal()

    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error(f"Document {doc_id} not found in background processing")
            return

        # 1. Status: Normalizing
        doc.status = "normalizing"
        db.commit()

        all_normalized_pages: List[NormalizedPage] = []
        for filename, content in file_payloads:
            try:
                pages = process_upload_to_pages(content, filename)
                all_normalized_pages.extend(pages)
            except Exception as e:
                logger.exception(f"Normalization failed for document {doc_id}: {e}")
                doc.status = "failed"
                db.commit()
                return

        if len(all_normalized_pages) > MAX_PAGES:
            logger.error(f"Document {doc_id} exceeds {MAX_PAGES} pages")
            doc.status = "failed"
            db.commit()
            return

        # Save normalized pages to disk and create DocumentPage records
        doc_dir = os.path.join(settings.STORAGE_PATH, "documents", str(doc_id), "pages")
        os.makedirs(doc_dir, exist_ok=True)

        for idx, page in enumerate(all_normalized_pages, start=1):
            page.page_no = idx
            page_path = os.path.join(doc_dir, f"{idx}.png")
            with open(page_path, "wb") as pf:
                pf.write(page.image_bytes)

            page_record = DocumentPage(
                document_id=doc_id,
                page_no=idx,
                width=page.width,
                height=page.height,
                image_path=page_path,
            )
            db.add(page_record)

        doc.page_count = len(all_normalized_pages)
        db.commit()

        # 2. Status: OCR
        doc.status = "ocr"
        db.commit()

        engine = get_ocr_engine()
        all_ocr_lines = []
        page_texts = []

        for page in all_normalized_pages:
            nparr = np.frombuffer(page.image_bytes, np.uint8)
            img_np = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            page_text, page_lines = engine.run(img_np, page_no=page.page_no)
            all_ocr_lines.extend(page_lines)
            if page_text:
                page_texts.append(page_text)

        doc.ocr_text = "\n\n".join(page_texts)
        doc.ocr_lines = all_ocr_lines
        doc.status = "needs_review"
        db.commit()
        logger.info(f"Document {doc_id} processing completed successfully")

    except Exception as e:
        logger.exception(f"Error during background processing of document {doc_id}: {e}")
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
