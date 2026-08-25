import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import HelmetVerifyResponse
from app.services import helmet_verification_service as helmet_service
from db.core.session import get_db
from db.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/verify", response_model=HelmetVerifyResponse)
async def verify_helmet(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    file: UploadFile = File(...),
) -> Any:
    """
    Rider uploads a selfie; server runs the helmet classifier and
    persists the verdict. A PASSED result here is a prerequisite for
    POST /shifts/start and POST /payments/create-order (see their gate
    checks) — it is NOT itself sufficient to start a shift, just the
    first step. The client cannot skip this by claiming helmet_worn on
    the shift-start request; that field doesn't exist on those requests.

    Content-type is checked but never trusted as the sole gate — the
    image bytes still go through real decode/preprocess before anything
    is decided.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    image_bytes = await file.read()

    try:
        result = helmet_service.verify_image(image_bytes)
    except helmet_service.HelmetVerificationError as e:
        logger.warning(f"Helmet verification failed for rider {current_user.id}: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    record = helmet_service.record_verification(db, current_user.id, result)
    db.commit()
    db.refresh(record)

    if result.helmet_worn:
        message = "Helmet verified. You're clear to start your shift."
    else:
        message = f"No helmet detected ({result.predicted_class}). Please wear a helmet and try again."

    return HelmetVerifyResponse(
        verification_id=record.id,
        helmet_worn=result.helmet_worn,
        predicted_class=result.predicted_class,
        confidence=result.confidence,
        model_version=result.model_version,
        valid_for_minutes=helmet_service.VERIFICATION_VALIDITY_MINUTES,
        message=message,
    )
