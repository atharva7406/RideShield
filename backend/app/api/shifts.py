from datetime import datetime, timezone
import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import ShiftStart, ShiftEnd, ShiftResponse
from db.core.session import get_db
from db.models.user import User
from db.models.shift import Shift
from db.models.payment import Payment
from db.models.enums import ShiftStatus, PaymentStatus, PaymentType, UserRole

router = APIRouter()

@router.post("/start", response_model=ShiftResponse)
def start_shift(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    shift_in: ShiftStart
) -> Any:
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

    # Check and deduct wallet balance if wallet payment method selected
    if shift_in.payment_method == "wallet":
        if current_user.wallet_balance < shift_in.premium_amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient wallet balance. Balance: ₹{current_user.wallet_balance:.2f}, Required: ₹{shift_in.premium_amount:.2f}"
            )
        current_user.wallet_balance -= shift_in.premium_amount

    # Start new shift
    policy_num = f"POL-{uuid.uuid4().hex[:8].upper()}"
    db_shift = Shift(
        rider_id=current_user.id,
        status=ShiftStatus.ACTIVE,
        start_time=datetime.now(timezone.utc),
        premium_amount=shift_in.premium_amount,
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
        amount=shift_in.premium_amount,
        status=PaymentStatus.SUCCESSFUL,
        transaction_ref=f"TXN-{uuid.uuid4().hex[:12].upper()}",
        processed_at=datetime.now(timezone.utc)
    )
    db.add(db_payment)
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
    db_shift = db.query(Shift).filter(
        Shift.id == shift_id,
        Shift.rider_id == current_user.id
    ).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if db_shift.status != ShiftStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Shift is already ended or cancelled")

    db_shift.status = ShiftStatus.COMPLETED
    db_shift.end_time = datetime.now(timezone.utc)
    db_shift.distance_km = shift_in.distance_km

    db.add(db_shift)
    db.commit()
    db.refresh(db_shift)

    import math
    from db.models.incident import Incident
    from db.models.telemetry import TelemetryBatch, TelemetrySample
    from app.schemas import ShiftSummarySchema

    # Incidents
    incident_count = db.query(Incident).filter(Incident.shift_id == shift_id).count()

    # Telemetry
    avg_speed = 0.0
    max_speed = 0.0
    max_g = 1.0
    batches = db.query(TelemetryBatch).filter(TelemetryBatch.shift_id == shift_id).all()
    batch_ids = [b.id for b in batches]
    if batch_ids:
        samples = db.query(TelemetrySample).filter(TelemetrySample.batch_id.in_(batch_ids)).all()
        if samples:
            speeds = [s.speed for s in samples]
            avg_speed = sum(speeds) / len(speeds)
            max_speed = max(speeds)
            g_forces = [math.sqrt(s.accel_x**2 + s.accel_y**2 + s.accel_z**2)/9.81 for s in samples]
            max_g = max(g_forces)

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
