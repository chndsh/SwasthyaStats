"""Background worker for embedding confirmed document observations and OCR text."""
import logging
from typing import List, Tuple
from app.db import SessionLocal
from app.models import Document, Observation, Chunk
from app.pipeline.embed import get_embed_engine, observation_summary

logger = logging.getLogger(__name__)


def embed_document(document_id: int) -> None:
    """Embeds all confirmed observations and OCR text for a document into chunks.

    Runs as a background task. Idempotent: deletes any existing chunks for document_id first.
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.warning(f"embed_document: Document {document_id} not found")
            return

        confirmed_obs = (
            db.query(Observation)
            .filter(Observation.document_id == document_id, Observation.status == "confirmed")
            .all()
        )

        # Build chunks: (text, page)
        chunk_items: List[Tuple[str, int]] = []

        # 1. Per-observation summary chunks
        for obs in confirmed_obs:
            summary = observation_summary(obs)
            chunk_items.append((summary, obs.page_no or 1))

        # 2. Document OCR text summary chunk
        if doc.ocr_text and doc.ocr_text.strip():
            page_text = doc.ocr_text.strip()[:2000]
            chunk_items.append((page_text, 1))

        if not chunk_items:
            logger.info(f"embed_document: No observations or OCR text to embed for document {document_id}")
            return

        engine = get_embed_engine()
        texts = [item[0] for item in chunk_items]
        vectors = engine.embed(texts)

        # Idempotent: delete existing chunks for this document
        db.query(Chunk).filter(Chunk.document_id == document_id).delete()

        # Insert new chunk rows
        model_name = getattr(engine, "model_name", "multilingual-e5-small")
        for (text, page), vec in zip(chunk_items, vectors):
            chunk = Chunk(
                user_id=doc.user_id,
                document_id=doc.id,
                text=text,
                embed_model=model_name,
                embedding=vec,
                page=page,
            )
            db.add(chunk)

        db.commit()
        logger.info(f"Embedded {len(chunk_items)} chunks for document {document_id} with {model_name}")
    except Exception as e:
        db.rollback()
        logger.exception(f"Error embedding document {document_id}: {e}")
    finally:
        db.close()
