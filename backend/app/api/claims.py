from datetime import datetime, timezone
import uuid
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
import os
import shutil
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import ClaimCreate, ClaimResponse
from db.core.session import get_db
from db.models.user import User
from db.models.incident import Incident
from db.models.claim import Claim
from db.models.claim_medical_report import ClaimMedicalReport
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

    # Phase 4 (Incident Decision Engine): an incident the rider (or the
    # automated/WhatsApp verification flow) already resolved as NOT a real
    # accident must never become a claim.
    if incident.status in (IncidentStatus.FALSE_POSITIVE, IncidentStatus.DISCARDED):
        raise HTTPException(
            status_code=400,
            detail="This incident was resolved as a false positive and is not eligible for a claim.",
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
        status=ClaimStatus.MEDICAL_REPORT_PENDING,
        claimed_amount=claim_in.claimed_amount
    )

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
    elif current_user.role == UserRole.HOSPITAL_REP:
        if not current_user.hospital:
            return []
        claims = db.query(Claim).join(Incident).filter(
            Incident.locality == current_user.hospital.locality,
            Claim.status.in_([ClaimStatus.MEDICAL_REPORT_PENDING, ClaimStatus.MEDICAL_REPORT_SUBMITTED])
        ).all()
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

    if current_user.role == UserRole.HOSPITAL_REP:
        if not current_user.hospital or db_claim.incident.locality != current_user.hospital.locality:
            raise HTTPException(status_code=403, detail="Not authorized for this locality")

    return db_claim

@router.post("/{claim_id}/review", response_model=ClaimResponse)
def start_claim_review(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    claim_id: uuid.UUID
) -> Any:
    if current_user.role not in [UserRole.INSURER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only insurers or admins can review claims")

    db_claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not db_claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if db_claim.status not in [ClaimStatus.SUBMITTED, ClaimStatus.MEDICAL_REPORT_SUBMITTED]:
        raise HTTPException(status_code=400, detail="Claim cannot be moved to UNDER_REVIEW from its current state")

    db_claim.status = ClaimStatus.UNDER_REVIEW
    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)
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

    if db_claim.status != ClaimStatus.UNDER_REVIEW:
        raise HTTPException(status_code=400, detail="Decision can only be made when claim is UNDER_REVIEW")

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

    if db_claim.status != ClaimStatus.UNDER_REVIEW:
        raise HTTPException(status_code=400, detail="Decision can only be made when claim is UNDER_REVIEW")

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

@router.post("/{claim_id}/reports", response_model=ClaimResponse)
def upload_medical_report(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    claim_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    notes: Optional[str] = Form(None)
) -> Any:
    if current_user.role != UserRole.HOSPITAL_REP or not current_user.hospital:
        raise HTTPException(status_code=403, detail="Only authorized hospital representatives can upload medical reports.")

    db_claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not db_claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if db_claim.incident.locality != current_user.hospital.locality:
        raise HTTPException(status_code=403, detail="Not authorized to upload reports for this locality.")

    # File validation
    ALLOWED_MIME_TYPES = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF, JPEG, and PNG are allowed.")

    # Read file for size validation (5MB max)
    file_bytes = file.file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 5MB.")
    file.file.seek(0)

    # Secure filename
    safe_filename = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "medical_reports")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    report = ClaimMedicalReport(
        claim_id=db_claim.id,
        hospital_id=current_user.hospital_id,
        uploaded_by=current_user.id,
        file_reference=file_path,
        document_type=document_type,
        notes=notes
    )
    db.add(report)

    if db_claim.status == ClaimStatus.MEDICAL_REPORT_PENDING:
        db_claim.status = ClaimStatus.MEDICAL_REPORT_SUBMITTED
        db.add(db_claim)

    db.commit()
    db.refresh(db_claim)
    return db_claim

@router.get("/{claim_id}/reports/{report_id}/download")
def download_medical_report(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    claim_id: uuid.UUID,
    report_id: uuid.UUID,
) -> Any:
    db_claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not db_claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    report = db.query(ClaimMedicalReport).filter(
        ClaimMedicalReport.id == report_id,
        ClaimMedicalReport.claim_id == claim_id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Medical report not found")

    if current_user.role in [UserRole.INSURER, UserRole.ADMIN]:
        pass
    elif current_user.role == UserRole.HOSPITAL_REP:
        if not current_user.hospital or db_claim.incident.locality != current_user.hospital.locality:
            raise HTTPException(status_code=403, detail="Not authorized to download report for this locality")
    elif current_user.role == UserRole.RIDER:
        if db_claim.rider_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    file_path = report.file_reference
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report file not found on server")

    filename = os.path.basename(file_path)
    return FileResponse(path=file_path, filename=filename)
