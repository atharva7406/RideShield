from datetime import datetime, timezone
import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import IncidentCreate, IncidentResponse
from db.core.session import get_db
from db.models.user import User
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
