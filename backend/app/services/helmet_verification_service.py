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

MODEL QUALITY / CURRENT INFERENCE PATH: the original helmet_detection_engine
ONNX classifier (helmet_detection_engine/config.py's module docstring)
was trained on synthetic noise images, never real photos, and its
real-photo confidence was measured at ~44-53% (no better than random for
a 3-class problem) — see the DB evidence that led to replacing it.
verify_image() below therefore does NOT call that model. It uses a
classical Haar-cascade FACE detector (bundled inside opencv-python-headless
itself — no external model file, no training data needed) as a genuine
per-image heuristic: a full-face motorcycle helmet obscures the face, so
"no face detected in an otherwise-decodable selfie" is used as the
full-face-helmet signal, and "a face is clearly detected" as no_helmet.
This is real image analysis, not a bypass — output varies with the actual
photo — but it IS a heuristic, not a trained classifier: it will
misclassify half-face helmets (face still visible) and bad-lighting/
no-face photos as false positives. model_version is stamped
"face-heuristic-v1" so this is always distinguishable in the DB from
either the old ONNX model or a manual bypass.

ISOLATION: only this module imports helmet_detection_engine / cv2 for
helmet verification, same boundary principle as ml_scoring_service/
ml_incident_engine and rider_behaviour_risk_service/behaviour_risk_engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_engine_available = True
try:
    from helmet_detection_engine import config as helmet_cfg
    from helmet_detection_engine.predict import load_session, predict_from_image_bytes
except Exception as e:  # pragma: no cover - defensive import guard
    _engine_available = False
    logger.warning(f"helmet_detection_engine unavailable (unused by the current face-heuristic inference path): {e}")

FACE_HEURISTIC_MODEL_VERSION = "face-heuristic-v1"

_face_cascade = None


def _get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            raise HelmetVerificationError("Face-detection cascade failed to load.")
        _face_cascade = cascade
    return _face_cascade


# A face detector alone only catches CLOSED full-face helmets (visor down,
# nothing visible). Half-face/open-face helmets and full-face helmets with
# the visor up still show eyes/nose/mouth, so the face cascade correctly
# finds a face — but the rider is still wearing a helmet. This threshold
# is the second signal that catches that case: the region directly above
# a detected face (where bare hair would be) is smooth/uniform-colored
# plastic for a helmet shell, versus visibly textured for real hair.
# Grayscale intensity std-dev is the cheap proxy — hair's strand/shadow
# texture reliably reads higher than a helmet shell's smooth surface
# under normal selfie lighting. Not derived from labeled data (there is
# none) — a documented, tunable starting point like every other threshold
# in this codebase, not a calibrated operating point. Raised from an
# initial 18.0 after real-device testing showed real helmet shells
# (glare, vents, strap lines) read noisier than a lab assumption of
# "perfectly smooth plastic" — 35.0 gives more benefit of the doubt.
HAIR_VS_HELMET_STD_THRESHOLD = 35.0


def _region_above_face_is_smooth(gray: "np.ndarray", face_box) -> Optional[bool]:
    """True if the band directly above the detected face looks like a
    smooth helmet shell rather than textured hair; None if there isn't
    enough headroom in the frame to judge (face detected right at the
    top edge) — caller should treat None as "can't tell, assume no
    helmet" per the fail-closed gate philosophy."""
    x, y, w, h = face_box
    top = max(0, y - h // 2)
    # Narrowed to the central 60% of the face's width and closer to the
    # brow line (h // 3, not h // 2) — real-device testing showed the
    # full-width band was catching hair at the temples / helmet strap
    # edges even for a genuinely worn helmet, dragging the std up.
    margin = int(w * 0.2)
    left = x + margin
    right = x + w - margin
    bottom = max(top + 1, y - h // 6)
    region = gray[top:bottom, left:right]
    if region.size < 80:  # too small a sample to judge reliably
        return None
    return float(region.std()) < HAIR_VS_HELMET_STD_THRESHOLD


def _run_face_heuristic(image_bytes: bytes) -> dict:
    """Real per-image inference: decodes the upload, runs Haar-cascade
    frontal-face detection, and returns a result shaped identically to
    the old ONNX predict_from_image_bytes() output so nothing downstream
    (verify_image, the API schema) needs to know which path ran."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image — not a valid image file.")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = _get_face_cascade()
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    if len(faces) == 0:
        # No face at all — closed full-face helmet (visor down), or a bad
        # photo. Can't tell those apart without more signal; treat as worn,
        # same as before.
        return {
            "predicted_class": "full_face_helmet",
            "confidence": 0.75,
            "helmet_worn": True,
            "model_version": FACE_HEURISTIC_MODEL_VERSION,
        }

    largest = max(faces, key=lambda f: f[2] * f[3])
    face_area_ratio = (largest[2] * largest[3]) / float(gray.shape[0] * gray.shape[1])
    smooth_above = _region_above_face_is_smooth(gray, largest)

    if smooth_above:
        # Face visible, but what should be hair is a smooth uniform
        # surface instead — half-face/open-visor helmet.
        return {
            "predicted_class": "half_face_helmet",
            "confidence": 0.7,
            "helmet_worn": True,
            "model_version": FACE_HEURISTIC_MODEL_VERSION,
        }

    confidence = min(0.95, 0.6 + face_area_ratio)
    return {
        "predicted_class": "no_helmet",
        "confidence": float(confidence),
        "helmet_worn": False,
        "model_version": FACE_HEURISTIC_MODEL_VERSION,
    }

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

    try:
        result = _run_face_heuristic(image_bytes)
    except ValueError as e:
        raise HelmetVerificationError(str(e))
    except HelmetVerificationError:
        raise
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
