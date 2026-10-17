from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.security.auth import verify_api_key
from app.models import Observation
from app.schemas import LabTestSummary, LabChartResponse, ChartPoint

router = APIRouter(prefix="/api/v1", tags=["Charts"])


@router.get(
    "/tests",
    response_model=List[LabTestSummary],
    dependencies=[Depends(verify_api_key)],
)
def list_available_tests(db: Session = Depends(get_db)):
    """Lists distinct lab tests having confirmed observations with latest value and reference intervals."""
    # Group by test_name for confirmed observations
    confirmed_obs = (
        db.query(Observation)
        .filter(Observation.status == "confirmed")
        .order_by(Observation.test_name.asc(), Observation.collected_at.desc().nullslast(), Observation.id.desc())
        .all()
    )

    tests_map = {}
    for obs in confirmed_obs:
        key = obs.test_name
        if key not in tests_map:
            tests_map[key] = {
                "test_name": obs.test_name,
                "canonical_test_id": obs.canonical_test_id,
                "count": 1,
                "latest_value": obs.value_num,
                "latest_unit": obs.unit,
                "latest_flag": obs.flag,
                "latest_date": obs.collected_at,
                "ref_low": obs.ref_low,
                "ref_high": obs.ref_high,
            }
        else:
            tests_map[key]["count"] += 1

    result = [LabTestSummary(**data) for data in tests_map.values()]
    result.sort(key=lambda t: t.test_name.lower())
    return result


@router.get(
    "/charts/lab",
    response_model=LabChartResponse,
    dependencies=[Depends(verify_api_key)],
)
def get_lab_chart(
    test: str = Query(..., description="Test name to plot"),
    from_date: Optional[date] = Query(None, alias="from", description="Start date filter"),
    to_date: Optional[date] = Query(None, alias="to", description="End date filter"),
    db: Session = Depends(get_db),
):
    """Returns chronological time-series points and reference ranges for a lab test."""
    query = (
        db.query(Observation)
        .filter(
            Observation.status == "confirmed",
            func.lower(Observation.test_name) == test.lower(),
            Observation.collected_at.isnot(None),
            Observation.value_num.isnot(None),
        )
    )

    if from_date:
        query = query.filter(Observation.collected_at >= from_date)
    if to_date:
        query = query.filter(Observation.collected_at <= to_date)

    obs_records = query.order_by(Observation.collected_at.asc(), Observation.id.asc()).all()

    if not obs_records:
        return LabChartResponse(
            test_name=test,
            points=[],
            ref_low=None,
            ref_high=None,
            unit=None,
        )

    # Use the most recent observation's unit and reference interval
    latest = obs_records[-1]
    points = [
        ChartPoint(
            date=o.collected_at,
            value=o.value_num,
            flag=o.flag,
            document_id=o.document_id,
            page_no=o.page_no or 1,
        )
        for o in obs_records
    ]

    return LabChartResponse(
        test_name=latest.test_name,
        points=points,
        ref_low=latest.ref_low,
        ref_high=latest.ref_high,
        unit=latest.unit,
    )
