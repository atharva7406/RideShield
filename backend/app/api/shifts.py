from datetime import datetime, timezone
import logging
import math
import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import ShiftStart, ShiftEnd, ShiftResponse, ShiftSummarySchema, PremiumPreviewResponse
from app.services import behaviour_summary_service, distance_service, helmet_verification_service, premium_pricing_service, rider_behaviour_profile_service
from db.core.session import get_db
from db.models.user import User
from db.models.shift import Shift
from db.models.shift_behaviour_summary import ShiftBehaviourSummary
from db.models.payment import Payment
from db.models.enums import ShiftStatus, PaymentStatus, PaymentType, UserRole

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/start", response_model=ShiftResponse)
def start_shift(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    shift_in: ShiftStart
) -> Any:
    """
    Starts a shift and (Phase 7) charges the SERVER-COMPUTED premium —
    shift_in.premium_amount is deprecated and never read below; it exists
    only so older app builds that still send it don't fail schema
    validation. See app/services/premium_pricing_service.py for the full
    architecture:

        authenticated rider -> RiderBehaviourProfile -> risk assessment
            -> PremiumPricingService -> PremiumQuote.final_premium

    This is the "wallet" / instant-activation path (no Razorpay order —
    see POST /payments/create-order + /payments/verify for the UPI path,
    which is wired the same way). Both paths must derive the amount from
    the rider ID alone; neither reads a client-supplied amount, risk
    score, or risk band.
    """
    # Check if there is an active shift for the rider
    active_shift = db.query(Shift).filter(
        Shift.rider_id == current_user.id,
        Shift.status == ShiftStatus.ACTIVE
    ).first()
    if active_shift:
        raise HTTPException(
            status_code=400,
            detail="You already have an active shift. Please end it before starting a new one."
        )

    # MANDATORY HELMET GATE: server-side only — no field on ShiftStart
    # can satisfy this. Requires a recent, PASSED, not-yet-consumed
    # verification created via POST /helmet/verify. Fails closed: no
    # usable verification (missing, failed, expired, or already spent on
    # another shift) means no shift starts, full stop.
    verification = helmet_verification_service.get_usable_verification(db, current_user.id)
    if verification is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "Helmet verification required before starting a shift. "
                "Please verify you're wearing a helmet (POST /helmet/verify) and try again."
            ),
        )

    # SERVER-AUTHORITATIVE PREMIUM (Phase 7): the ONLY inputs are
    # current_user.id and DB state — never shift_in. See
    # premium_pricing_service.calculate_premium_quote()'s own docstring
    # for why its signature makes a client-supplied amount structurally
    # impossible to smuggle in, not just conventionally ignored.
    quote = premium_pricing_service.calculate_premium_quote(db, current_user.id)
    final_premium = quote.final_premium  # Decimal, already clamped/quantized

    # Check and deduct wallet balance if wallet payment method selected.
    # wallet_balance is a plain Float column (pre-existing schema, not
    # touched by this phase) — float() here is the one, deliberate,
    # boundary-only conversion of the Decimal premium for that comparison.
    if shift_in.payment_method == "wallet":
        premium_float = float(final_premium)
        if current_user.wallet_balance < premium_float:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient wallet balance. Balance: ₹{current_user.wallet_balance:.2f}, Required: ₹{premium_float:.2f}"
            )
        current_user.wallet_balance -= premium_float

    # Start new shift
    policy_num = f"POL-{uuid.uuid4().hex[:8].upper()}"
    db_shift = Shift(
        rider_id=current_user.id,
        status=ShiftStatus.ACTIVE,
        start_time=datetime.now(timezone.utc),
        premium_amount=final_premium,
        policy_number=policy_num,
        distance_km=0.0
    )
    db.add(db_shift)
    db.flush()  # Acquire shift ID

    # Create Premium Payment
    db_payment = Payment(
        shift_id=db_shift.id,
        rider_id=current_user.id,
        payment_type=PaymentType.PREMIUM_COLLECTION,
        amount=final_premium,
        status=PaymentStatus.SUCCESSFUL,
        transaction_ref=f"TXN-{uuid.uuid4().hex[:12].upper()}",
        processed_at=datetime.now(timezone.utc)
    )
    db.add(db_payment)

    # Persist the audit trail: "why was this rider charged ₹X?"
    premium_pricing_service.persist_premium_quote(db, quote, db_shift.id)

    # Spend the helmet verification on THIS shift — it can't be reused
    # to start a second shift later.
    helmet_verification_service.consume_verification(verification, db_shift.id)

    db.commit()
    db.refresh(db_shift)
    return db_shift

