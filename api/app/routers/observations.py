from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.security.auth import verify_api_key
from app.models import Observation, Document
from app.schemas import ObservationRead, ObservationPatch

router = APIRouter(prefix="/api/v1/observations", tags=["Observations"])


@router.patch(
    "/{observation_id}",
    response_model=ObservationRead,
    dependencies=[Depends(verify_api_key)],
)
def patch_observation(
    observation_id: int,
    patch_data: ObservationPatch,
    db: Session = Depends(get_db),
):
    """Updates an observation's fields during human review.

    Rejects modifications with 409 Conflict if document is already confirmed.
    """
    obs = db.query(Observation).filter(Observation.id == observation_id).first()
    if not obs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found",
        )

    doc = db.query(Document).filter(Document.id == obs.document_id).first()
    if doc and doc.status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit observations of a confirmed document",
        )

    update_dict = patch_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            setattr(obs, field, value)

    db.commit()
    db.refresh(obs)
    return obs
