from datetime import datetime, timezone
import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import IncidentCreate, IncidentResponse
from db.core.session import get_db, SessionLocal
from db.models.user import User
from db.models.incident import Incident
from db.models.enums import IncidentStatus, UserRole

router = APIRouter()

@router.post("", response_model=IncidentResponse)
def create_incident(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    incident_in: IncidentCreate,
    background_tasks: BackgroundTasks
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
    from db.models.claim import Claim
    recent_incident = db.query(Incident).filter(
        Incident.shift_id == incident_in.shift_id,
        Incident.detected_at >= datetime.now(timezone.utc) - timedelta(seconds=60)
    ).order_by(Incident.detected_at.desc()).first()
    
    if recent_incident:
        has_claim = db.query(Claim).filter(Claim.incident_id == recent_incident.id).first()
        if not has_claim and recent_incident.status == IncidentStatus.DETECTED:
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
    
    # Trigger background escalation verification flow
    background_tasks.add_task(run_incident_escalation, db_incident.id)
    
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

@router.post("/{incident_id}/okay", response_model=IncidentResponse)
def incident_okay(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    incident_id: uuid.UUID
) -> Any:
    db_incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    if db_incident.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to resolve this incident")
        
    db_incident.status = IncidentStatus.FALSE_POSITIVE
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return db_incident

@router.post("/{incident_id}/help", response_model=IncidentResponse)
def incident_help(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    incident_id: uuid.UUID
) -> Any:
    db_incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    if db_incident.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to escalate this incident")
        
    db_incident.status = IncidentStatus.VERIFIED_ACCIDENT
    db.add(db_incident)
    
    db.commit()
    
    # Trigger emergency voice call in background
    import asyncio
    from app.services.whatsapp_service import make_voice_call
    profile = current_user.rider_profile
    emergency_phone = profile.emergency_contact_phone if profile else None
    if emergency_phone:
        call_msg = (
            f"Emergency alert from RideShield. Our rider {current_user.full_name} has requested assistance. "
            f"Location is latitude {db_incident.latitude}, longitude {db_incident.longitude}."
        )
        asyncio.create_task(make_voice_call(emergency_phone, call_msg))
        
    db.refresh(db_incident)
    return db_incident

# -----------------------------------------------------------------------------
# Background Escalation Logic
# -----------------------------------------------------------------------------

async def check_incident_cancelled(incident_id: uuid.UUID) -> bool:
    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            return True
        from db.models.enums import IncidentStatus
        if incident.status not in [IncidentStatus.DETECTED, IncidentStatus.PENDING_VERIFICATION]:
            return True
        return False
    finally:
        db.close()

async def wait_with_check(incident_id: uuid.UUID, seconds: int) -> bool:
    import asyncio
    for _ in range(0, seconds, 5):
        await asyncio.sleep(5)
        if await check_incident_cancelled(incident_id):
            return True
    return False

async def run_incident_escalation(incident_id: uuid.UUID):
    import asyncio
    from app.services.whatsapp_service import send_whatsapp_message, send_sms_message, make_voice_call
    from db.models.enums import IncidentStatus
    
    # Step 1: Wait 60 seconds (1 minute) for Rider App response
    resolved = await wait_with_check(incident_id, 60)
    if resolved:
        print(f"[Escalation] Incident {incident_id} resolved during app countdown. Halting escalation.")
        return
        
    # Step 2: No response -> Send WhatsApp
    db = SessionLocal()
    phone = None
    rider_name = None
    lat = "19.0760"
    lng = "72.8777"
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            return
        if incident.status == IncidentStatus.DETECTED:
            incident.status = IncidentStatus.PENDING_VERIFICATION
            db.add(incident)
            db.commit()
            
        rider = incident.rider
        phone = rider.phone_number
        rider_name = rider.full_name
        if incident.latitude:
            lat = str(round(incident.latitude, 4))
        if incident.longitude:
            lng = str(round(incident.longitude, 4))
    finally:
        db.close()
        
    if not phone:
        return
        
    print(f"[Escalation] Sending WhatsApp message to rider {rider_name} ({phone})")
    whatsapp_body = (
        f"RideShield Alert! We detected a possible crash for rider {rider_name}. "
        f"Are you okay? Reply 'YES' if you are fine, or 'HELP' if you need emergency assistance."
    )
    template_params = [
        {"type": "text", "text": rider_name},
        {"type": "text", "text": lat},
        {"type": "text", "text": lng}
    ]
    sent_whatsapp = await send_whatsapp_message(phone, whatsapp_body, template_params=template_params)
    
    if sent_whatsapp:
        # Wait 60 seconds (1 minute) for WhatsApp reply
        resolved = await wait_with_check(incident_id, 60)
        if resolved:
            print(f"[Escalation] Incident {incident_id} resolved after WhatsApp message. Halting escalation.")
            return
    else:
        print(f"[Escalation] WhatsApp delivery failed. Bypassing WhatsApp wait, escalating to SMS immediately.")
        
    # Step 3: No response -> Send SMS
    print(f"[Escalation] Sending SMS message to rider {rider_name} ({phone})")
    sms_body = (
        f"RideShield EMERGENCY Warning! Possible crash detected for {rider_name}. "
        f"Reply 'YES' if okay, or 'HELP' for SOS."
    )
    await send_sms_message(phone, sms_body)
    
    # Wait 60 seconds (1 minute) for SMS reply
    resolved = await wait_with_check(incident_id, 60)
    if resolved:
        print(f"[Escalation] Incident {incident_id} resolved after SMS message. Halting escalation.")
        return
        
    # Step 4: No response -> Trigger SOS (Auto-Claim and Voice Call to Emergency Contact)
    print(f"[Escalation] Escalating incident {incident_id} to SOS. Making emergency contact voice call.")
    db = SessionLocal()
    emergency_phone = None
    lat = 0.0
    lng = 0.0
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            return
            
        incident.status = IncidentStatus.VERIFIED_ACCIDENT
        db.add(incident)
        
        db.commit()
        
        lat = incident.latitude
        lng = incident.longitude
        profile = incident.rider.rider_profile
        emergency_phone = profile.emergency_contact_phone if profile else None
    finally:
        db.close()
        
    if emergency_phone:
        call_msg = (
            f"Emergency alert from RideShield. Our rider {rider_name} has experienced a potential accident "
            f"and has not responded. Location is latitude {lat}, longitude {lng}. "
            f"Please check on them immediately."
        )
        await make_voice_call(emergency_phone, call_msg)
