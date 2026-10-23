import hashlib
import io
import logging
import os
from typing import List, Tuple, Optional
import cv2
import numpy as np
from fastapi import UploadFile, HTTPException, status
from PIL import Image
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import SessionLocal
import json
from app.models import Document, DocumentPage, User, Extraction, Observation
from app.pipeline.normalize_pages import process_upload_to_pages, NormalizedPage
from app.pipeline.ocr.easyocr_engine import EasyOcrEngine
from app.pipeline.redact import redact_text
from app.pipeline.extract import extract_page, ExtractionFailed, LabReportRaw
from app.pipeline.normalize import score_observations, ScoredObservation
from app.llm.client import OpenAICompatClient
from app.services.settings import SettingsService

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
    user_id: int = 1,
) -> Tuple[Document, List[Tuple[str, bytes]]]:
    """Validates uploaded files, computes SHA256, and creates queued Document record."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")

    # I-1: Reject over-limit file count before touching the DB
    if len(files) > MAX_PAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files: upload limit is {MAX_PAGES} images per request",
        )

    # Ensure user exists or fallback to first available user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = db.query(User).first()
        if user:
            user_id = user.id

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

    # I-2: Validate file formats synchronously before creating DB record
    first_name, first_bytes = file_payloads[0]
    is_pdf = first_name.lower().endswith(".pdf") or first_bytes.startswith(b"%PDF")
    if is_pdf:
        if not first_bytes.startswith(b"%PDF"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Corrupted or invalid PDF header")
    else:
        # Validate every image file with PIL before committing to DB
        for fname, fbytes in file_payloads:
            try:
                img = Image.open(io.BytesIO(fbytes))
                img.verify()  # raises on corrupt data; file must be re-opened for further use
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File '{fname}' is not a valid image",
                )

    sha256_hash = hasher.hexdigest()
    primary_filename = file_payloads[0][0] if len(file_payloads) == 1 else f"{file_payloads[0][0]} (+{len(file_payloads)-1} files)"

    doc = Document(
        user_id=user_id,
        filename=primary_filename,
        sha256=sha256_hash,
        status="queued",
        page_count=len(file_payloads),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return doc, file_payloads


def process_document_background(doc_id: int, file_payloads: List[Tuple[str, bytes]], user_id: Optional[int] = None) -> None:
    """Asynchronous background worker executing page normalization and EasyOCR."""
    settings = get_settings()
    db = SessionLocal()
    if user_id:
        from app.db import set_rls_user_id
        set_rls_user_id(db, user_id)

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
        db.commit()

        # 3. Status: Extraction & Normalization
        _run_extraction_stage(doc_id, db)
        logger.info(f"Document {doc_id} processing completed successfully")

    except Exception as e:
        logger.exception(f"Error during background processing of document {doc_id}: {e}")
        try:
            db.rollback()
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc and doc.status != "rate_limited":
                doc.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


_lab_dictionary_cache = None


def get_lab_dictionary() -> dict:
    global _lab_dictionary_cache
    if _lab_dictionary_cache is None:
        paths = [
            os.path.join(os.path.dirname(__file__), "..", "data", "lab_dictionary.json"),
            os.path.join(os.path.dirname(__file__), "data", "lab_dictionary.json"),
            "/app/app/data/lab_dictionary.json",
            "/app/data/lab_dictionary.json",
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _lab_dictionary_cache = json.load(f)
                        break
                except Exception as e:
                    logger.warning(f"Error loading lab dictionary from {p}: {e}")
        if _lab_dictionary_cache is None:
            _lab_dictionary_cache = {}
    return _lab_dictionary_cache


def _run_extraction_stage(doc_id: int, db: Session) -> None:
    """Executes PII redaction, structured LLM extraction per page, grounding check,

    and dictionary normalization. Pauses on rate limits with status='rate_limited'.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return

    doc.status = "extracting"
    db.commit()

    if not doc.ocr_lines and not doc.ocr_text:
        doc.status = "needs_review"
        db.commit()
        return

    settings_service = SettingsService(db)
    app_settings = settings_service.get_read_settings()
    model_name = app_settings.llm_model or "default"
    prompt_version = "v1"

    client = OpenAICompatClient(db)
    patient_name = doc.user.display_name if (doc.user and doc.user.display_name) else None
    lab_dict = get_lab_dictionary()

    # Clear previous pending observations for this document (e.g. on re-run / retry)
    db.query(Observation).filter(
        Observation.document_id == doc_id,
        Observation.status == "pending",
    ).delete()

    total_pages = doc.page_count or 1
    last_report_date = None
    last_doctor_name = None
    confidence_map = {}

    for page_no in range(1, total_pages + 1):
        if page_no > 1:
            import time
            time.sleep(5.0)  # Pacing between pages to avoid Groq ITPM rate limit

        page_lines = [l for l in doc.ocr_lines if l.get("page") == page_no] if doc.ocr_lines else []
        if not page_lines and total_pages == 1 and doc.ocr_lines:
            page_lines = doc.ocr_lines

        # Group lines by row_id to present structured table rows with exact line IDs
        rows_by_id = {}
        for l in page_lines:
            rid = l.get("row_id", 0)
            rows_by_id.setdefault(rid, []).append(l)

        if len(rows_by_id) > 1 or (rows_by_id and 0 not in rows_by_id):
            row_strings = []
            for rid in sorted(rows_by_id.keys()):
                r_lines = rows_by_id[rid]
                cells_text = " | ".join(l.get("text", "").strip() for l in r_lines if l.get("text", "").strip())
                r_ids = [l["id"] for l in r_lines if "id" in l]
                if cells_text:
                    row_strings.append(f"[Line IDs: {r_ids}]: {cells_text}")
            page_text = "\n".join(row_strings)
        else:
            page_text = "\n".join([l.get("text", "") for l in page_lines])

        if not page_text and doc.ocr_text and total_pages == 1:
            page_text = doc.ocr_text

        redacted = redact_text(page_text, patient_name)
        line_ids = [l["id"] for l in page_lines if "id" in l]

        input_hash = hashlib.sha256(
            f"{redacted}:{prompt_version}:{model_name}".encode()
        ).hexdigest()

        # Cache lookup
        cached_ext = (
            db.query(Extraction)
            .filter(Extraction.document_id == doc_id, Extraction.input_hash == input_hash)
            .first()
        )

        if cached_ext and cached_ext.raw_json:
            try:
                report = LabReportRaw.model_validate(cached_ext.raw_json)
            except Exception:
                report = None
        else:
            report = None

        if report is None:
            try:
                report = extract_page(
                    redacted,
                    line_ids,
                    client=client,
                    prompt_version=prompt_version,
                )
            except (RuntimeError, ValueError) as rerr:
                logger.warning(f"Extraction rate limited or keys exhausted for doc {doc_id}: {rerr}")
                db.rollback()
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc:
                    doc.status = "rate_limited"
                    db.commit()
                return
            except ExtractionFailed as e:
                logger.error(f"Extraction failed for doc {doc_id}: {e}")
                db.rollback()
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc:
                    doc.status = "failed"
                    db.commit()
                return
            except Exception as ex:
                err_msg = str(ex).lower()
                db.rollback()
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc:
                    if "rate" in err_msg or "exhausted" in err_msg or "429" in err_msg:
                        doc.status = "rate_limited"
                    else:
                        logger.exception(f"Unexpected extraction error for doc {doc_id}: {ex}")
                        doc.status = "failed"
                    db.commit()
                return

        if report.report_date:
            last_report_date = report.report_date
        if report.doctor_name:
            last_doctor_name = report.doctor_name

        scored = score_observations(report.observations, page_lines, lab_dict)

        for s in scored:
            obs_rec = Observation(
                user_id=doc.user_id,
                document_id=doc.id,
                test_name=s.obs.test_name,
                canonical_test_id=s.canonical_test_id,
                value_num=s.obs.value,
                value_text=s.obs.value_text,
                unit=s.normalized_unit,
                ref_low=s.normalized_ref_low,
                ref_high=s.normalized_ref_high,
                flag=s.obs.flag,
                collected_at=report.report_date or doc.doc_date,
                page_no=page_no,
                source_line_ids=s.obs.line_ids,
                status="pending",
            )
            db.add(obs_rec)
            db.flush()
            confidence_map[str(obs_rec.id)] = s.confidence

        if not cached_ext:
            extraction = Extraction(
                document_id=doc.id,
                model=model_name,
                prompt_version=prompt_version,
                structured_mode=app_settings.llm_structured_mode,
                input_hash=input_hash,
                raw_json=report.model_dump(mode="json"),
                field_confidence=confidence_map,
            )
            db.add(extraction)
        db.commit()

    if last_report_date and not doc.doc_date:
        doc.doc_date = last_report_date
    if last_doctor_name and not doc.doctor_name:
        doc.doctor_name = last_doctor_name

    doc.status = "needs_review"
    db.commit()
    logger.info(f"Document {doc_id} extraction completed successfully")
