from datetime import datetime, timezone
import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import CrashWindowResponse, CrashWindowSubmission, IncidentCreate, IncidentResponse
from app.services import ml_scoring_service
from db.core.session import get_db
from db.models.user import User
from db.models.shift import Shift
from db.models.incident import Incident
from db.models.enums import IncidentStatus, UserRole

router = APIRouter()

@router.post("", response_model=IncidentResponse)
def create_incident(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    incident_in: IncidentCreate
) -> Any:
    # rider_id is always derived from the authenticated token — never trusted from client
    rider_id = current_user.id

    # Only RIDERs and ADMINs may create incidents
    if current_user.role not in [UserRole.RIDER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=403,
            detail="Only riders may report incidents"
        )
    
    # Duplicate Protection: Ignore new incidents for the same shift within the last 60 seconds
    from datetime import timedelta
    recent_incident = db.query(Incident).filter(
        Incident.shift_id == incident_in.shift_id,
        Incident.detected_at >= datetime.now(timezone.utc) - timedelta(seconds=60)
    ).first()
    
    if recent_incident:
        # Return the existing recent incident instead of creating a duplicate
        return recent_incident
    
    db_incident = Incident(
        shift_id=incident_in.shift_id,
        rider_id=rider_id,
        status=IncidentStatus.DETECTED,
        peak_g_force=incident_in.peak_g_force,
        confidence_score=incident_in.confidence_score,
        latitude=incident_in.latitude,
        longitude=incident_in.longitude,
        detected_at=datetime.now(timezone.utc)
    )
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return db_incident

@router.post("/from-window", response_model=CrashWindowResponse)
def create_incident_from_window(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    submission: CrashWindowSubmission
) -> Any:
    """
    On-device Tier-0 candidate reporting WITH the raw sensor window — the
    CrashDetector's rolling ~5s buffer, already held in memory on-device
    for local detection, sent here instead of only the collapsed summary
    POST /incidents accepts. Lets the backend re-score with the trained ML
    model and compute peak_g_force/confidence from the window itself,
    rather than trusting client-supplied numbers the way the sparse path
    has to.

    ML available -> ml_scoring_service returns a calibrated
    crash_probability from the model. ML unavailable, model missing, or
    scoring throws for any reason -> transparently falls back to the same
    G-force-threshold rule telemetry_service.py's ingest path already
    uses, computed from this window's own data. See
    app/services/ml_scoring_service.py's module docstring — this fallback
    is a hard contract, not a best-effort detail: the ML layer must never
    be a single point of failure for crash detection.
    """
    if current_user.role not in [UserRole.RIDER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only riders may report incidents")

    shift = db.query(Shift).filter(Shift.id == submission.shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if current_user.role == UserRole.RIDER and shift.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to report an incident for this shift")

    # Duplicate protection, same window as POST /incidents.
    from datetime import timedelta
    recent_incident = db.query(Incident).filter(
        Incident.shift_id == submission.shift_id,
        Incident.detected_at >= datetime.now(timezone.utc) - timedelta(seconds=60)
    ).first()
    if recent_incident:
        return CrashWindowResponse(
            incident_id=recent_incident.id,
            confidence_score=float(recent_incident.confidence_score),
            scoring_method="duplicate_suppressed",
            predicted_class=None,
        )

    scoring = ml_scoring_service.score_window(
        shift_id=str(submission.shift_id),
        accel_samples=[s.model_dump() for s in submission.accel_samples],
        gyro_samples=[s.model_dump() for s in submission.gyro_samples],
        gps_samples=[s.model_dump() for s in submission.gps_samples],
    )
    if scoring is None:
        raise HTTPException(status_code=422, detail="Submitted window has too few accel samples to score (need >= 3)")

    gps_samples = submission.gps_samples
    avg_lat = sum(s.latitude for s in gps_samples) / len(gps_samples) if gps_samples else 0.0
    avg_lng = sum(s.longitude for s in gps_samples) / len(gps_samples) if gps_samples else 0.0

    db_incident = Incident(
        shift_id=submission.shift_id,
        rider_id=shift.rider_id,
        status=IncidentStatus.DETECTED,
        peak_g_force=scoring["peak_g_force"],
        confidence_score=scoring["confidence_score"],
        latitude=avg_lat,
        longitude=avg_lng,
        detected_at=datetime.now(timezone.utc)
    )
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    return CrashWindowResponse(
        incident_id=db_incident.id,
        confidence_score=scoring["confidence_score"],
        scoring_method=scoring["method"],
        predicted_class=scoring["predicted_class"],
    )

@router.get("", response_model=List[IncidentResponse])
def read_incidents(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    if current_user.role in [UserRole.INSURER, UserRole.ADMIN, UserRole.SUPPORT]:
        incidents = db.query(Incident).all()
    else:
        incidents = db.query(Incident).filter(Incident.rider_id == current_user.id).all()
    return incidents

@router.get("/{incident_id}", response_model=IncidentResponse)
def read_incident(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    incident_id: uuid.UUID
) -> Any:
    db_incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    if current_user.role == UserRole.RIDER and db_incident.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this incident")
        
    return db_incident
