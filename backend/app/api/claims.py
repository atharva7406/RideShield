from datetime import datetime, timezone
import uuid
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import ClaimCreate, ClaimResponse
from db.core.session import get_db
from db.models.user import User
from db.models.incident import Incident
from db.models.claim import Claim
from db.models.payment import Payment
from db.models.enums import ClaimStatus, IncidentStatus, UserRole, PaymentStatus, PaymentType

router = APIRouter()

@router.post("", response_model=ClaimResponse)
def submit_claim(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    claim_in: ClaimCreate
) -> Any:
    # Verify incident
    incident = db.query(Incident).filter(Incident.id == claim_in.incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if current_user.role == UserRole.RIDER and incident.rider_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only file claims for your own incidents."
        )

    # Check if a claim already exists for this incident
    existing_claim = db.query(Claim).filter(Claim.incident_id == claim_in.incident_id).first()
    if existing_claim:
        raise HTTPException(
            status_code=400,
            detail="A claim has already been submitted for this incident."
        )

    claim_num = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    db_claim = Claim(
        incident_id=claim_in.incident_id,
        rider_id=incident.rider_id,
        shift_id=incident.shift_id,
        claim_number=claim_num,
        status=ClaimStatus.SUBMITTED,
        claimed_amount=claim_in.claimed_amount
    )

    # Auto-approve if incident confidence score is very high (L3 automated payout demo flow)
    if incident.confidence_score >= 0.85:
        db_claim.status = ClaimStatus.APPROVED
        db_claim.approved_amount = claim_in.claimed_amount

        # Create instant mock Claim Payout
        db_payment = Payment(
            claim_id=db_claim.id,
            rider_id=incident.rider_id,
            payment_type=PaymentType.CLAIM_PAYOUT,
            amount=claim_in.claimed_amount,
            status=PaymentStatus.SUCCESSFUL,
            transaction_ref=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            processed_at=datetime.now(timezone.utc)
        )
        db.add(db_payment)

        # Update incident status to VERIFIED_ACCIDENT
        incident.status = IncidentStatus.VERIFIED_ACCIDENT
        db.add(incident)

        # Update rider's wallet balance
        rider = db.query(User).filter(User.id == incident.rider_id).first()
        if rider:
            rider.wallet_balance += claim_in.claimed_amount
            db.add(rider)

    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)
    return db_claim

@router.get("", response_model=List[ClaimResponse])
def read_claims(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    if current_user.role in [UserRole.INSURER, UserRole.ADMIN, UserRole.SUPPORT]:
        claims = db.query(Claim).all()
    else:
        claims = db.query(Claim).filter(Claim.rider_id == current_user.id).all()
    return claims

@router.get("/{claim_id}", response_model=ClaimResponse)
def read_claim(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    claim_id: uuid.UUID
) -> Any:
    db_claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not db_claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if current_user.role == UserRole.RIDER and db_claim.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this claim")

    return db_claim

@router.post("/{claim_id}/approve", response_model=ClaimResponse)
def approve_claim(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    claim_id: uuid.UUID,
    approved_amount: float
) -> Any:
    if current_user.role not in [UserRole.INSURER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only insurers or admins can approve claims")

    db_claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not db_claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    db_claim.status = ClaimStatus.APPROVED
    db_claim.approved_amount = approved_amount

    # Trigger payout
    db_payment = Payment(
        claim_id=db_claim.id,
        rider_id=db_claim.rider_id,
        payment_type=PaymentType.CLAIM_PAYOUT,
        amount=approved_amount,
        status=PaymentStatus.SUCCESSFUL,
        transaction_ref=f"TXN-{uuid.uuid4().hex[:12].upper()}",
        processed_at=datetime.now(timezone.utc)
    )
    db.add(db_payment)

    # Update incident status
    incident = db.query(Incident).filter(Incident.id == db_claim.incident_id).first()
    if incident:
      incident.status = IncidentStatus.VERIFIED_ACCIDENT
      db.add(incident)

    # Update rider's wallet balance
    rider = db.query(User).filter(User.id == db_claim.rider_id).first()
    if rider:
      rider.wallet_balance += approved_amount
      db.add(rider)

    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)
    return db_claim

@router.post("/{claim_id}/reject", response_model=ClaimResponse)
def reject_claim(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    claim_id: uuid.UUID,
    rejection_reason: str
) -> Any:
    if current_user.role not in [UserRole.INSURER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only insurers or admins can reject claims")

    db_claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not db_claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    db_claim.status = ClaimStatus.REJECTED
    db_claim.rejection_reason = rejection_reason

    incident = db.query(Incident).filter(Incident.id == db_claim.incident_id).first()
    if incident:
        incident.status = IncidentStatus.FALSE_POSITIVE
        db.add(incident)

    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)
    return db_claim
