from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.db import get_db
from app.security.auth import verify_api_key
from app.models import Observation
from app.schemas import LabTestSummary, LabChartResponse, ChartPoint
from app.services.documents import get_lab_dictionary
from app.pipeline.normalize import _find_canonical_test_id

router = APIRouter(prefix="/api/v1", tags=["Charts"])


@router.get(
    "/tests",
    response_model=List[LabTestSummary],
    dependencies=[Depends(verify_api_key)],
)
def list_available_tests(db: Session = Depends(get_db)):
    """Lists distinct lab tests having confirmed observations, normalized to canonical test IDs where matched."""
    lab_dict = get_lab_dictionary()

    confirmed_obs = (
        db.query(Observation)
        .filter(Observation.status == "confirmed")
        .order_by(
            Observation.collected_at.desc().nullslast(),
            Observation.id.desc(),
        )
        .all()
    )

    tests_map = {}
    for obs in confirmed_obs:
        # Determine canonical ID and canonical display name
        canon_id = obs.canonical_test_id or _find_canonical_test_id(obs.test_name, lab_dict)
        if canon_id and canon_id in lab_dict:
            display_name = lab_dict[canon_id].get("name", obs.test_name)
            key = canon_id
        else:
            display_name = obs.test_name
            key = obs.test_name.strip().lower()

        if key not in tests_map:
            tests_map[key] = {
                "test_name": display_name,
                "canonical_test_id": canon_id,
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
            # If current recorded latest_date is None but this observation has one, update latest details
            if tests_map[key]["latest_date"] is None and obs.collected_at is not None:
                tests_map[key]["latest_value"] = obs.value_num
                tests_map[key]["latest_unit"] = obs.unit
                tests_map[key]["latest_flag"] = obs.flag
                tests_map[key]["latest_date"] = obs.collected_at
                tests_map[key]["ref_low"] = obs.ref_low
                tests_map[key]["ref_high"] = obs.ref_high

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
    """Returns chronological time-series points and reference ranges for a lab test, alias-resolved."""
    lab_dict = get_lab_dictionary()
    clean_test = test.strip().lower()
    canon_id = clean_test if clean_test in lab_dict else _find_canonical_test_id(test, lab_dict)

    query = (
        db.query(Observation)
        .filter(
            Observation.status == "confirmed",
            Observation.collected_at.isnot(None),
            Observation.value_num.isnot(None),
        )
    )

    if canon_id:
        canon_name = lab_dict.get(canon_id, {}).get("name", "").lower()
        query = query.filter(
            or_(
                Observation.canonical_test_id == canon_id,
                func.lower(Observation.test_name) == clean_test,
                func.lower(Observation.test_name) == canon_name,
            )
        )
    else:
        query = query.filter(func.lower(Observation.test_name) == clean_test)

    if from_date:
        query = query.filter(Observation.collected_at >= from_date)
    if to_date:
        query = query.filter(Observation.collected_at <= to_date)

    obs_records = query.order_by(Observation.collected_at.asc(), Observation.id.asc()).all()

    display_title = lab_dict.get(canon_id, {}).get("name", test) if canon_id else test

    if not obs_records:
        return LabChartResponse(
            test_name=display_title,
            points=[],
            ref_low=None,
            ref_high=None,
            unit=None,
        )

    # Use the most recent observation with non-null ref bounds or the latest reading
    latest = obs_records[-1]
    ref_low = next((o.ref_low for o in reversed(obs_records) if o.ref_low is not None), latest.ref_low)
    ref_high = next((o.ref_high for o in reversed(obs_records) if o.ref_high is not None), latest.ref_high)
    unit = next((o.unit for o in reversed(obs_records) if o.unit is not None), latest.unit)

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
        test_name=display_title,
        points=points,
        ref_low=ref_low,
        ref_high=ref_high,
        unit=unit,
    )
