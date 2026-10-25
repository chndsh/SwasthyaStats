from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import get_settings
from app.routers import auth as auth_router
from app.routers import settings as settings_router
from app.routers import documents as documents_router
from app.routers import observations as observations_router
from app.routers import charts as charts_router
from app.routers import ask as ask_router
from app.web import configure_web
from app.db import engine, Base
from app.models import Document
from app.routers.auth import bootstrap_admin
from sqlalchemy.orm import Session
from sqlalchemy import text as sa_text
import re
import datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database extensions are enabled
    with engine.connect() as conn:
        conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()

    # Ensure tables are created
    Base.metadata.create_all(bind=engine)

    # Seed admin if needed and clean orphaned docs
    with Session(engine) as session:
        bootstrap_admin(session)
        # Reset any orphaned documents interrupted during previous server shutdown
        session.query(Document).filter(
            Document.status.in_(["extracting", "normalizing", "ocr"])
        ).update({"status": "failed"}, synchronize_session=False)

        # Backfill missing canonical_test_id on observations using updated lab dictionary
        from app.services.documents import get_lab_dictionary
        from app.pipeline.normalize import _find_canonical_test_id
        from app.models import Observation
        lab_dict = get_lab_dictionary()
        unlinked = session.query(Observation).filter(Observation.canonical_test_id == None).all()
        for obs in unlinked:
            cid = _find_canonical_test_id(obs.test_name, lab_dict)
            if cid:
                obs.canonical_test_id = cid

        # Backfill missing doc_date on documents from ocr_lines or created_at
        docs_without_date = session.query(Document).filter(Document.doc_date == None).all()
        date_pat1 = re.compile(r"\b(20\d\d)[/-](\d{1,2})[/-](\d{1,2})\b")
        for doc in docs_without_date:
            extracted_date = None
            if doc.ocr_lines and isinstance(doc.ocr_lines, list):
                prev_label = ""
                for l in doc.ocr_lines:
                    txt = (l.get("text", "") if isinstance(l, dict) else str(l)).strip()
                    low = txt.lower()
                    m = date_pat1.search(txt)
                    if m:
                        try:
                            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                            if "collect" in low or "collect" in prev_label:
                                extracted_date = d
                                break
                            elif ("report" in low or "report" in prev_label) and not extracted_date:
                                extracted_date = d
                            elif "birth" not in prev_label and "dob" not in prev_label and not extracted_date:
                                extracted_date = d
                        except ValueError:
                            pass
                    prev_label = low
            if not extracted_date and doc.created_at:
                extracted_date = doc.created_at.date()
            if extracted_date:
                doc.doc_date = extracted_date

        session.commit()

        # Backfill missing collected_at on observations from parent document
        session.execute(sa_text("""
            UPDATE observations o
            SET collected_at = COALESCE(d.doc_date, d.created_at::date, CURRENT_DATE)
            FROM documents d
            WHERE o.document_id = d.id AND o.collected_at IS NULL;
        """))
        session.commit()
    yield


app = FastAPI(
    title="Health Records API",
    version="0.5.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# API Routers
app.include_router(auth_router.router)
app.include_router(settings_router.router)
app.include_router(documents_router.router)
app.include_router(observations_router.router)
app.include_router(charts_router.router)
app.include_router(ask_router.router)


@app.get("/health", tags=["Health"])
def healthcheck():
    return {"status": "ok", "version": "0.5.0"}


configure_web(app)
