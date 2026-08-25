"""
Wraps helmet_detection_engine for use inside the live backend. Mirrors
this project's established *_service.py shape (ml_scoring_service.py,
rider_behaviour_risk_service.py) but with an INVERTED fallback
philosophy, deliberately:

  - Those services fail OPEN: if the ML model is unavailable, they fall
    back to a deterministic default so the rider is never blocked from
    a core flow (starting a shift, getting priced) by an ML outage.
  - This service fails CLOSED: helmet verification is a mandatory safety
    gate ("if he doesn't have a helmet, he can't start shift" — explicit
    product decision). If the model can't run, there is no safe default
    that means "assume they're wearing a helmet" — so verification
    simply doesn't succeed, and the gate in app/api/shifts.py /
    app/api/payments.py stays closed until a real, passed verification
    exists. The rider sees a clear "try again" error, not a silent bypass
    and not a silent permanent lockout (retrying re-attempts inference).

MODEL QUALITY: see helmet_detection_engine/config.py's module docstring.
The shipped model was not trained on real photos. This service does not
paper over that — model_version is literally suffixed "-unvalidated" so
it's visible in every persisted HelmetVerification row and API response.

ISOLATION: only this module imports helmet_detection_engine, same
boundary principle as ml_scoring_service/ml_incident_engine and
rider_behaviour_risk_service/behaviour_risk_engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_engine_available = True
try:
    from helmet_detection_engine import config as helmet_cfg
    from helmet_detection_engine.predict import load_session, predict_from_image_bytes
except Exception as e:  # pragma: no cover - defensive import guard
    _engine_available = False
    logger.warning(f"helmet_detection_engine unavailable, verification will always fail closed: {e}")

# How long a PASSED, unconsumed verification remains usable to start a
# shift. Selfie must be recent — a helmet check from an hour ago doesn't
# prove the rider still has it on now.
VERIFICATION_VALIDITY_MINUTES = 15

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB — generous for a phone selfie, small enough to reject abuse


class HelmetVerificationError(Exception):
    """Raised for a caller-facing failure (bad image, model unavailable).
    Distinct from a successful inference that happens to return
    helmet_worn=False — that's a normal result, not an error."""


@dataclass
class HelmetVerificationResult:
    predicted_class: str
    confidence: float
    helmet_worn: bool
    model_version: str


def _get_session():
    if not _engine_available:
        raise HelmetVerificationError("Helmet detection model is unavailable.")
    try:
        return load_session()
    except Exception as e:
        logger.error(f"Failed to load helmet detection model: {e}")
        raise HelmetVerificationError("Helmet detection model failed to load.")


def verify_image(image_bytes: bytes) -> HelmetVerificationResult:
    """Runs inference on an uploaded selfie. Raises HelmetVerificationError
    for anything that prevents getting a real verdict (oversized upload,
    corrupt image, model unavailable) — never returns a fabricated
    result. A successful return with helmet_worn=False is not an error;
    it's the model doing its job."""
    if not image_bytes:
        raise HelmetVerificationError("No image data received.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HelmetVerificationError("Image is too large.")

    session = _get_session()
    try:
        result = predict_from_image_bytes(image_bytes, session=session)
    except ValueError as e:
        raise HelmetVerificationError(str(e))
    except Exception as e:
        logger.error(f"Helmet detection inference failed: {e}")
        raise HelmetVerificationError("Helmet detection failed to process the image.")

    return HelmetVerificationResult(
        predicted_class=result["predicted_class"],
        confidence=result["confidence"],
        helmet_worn=result["helmet_worn"],
        model_version=result["model_version"],
    )


def record_verification(db, rider_id, result: HelmetVerificationResult):
    """Persists the verification result. Does not commit — caller
    controls the transaction boundary (same convention as
    premium_pricing_service.persist_premium_quote)."""
    from db.models.helmet_verification import HelmetVerification

    record = HelmetVerification(
        rider_id=rider_id,
        predicted_class=result.predicted_class,
        confidence=result.confidence,
        helmet_worn=result.helmet_worn,
        model_version=result.model_version,
    )
    db.add(record)
    return record


def get_usable_verification(db, rider_id):
    """The most recent PASSED, unconsumed, still-valid verification for
    this rider — or None. This is the ONLY thing POST /shifts/start and
    POST /payments/create-order are allowed to trust; never a
    client-supplied "I have a helmet" claim."""
    from db.models.helmet_verification import HelmetVerification

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=VERIFICATION_VALIDITY_MINUTES)
    return (
        db.query(HelmetVerification)
        .filter(
            HelmetVerification.rider_id == rider_id,
            HelmetVerification.helmet_worn.is_(True),
            HelmetVerification.consumed_at.is_(None),
            HelmetVerification.created_at >= cutoff,
        )
        .order_by(HelmetVerification.created_at.desc())
        .first()
    )


def consume_verification(verification, shift_id) -> None:
    """Marks a verification as spent on this specific shift — it can
    never be reused to start a different shift later. Does not commit."""
    verification.consumed_at = datetime.now(timezone.utc)
    verification.shift_id = shift_id
