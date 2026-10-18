from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import get_settings
from app.routers import settings as settings_router
from app.routers import documents as documents_router
from app.routers import observations as observations_router
from app.web import configure_web
from app.db import engine, Base
from app.models import Patient, Document
from sqlalchemy.orm import Session
from sqlalchemy import text as sa_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database extensions are enabled
    with engine.connect() as conn:
        conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()

    # Ensure tables are created
    Base.metadata.create_all(bind=engine)

    # Seed default patient if not exists
    with Session(engine) as session:
        default_patient = session.query(Patient).first()
        if not default_patient:
            session.add(Patient(id=1, name="Primary Patient"))
        # Reset any orphaned documents interrupted during previous server shutdown
        session.query(Document).filter(
            Document.status.in_(["extracting", "normalizing", "ocr"])
        ).update({"status": "failed"}, synchronize_session=False)
        session.commit()
    yield


app = FastAPI(
    title="Health Records API",
    version="0.4.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# API Routers
app.include_router(settings_router.router)
app.include_router(documents_router.router)
app.include_router(observations_router.router)
from app.routers import charts as charts_router
app.include_router(charts_router.router)
from app.routers import ask as ask_router
app.include_router(ask_router.router)




@app.get("/health", tags=["Health"])
def healthcheck():
    return {"status": "ok", "version": "0.4.0"}


# Web & Static files configuration
configure_web(app)
