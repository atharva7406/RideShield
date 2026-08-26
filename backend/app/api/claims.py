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

    # Check if a claim already exists for this incident
    existing_claim = db.query(Claim).filter(Claim.incident_id == claim_in.incident_id).first()
    if existing_claim:
        attach_extra_fields(existing_claim, db)
        return existing_claim

    claim_num = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    db_claim = Claim(
        id=uuid.uuid4(),
        incident_id=claim_in.incident_id,
        rider_id=incident.rider_id,
        shift_id=incident.shift_id,
        claim_number=claim_num,
        status=ClaimStatus.MEDICAL_REPORT_PENDING,
        claimed_amount=claim_in.claimed_amount,
        filed_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(db_claim)

    from db.models.audit import AuditEvent
    audit = AuditEvent(
        id=uuid.uuid4(),
        performed_by_user_id=current_user.id,
        claim_id=db_claim.id,
        entity_type="claim",
        entity_id=db_claim.id,
        event_type="CLAIM_SUBMITTED",
        new_state=ClaimStatus.MEDICAL_REPORT_PENDING,
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()
    db.refresh(db_claim)
    attach_extra_fields(db_claim, db)
    return db_claim

@router.get("", response_model=List[ClaimResponse])
def read_claims(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    if current_user.role in [UserRole.INSURER, UserRole.ADMIN, UserRole.SUPPORT]:
        claims = db.query(Claim).all()
    elif current_user.role == UserRole.HOSPITAL_REP:
        hospital = current_user.hospital
        h_lat = hospital.latitude if (hospital and hospital.latitude is not None) else 19.0760
        h_lng = hospital.longitude if (hospital and hospital.longitude is not None) else 72.8777

        # Query active/submitted claims
        all_claims = db.query(Claim).join(Incident).filter(
            Claim.status.in_([
                ClaimStatus.SUBMITTED,
                ClaimStatus.MEDICAL_REPORT_PENDING,
                ClaimStatus.MEDICAL_REPORT_SUBMITTED,
                ClaimStatus.UNDER_REVIEW
            ])
        ).all()

        from datetime import timedelta
        now = datetime.now(timezone.utc)
        four_hours_ago = now - timedelta(hours=4.0)
        nearby_claims = []
        
        for claim in all_claims:
            incident = claim.incident
            if incident and incident.latitude is not None and incident.longitude is not None:
                det = incident.detected_at
                if det and det.tzinfo is None:
                    det = det.replace(tzinfo=timezone.utc)
                
                # Rule 1: Incident detected within past 4 hours
                if det and det >= four_hours_ago:
                    inc_lat = incident.latitude
                    inc_lng = incident.longitude
                    
                    # Rule 2: Strict 5km radius (or mock test coordinates 0,0 if testing on emulator)
                    if (inc_lat == 0.0 and inc_lng == 0.0) or (abs(inc_lat) < 0.01 and abs(inc_lng) < 0.01):
                        nearby_claims.append(claim)
                    else:
                        dist = haversine_distance(h_lat, h_lng, inc_lat, inc_lng)
                        if dist <= 5.0:
                            nearby_claims.append(claim)

        claims = nearby_claims
    else:
        claims = db.query(Claim).filter(Claim.rider_id == current_user.id).all()
        
    for c in claims:
        attach_extra_fields(c, db)
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

    attach_extra_fields(db_claim, db)
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


import math

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # radius of earth in km
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def run_claim_verification(claim_id: uuid.UUID, db: Session):
    from db.models.claim import Claim
    from db.models.enums import ClaimStatus
    from db.models.audit import AuditEvent
    from db.models.evidence import IncidentEvidence
    import json
    
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return
        
    incident = claim.incident
    rider = claim.rider
    
    # 1. Telemetry confidence
    telemetry_conf = float(incident.confidence_score) if incident else 0.5
    
    # 2. Hospital report evidence
    hospital_match_score = 0.0
    hospital_report = db.query(IncidentEvidence).filter(
        IncidentEvidence.claim_id == claim_id,
        IncidentEvidence.file_type == "hospital_report"
    ).first()
    
    time_diff_hours = 0.0
    if hospital_report:
        hospital_match_score = 0.5  # Base score for report presence
        try:
            report_data = json.loads(hospital_report.file_url)
            # Time match check
            admission_time_str = report_data.get("admission_timestamp")
            if admission_time_str:
                admission_time = datetime.fromisoformat(admission_time_str.replace("Z", "+00:00"))
                incident_time = incident.detected_at
                time_diff = abs((admission_time - incident_time).total_seconds()) / 3600.0
                time_diff_hours = time_diff
                if time_diff <= 2.0:
                    hospital_match_score += 0.3
                elif time_diff <= 4.0:
                    hospital_match_score += 0.15
            # Identity match check
            patient_id = report_data.get("patient_identifier", "").lower()
            if rider and (rider.full_name.lower() in patient_id or patient_id in rider.full_name.lower()):
                hospital_match_score += 0.2
        except Exception as e:
            print(f"[Verification Error] Failed to parse hospital report: {e}")
            
    # 3. Rider trust score
    rider_trust = 1.0
    if rider and rider.rider_profile:
        rider_trust = float(rider.rider_profile.safety_rating) / 5.0
        
    # Final weighted score
    final_score = (telemetry_conf * 0.4) + (hospital_match_score * 0.4) + (rider_trust * 0.2)
    
    # Store verification status
    old_status = claim.status
    if final_score >= 0.7:
        claim.status = ClaimStatus.APPROVED
        claim.approved_amount = claim.claimed_amount
    else:
        claim.status = ClaimStatus.UNDER_REVIEW
        
    db.add(claim)
    
    # Audit log
    audit = AuditEvent(
        id=uuid.uuid4(),
        performed_by_user_id=rider.id if rider else None,
        claim_id=claim.id,
        entity_type="claim",
        entity_id=claim.id,
        event_type="CLAIM_VERIFICATION_RUN",
        old_state=old_status,
        new_state=claim.status,
        metadata_json={
            "verification_score": round(final_score, 3),
            "telemetry_confidence": telemetry_conf,
            "hospital_match_score": hospital_match_score,
            "rider_trust_score": rider_trust,
            "time_difference_hours": round(time_diff_hours, 2)
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()


from pydantic import BaseModel

class HospitalReportCreate(BaseModel):
    patient_identifier: str
    injury_description: str
    admission_timestamp: datetime
    facility_name: str

@router.post("/{claim_id}/hospital-report")
def submit_hospital_report(
    claim_id: uuid.UUID,
    report: HospitalReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    import json
    report_data = {
        "patient_identifier": report.patient_identifier,
        "injury_description": report.injury_description,
        "admission_timestamp": report.admission_timestamp.isoformat(),
        "facility_name": report.facility_name
    }
    
    from db.models.evidence import IncidentEvidence
    evidence = IncidentEvidence(
        id=uuid.uuid4(),
        incident_id=claim.incident_id,
        claim_id=claim.id,
        file_url=json.dumps(report_data),
        file_type="hospital_report",
        uploaded_at=datetime.now(timezone.utc)
    )
    db.add(evidence)
    
    # Update claim status
    claim.status = ClaimStatus.MEDICAL_REPORT_SUBMITTED
    db.add(claim)
    db.commit()
    
    # Trigger verification logic
    run_claim_verification(claim.id, db)
    
    db.refresh(claim)
    # Populate extra fields before return
    attach_extra_fields(claim, db)
    return claim


@router.get("/lookup/{claim_number}", response_model=ClaimResponse)
def lookup_claim_by_code(
    claim_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    # Normalize search term
    search_code = claim_number.strip().upper()
    
    # 1. Try exact match
    claim = db.query(Claim).filter(Claim.claim_number == search_code).first()
    
    # 2. Try case-insensitive comparison
    if not claim:
        from sqlalchemy import func
        claim = db.query(Claim).filter(func.upper(Claim.claim_number) == search_code).first()
        
    # 3. Try matches stripping CLM- prefix
    if not claim:
        stripped = search_code.replace("CLM-", "").replace("CLM", "").replace("-", "")
        claim = db.query(Claim).filter(
            (Claim.claim_number.like(f"%{stripped}")) |
            (func.upper(Claim.claim_number).like(f"%{stripped}%"))
        ).first()
        
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    attach_extra_fields(claim, db)
    return claim


def attach_extra_fields(claim: Claim, db: Session):
    from db.models.evidence import IncidentEvidence
    from db.models.audit import AuditEvent
    
    # Retrieve evidence linked to the claim/incident
    evidence_list = db.query(IncidentEvidence).filter(
        (IncidentEvidence.claim_id == claim.id) | 
        ((IncidentEvidence.incident_id == claim.incident_id) & (IncidentEvidence.claim_id == None))
    ).all()
    claim.evidence = evidence_list
    
    # Retrieve verification score from AuditEvent
    verification_score = None
    audit = db.query(AuditEvent).filter(
        AuditEvent.claim_id == claim.id,
        AuditEvent.event_type == "CLAIM_VERIFICATION_RUN"
    ).order_by(AuditEvent.created_at.desc()).first()
    if audit and audit.metadata_json:
        verification_score = audit.metadata_json.get("verification_score")
    claim.verification_score = verification_score
