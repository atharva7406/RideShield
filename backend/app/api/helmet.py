import logging
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import HelmetVerifyResponse
from app.services import helmet_verification_service as helmet_service
from db.core.session import get_db
from db.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/acknowledge", response_model=HelmetVerifyResponse)
def acknowledge_helmet(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Rider explicitly checks the mandatory "I will wear a helmet at all
    times" checkbox on the rider-app helmet-check screen. Replaces the
    earlier photo/ML-based helmet detection (removed entirely — see
    helmet_verification_service.py's module docstring) with an honest
    acknowledgment: the backend cannot verify from a selfie whether a
    rider actually keeps a helmet on for a whole shift, so it now records
    informed consent to a hard, real consequence instead of a
    probabilistic guess.

    If the rider is later found not to have been wearing a helmet at the
    time of an accident, that voids the resulting claim — enforced at
    claim-review time, not here.

    A PASSED result here is a prerequisite for POST /shifts/start and
    POST /payments/create-order (see their gate checks) — it is NOT
    itself sufficient to start a shift, just the first step.
    """
    result = helmet_service.acknowledge_helmet_safety()
    record = helmet_service.record_verification(db, current_user.id, result)
    db.commit()
    db.refresh(record)

    return HelmetVerifyResponse(
        verification_id=record.id,
        helmet_worn=result.helmet_worn,
        predicted_class=result.predicted_class,
        confidence=result.confidence,
        model_version=result.model_version,
        valid_for_minutes=helmet_service.VERIFICATION_VALIDITY_MINUTES,
        message="Helmet safety acknowledgment recorded. You're clear to start your shift.",
    )
