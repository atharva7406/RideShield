"""
Mandatory helmet safety gate for starting a shift.

HISTORY / WHY THERE'S NO ML HERE: earlier phases of this project tried
two different image-based classifiers to infer "is this rider wearing a
helmet" from an uploaded selfie — first an ONNX model trained on
synthetic noise images (real-photo confidence measured at ~44-53%, no
better than random for a 3-class problem), then a classical Haar-cascade
face-detector heuristic ("no face detected" as a proxy for "full-face
helmet on"). Both were removed: neither reliably distinguished a worn
helmet from no helmet, and even a perfect classifier only proves the
rider had a helmet on for the one frame of the selfie — it can't prove
they kept it on for the rest of the shift. This service now records an
explicit, honest signal instead of a probabilistic guess: the rider
checking a mandatory "I will wear a helmet at all times" checkbox on the
rider-app helmet-check screen, with the real consequence (claim
rejection) written into the copy itself. If a rider is later found not
to have been wearing a helmet at the time of an accident, that's grounds
to void the resulting claim — enforced at claim-review time, not by this
service.

FAIL-CLOSED, same as before: the gate in app/api/shifts.py /
app/api/payments.py stays closed until a real, unconsumed acknowledgment
exists. There's no dev bypass anywhere in this flow anymore — the
checkbox itself is the one, real, always-available way through the gate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Stamped onto every acknowledgment row's API response so it's always
# distinguishable from the earlier ONNX/Haar-cascade model versions in
# historical records.
ACKNOWLEDGMENT_MODEL_VERSION = "checkbox-acknowledgment-v1"

# How long a recorded, unconsumed acknowledgment remains usable to start
# a shift. Re-confirmation is required per shift, not once ever — a
# checkbox ticked an hour ago doesn't mean the rider is about to start
# riding right now.
VERIFICATION_VALIDITY_MINUTES = 15


@dataclass
class HelmetVerificationResult:
    predicted_class: str
    confidence: float
    helmet_worn: bool
    model_version: str


def acknowledge_helmet_safety() -> HelmetVerificationResult:
    """The rider explicitly confirmed the mandatory helmet safety
    checkbox. Pure, deterministic — there is no model to run and nothing
    that can fail here; the only way to get a False result is to never
    call this at all (i.e. not check the box)."""
    return HelmetVerificationResult(
        predicted_class="checkbox_acknowledged",
        confidence=1.0,
        helmet_worn=True,
        model_version=ACKNOWLEDGMENT_MODEL_VERSION,
    )


def record_verification(db, rider_id, result: HelmetVerificationResult):
    """Persists the acknowledgment. Does not commit — caller controls the
    transaction boundary (same convention as
    premium_pricing_service.persist_premium_quote)."""
    from db.models.helmet_verification import HelmetVerification

    record = HelmetVerification(
        rider_id=rider_id,
        helmet_worn=result.helmet_worn,
    )
    db.add(record)
    return record


def get_usable_verification(db, rider_id):
    """The most recent PASSED, unconsumed, still-valid acknowledgment for
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
    """Marks an acknowledgment as spent on this specific shift — it can
    never be reused to start a different shift later. Does not commit."""
    verification.consumed_at = datetime.now(timezone.utc)
    verification.shift_id = shift_id