@router.post("/{shift_id}/end", response_model=ShiftResponse)
def end_shift(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    shift_id: uuid.UUID,
    shift_in: ShiftEnd
) -> Any:
    """
    Ends a shift and generates its ShiftBehaviourSummary (Phase 1 of the
    Behaviour Risk & Premium Engine — see
    app/services/distance_service.py and
    app/services/behaviour_summary_service.py for the calculations).

    `shift_in.distance_km` (if the client still sends it) is accepted for
    backward compatibility but NEVER trusted — the authoritative
    Shift.distance_km is computed here, server-side, from the shift's own
    retained GPS telemetry.

    Idempotent: if a ShiftBehaviourSummary already exists for this shift
    (a retried request, or a narrow concurrent-request race), no duplicate
    is created — the shift_id UNIQUE constraint on ShiftBehaviourSummary
    is the hard backstop; the pre-check here is just the graceful path
    that avoids surfacing that as a 500.
    """
    db_shift = db.query(Shift).filter(
        Shift.id == shift_id,
        Shift.rider_id == current_user.id
    ).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if db_shift.status != ShiftStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Shift is already ended or cancelled")

    from db.models.incident import Incident
    from db.models.telemetry import TelemetryBatch, TelemetrySample

    batches = db.query(TelemetryBatch).filter(TelemetryBatch.shift_id == shift_id).all()
    batch_ids = [b.id for b in batches]
    samples = (
        db.query(TelemetrySample).filter(TelemetrySample.batch_id.in_(batch_ids)).all()
        if batch_ids else []
    )

    db_shift.status = ShiftStatus.COMPLETED
    db_shift.end_time = datetime.now(timezone.utc)

    duration_seconds = max(0.0, (db_shift.end_time - db_shift.start_time).total_seconds())

    distance_result = distance_service.compute_distance_km(samples)
    # Server-authoritative — shift_in.distance_km is never used here.
    db_shift.distance_km = distance_result.distance_km

    existing_summary = db.query(ShiftBehaviourSummary).filter(
        ShiftBehaviourSummary.shift_id == shift_id
    ).first()

    if existing_summary is None:
        metrics = behaviour_summary_service.compute_behaviour_metrics(samples)
        quality = behaviour_summary_service.compute_data_quality(samples, duration_seconds, distance_result)
        sampling_density = (metrics.sample_count / (duration_seconds / 60.0)) if duration_seconds > 0 else 0.0

        db_summary = ShiftBehaviourSummary(
            shift_id=shift_id,
            rider_id=current_user.id,
            duration_seconds=int(duration_seconds),
            distance_km=distance_result.distance_km,
            sample_count=metrics.sample_count,
            average_speed=metrics.average_speed,
            max_speed=metrics.max_speed,
            hard_braking_count=metrics.hard_braking_count,
            hard_acceleration_count=metrics.hard_acceleration_count,
            overspeeding_count=metrics.overspeeding_count,
            sharp_turn_count=metrics.sharp_turn_count,
            hard_braking_rate=behaviour_summary_service.compute_hourly_rate(
                metrics.hard_braking_count, duration_seconds),
            hard_acceleration_rate=behaviour_summary_service.compute_hourly_rate(
                metrics.hard_acceleration_count, duration_seconds),
            overspeeding_rate=behaviour_summary_service.compute_hourly_rate(
                metrics.overspeeding_count, duration_seconds),
            sharp_turn_rate=behaviour_summary_service.compute_hourly_rate(
                metrics.sharp_turn_count, duration_seconds),
            max_g=metrics.max_g,
            accel_std=metrics.accel_std,
            jerk_mean=metrics.jerk_mean,
            sampling_density=sampling_density,
            data_quality_score=quality.score,
            is_valid=behaviour_summary_service.is_summary_valid(metrics.sample_count, quality.score),
        )
        db.add(db_summary)

    db.add(db_shift)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent end_shift request for the same
        # shift — the other request's summary already committed. Roll
        # back this transaction's attempt and continue; the shift status/
        # end_time/distance updates are safe to retry-commit since they're
        # idempotent writes (same values either request would compute).
        db.rollback()
        db_shift.status = ShiftStatus.COMPLETED
        db_shift.end_time = db_shift.end_time or datetime.now(timezone.utc)
        db_shift.distance_km = distance_result.distance_km
        db.add(db_shift)
        db.commit()
    db.refresh(db_shift)

    # ShiftBehaviourSummary -> RiderBehaviourProfile (Phase 2). Rebuilding
    # the profile must NEVER prevent the shift itself from completing —
    # the shift/summary above already committed successfully; a failure
    # here is logged and swallowed, not raised, same fallback-safety
    # principle as app/services/ml_scoring_service.py's ML/rule-engine
    # fallback for crash scoring.
    try:
        rider_behaviour_profile_service.rebuild_rider_profile(db, current_user.id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to rebuild RiderBehaviourProfile for rider {current_user.id}: {e}")

    # Response summary — unchanged shape, computed from the same samples
    # already fetched above (not a second query).
    incident_count = db.query(Incident).filter(Incident.shift_id == shift_id).count()
    speeds = [s.speed for s in samples]
    avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
    max_speed = max(speeds) if speeds else 0.0
    g_forces = [math.sqrt(s.accel_x**2 + s.accel_y**2 + s.accel_z**2) / 9.81 for s in samples]
    max_g = max(g_forces) if g_forces else 1.0

    delta = db_shift.end_time - db_shift.start_time
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    duration_str = f"{hours}h {minutes}m"

    db_shift.summary = ShiftSummarySchema(
        duration=duration_str,
        distanceKm=float(db_shift.distance_km),
        avgSpeedKmh=float(avg_speed),
        peakSpeedKmh=float(max_speed),
        peakGForce=float(max_g),
        incidentCount=incident_count,
        premiumPaidInr=float(db_shift.premium_amount)
    )

    return db_shift

@router.get("", response_model=List[ShiftResponse])
def read_shifts(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    if current_user.role in [UserRole.INSURER, UserRole.ADMIN, UserRole.SUPPORT]:
        shifts = db.query(Shift).all()
    else:
        shifts = db.query(Shift).filter(Shift.rider_id == current_user.id).all()
    return shifts

@router.get("/premium-preview", response_model=PremiumPreviewResponse)
def preview_premium(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Read-only preview of the premium PremiumPricingService would charge
    right now for this rider's next shift.

    Calls premium_pricing_service.calculate_premium_quote() — the exact
    same server-authoritative function POST /shifts/start and
    POST /payments/create-order use — so the previewed price is
    identical to what a subsequent payment would charge, provided the
    rider's history hasn't changed in between. No pricing formula is
    duplicated here.

    ZERO SIDE EFFECTS, by construction, not by convention: this handler
    never calls db.add/db.commit/db.flush, never touches Payment/Shift/
    PremiumQuoteRecord, never calls razorpay_service, and
    calculate_premium_quote() itself only reads (RiderBehaviourProfile,
    the rider's most recent Shift for the rate-of-change baseline) — it
    performs no writes of its own either. Safe to call as often as the
    rider app wants to render the payment screen.

    Must come before GET /{shift_id} in route registration order, or
    FastAPI would try to parse "premium-preview" as a shift_id UUID.
    """
    quote = premium_pricing_service.calculate_premium_quote(db, current_user.id)
    return PremiumPreviewResponse(
        base_premium=float(quote.base_premium),
        risk_score=quote.risk_score,
        risk_band=quote.risk_band,
        confidence=quote.confidence,
        pricing_mode=quote.pricing_mode,
        scoring_method=quote.scoring_method,
        model_version=quote.model_version,
        adjustment_amount=float(quote.adjustment_amount),
        final_premium=float(quote.final_premium),
        is_cold_start=quote.is_cold_start,
        explanation=quote.explanation,
    )

@router.get("/{shift_id}", response_model=ShiftResponse)
def read_shift(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    shift_id: uuid.UUID
) -> Any:
    db_shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
        
    if current_user.role == UserRole.RIDER and db_shift.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this shift")
        
    return db_shift
