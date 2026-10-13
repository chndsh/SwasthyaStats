import httpx
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.security.auth import verify_api_key
from app.services.settings import SettingsService
from app.schemas import AppSettingsRead, AppSettingsUpdate, TestLlmResponse, UsageStats
from app.llm.probe import run_probe_ladder
from app.models import LlmCall, Document

router = APIRouter(prefix="/api/v1", tags=["Settings"], dependencies=[Depends(verify_api_key)])


@router.get("/settings", response_model=AppSettingsRead)
def get_settings_endpoint(db: Session = Depends(get_db)):
    service = SettingsService(db)
    return service.get_read_settings()


@router.put("/settings", response_model=AppSettingsRead)
def update_settings_endpoint(update: AppSettingsUpdate, db: Session = Depends(get_db)):
    service = SettingsService(db)
    return service.update_settings(update)


@router.get("/settings/models", response_model=List[str])
def list_models_endpoint(db: Session = Depends(get_db)):
    service = SettingsService(db)
    settings = service.get_read_settings()
    keys = service.get_decrypted_keys()

    if not keys:
        return []

    base_url = settings.llm_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {keys[0]['key']}"}
    if settings.llm_extra_headers:
        headers.update(settings.llm_extra_headers)

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url}/models", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            models_data = data.get("data", [])
            model_ids = [m.get("id") for m in models_data if "id" in m]
            return sorted(model_ids)
        return []
    except Exception:
        return []


@router.post("/settings/test-llm", response_model=TestLlmResponse)
def test_llm_connection_endpoint(db: Session = Depends(get_db)):
    return run_probe_ladder(db)


@router.get("/usage", response_model=UsageStats)
def get_usage_stats(db: Session = Depends(get_db)):
    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    total_tokens = (
        db.query(func.coalesce(func.sum(LlmCall.prompt_tokens + LlmCall.completion_tokens), 0))
        .filter(LlmCall.created_at >= today_start)
        .scalar()
    )
    total_calls = (
        db.query(func.count(LlmCall.id))
        .filter(LlmCall.created_at >= today_start)
        .scalar()
    )
    rate_limited_docs = (
        db.query(func.count(Document.id))
        .filter(Document.status == "rate_limited")
        .scalar()
    )
    last_call = (
        db.query(LlmCall.created_at)
        .order_by(LlmCall.created_at.desc())
        .first()
    )

    return UsageStats(
        tokens_today=int(total_tokens or 0),
        calls_today=int(total_calls or 0),
        rate_limited_documents=int(rate_limited_docs or 0),
        last_call_at=last_call[0] if last_call else None,
    )
