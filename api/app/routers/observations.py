from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db, set_rls_user_id
from app.security.auth import get_current_user
from app.models import Observation, Document, User
from app.schemas import ObservationRead, ObservationPatch

router = APIRouter(prefix="/api/v1/observations", tags=["Observations"])


@router.patch(
    "/{observation_id}",
    response_model=ObservationRead,
)
def patch_observation(
    observation_id: int,
    patch_data: ObservationPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates an observation's fields during human review.

    Rejects modifications with 409 Conflict if document is already confirmed.
    """
    set_rls_user_id(db, current_user.id)
    obs = db.query(Observation).filter(Observation.id == observation_id, Observation.user_id == current_user.id).first()
    if not obs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found",
        )

    doc = db.query(Document).filter(Document.id == obs.document_id, Document.user_id == current_user.id).first()
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
