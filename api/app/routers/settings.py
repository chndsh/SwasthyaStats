import httpx
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db, set_rls_user_id
from app.security.auth import get_current_user
from app.models import LlmCall, Document, User
from app.services.settings import SettingsService
from app.schemas import AppSettingsRead, AppSettingsUpdate, TestLlmResponse, UsageStats
from app.llm.probe import run_probe_ladder

router = APIRouter(prefix="/api/v1", tags=["Settings"])


@router.get("/settings", response_model=AppSettingsRead)
def get_settings_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_rls_user_id(db, current_user.id)
    service = SettingsService(db, current_user.id)
    return service.get_read_settings()


@router.put("/settings", response_model=AppSettingsRead)
def update_settings_endpoint(
    update: AppSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_rls_user_id(db, current_user.id)
    service = SettingsService(db, current_user.id)
    return service.update_settings(update)


@router.get("/settings/models", response_model=List[str])
def list_models_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_rls_user_id(db, current_user.id)
    service = SettingsService(db, current_user.id)
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
def test_llm_connection_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_rls_user_id(db, current_user.id)
    return run_probe_ladder(db, user_id=current_user.id)


@router.get("/usage", response_model=UsageStats)
def get_usage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import timezone
    set_rls_user_id(db, current_user.id)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_tokens = (
        db.query(func.coalesce(func.sum(LlmCall.prompt_tokens + LlmCall.completion_tokens), 0))
        .filter(LlmCall.created_at >= today_start, LlmCall.user_id == current_user.id)
        .scalar()
    )
    total_calls = (
        db.query(func.count(LlmCall.id))
        .filter(LlmCall.created_at >= today_start, LlmCall.user_id == current_user.id)
        .scalar()
    )

    doc_counts = dict(
        db.query(Document.status, func.count(Document.id))
        .filter(Document.user_id == current_user.id)
        .group_by(Document.status)
        .all()
    )

    service = SettingsService(db, current_user.id)
    daily_cap = service.get_setting_value("llm.daily_token_cap", 200000)

    return UsageStats(
        total_tokens_today=total_tokens,
        daily_token_cap=daily_cap,
        total_calls_today=total_calls,
        document_counts=doc_counts,
    )
