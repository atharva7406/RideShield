from datetime import datetime, timezone
import uuid
from typing import Any, List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas import CrashWindowResponse, CrashWindowSubmission, IncidentCreate, IncidentResponse
from app.services import ml_scoring_service
from app.services import window_quality_service
from app.services import incident_decision_engine as decision_engine
from db.core.session import get_db, SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.incident import Incident
from db.models.enums import IncidentStatus, UserRole

router = APIRouter()


def _recent_incident_for_shift(db: Session, shift_id) -> Incident | None:
    """Duplicate-suppression check shared by both incident-creation paths
    (POST /incidents and POST /incidents/from-window) — the Tier-0-only
    sparse path and the ML-scored window path are two ways of reporting
    the SAME kind of event and must apply the identical dedup rule, or a
    rider could end up with two open incidents for one real crash just
    because one report came in offline (sparse) and the retry came in
    online (windowed), or vice versa.

    A recent incident only suppresses a new one if it's still exactly
    where a duplicate-check makes sense: no claim filed yet AND still in
    the raw DETECTED state. Once escalation has moved it to
    PENDING_VERIFICATION/VERIFIED_ACCIDENT, or a claim already exists, a
    fresh trigger within the same 60s window is treated as a new,
    separate report rather than silently swallowed.
    """
    from datetime import timedelta
    from db.models.claim import Claim

    recent = (
        db.query(Incident)
        .filter(
            Incident.shift_id == shift_id,
            Incident.detected_at >= datetime.now(timezone.utc) - timedelta(seconds=60),
        )
        .order_by(Incident.detected_at.desc())
        .first()
    )
    if recent is None:
        return None
    has_claim = db.query(Claim).filter(Claim.incident_id == recent.id).first()
    if not has_claim and recent.status == IncidentStatus.DETECTED:
        return recent
    return None


@router.post("", response_model=IncidentResponse)
def create_incident(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    incident_in: IncidentCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    # rider_id is always derived from the authenticated token — never trusted from client
    rider_id = current_user.id

    # Only RIDERs and ADMINs may create incidents
    if current_user.role not in [UserRole.RIDER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=403,
            detail="Only riders may report incidents"
        )

    recent_incident = _recent_incident_for_shift(db, incident_in.shift_id)
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

    # Converge into the same L1->L2->L3 verification/escalation workflow
    # as the ML-scored /from-window path below — same Incident Decision
    # Engine regardless of which path detected the event.
    background_tasks.add_task(run_incident_escalation, db_incident.id)

    return db_incident

@router.post("/from-window", response_model=CrashWindowResponse)
def create_incident_from_window(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    submission: CrashWindowSubmission,
    background_tasks: BackgroundTasks,
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

    # Phase 2 (exactly-once sync) — idempotency fast path: an offline-queued
    # incident retries with the SAME client_incident_id every attempt (see
    # rider-app/src/services/incidentSync.ts). If that exact ID already
    # exists, this retry is the same physical crash being re-synced, not a
    # new event — return the existing incident and do NOT re-trigger
    # escalation (a retry must never restart L1/L2/L3, see below) or create
    # a second row. This check alone is only a fast path, not the
    # guarantee — see the IntegrityError handling below for why.
    if submission.client_incident_id:
        existing = (
            db.query(Incident)
            .filter(Incident.client_incident_id == submission.client_incident_id)
            .first()
        )
        if existing:
            return CrashWindowResponse(
                incident_id=existing.id,
                confidence_score=float(existing.confidence_score),
                scoring_method="duplicate_suppressed",
                predicted_class=None,
            )

    # Duplicate protection — same rule as POST /incidents (see
    # _recent_incident_for_shift's docstring for why these two paths must
    # share one dedup rule). Still needed as a fallback for submissions with
    # no client_incident_id (old app builds, or the plain POST /incidents
    # path) — the exact-ID check above is authoritative when an ID is
    # present, this heuristic covers everything else.
    recent_incident = _recent_incident_for_shift(db, submission.shift_id)
    if recent_incident:
        return CrashWindowResponse(
            incident_id=recent_incident.id,
            confidence_score=float(recent_incident.confidence_score),
            scoring_method="duplicate_suppressed",
            predicted_class=None,
        )

    accel_dicts = [s.model_dump() for s in submission.accel_samples]
    gyro_dicts = [s.model_dump() for s in submission.gyro_samples]
    gps_dicts = [s.model_dump() for s in submission.gps_samples]

    # Phase 4 — server-computed independently of any client-supplied
    # window_metadata (see window_quality_service.py's docstring for why).
    window_quality = window_quality_service.assess_window_quality(accel_dicts, gyro_dicts, gps_dicts)

    scoring = ml_scoring_service.score_window(
        shift_id=str(submission.shift_id),
        accel_samples=accel_dicts,
        gyro_samples=gyro_dicts,
        gps_samples=gps_dicts,
    )
    if scoring is None:
        raise HTTPException(status_code=422, detail="Submitted window has too few accel samples to score (need >= 3)")

    # Fuses the ML score with window quality and the Tier-0-style
    # corroborating signals ml_scoring_service now surfaces — see
    # incident_decision_engine.py's module docstring. Annotation only at
    # this point: status is still DETECTED, unchanged from before Phase 4.
    evidence = decision_engine.assess_evidence_confidence(
        scoring_method=scoring["method"],
        confidence_score=scoring["confidence_score"],
        peak_g_force=scoring["peak_g_force"],
        window_quality=window_quality.quality,
        post_impact_stillness=scoring["post_impact_stillness"],
        speed_drop=scoring["speed_drop"],
    )

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
        detected_at=datetime.now(timezone.utc),
        client_incident_id=submission.client_incident_id,
        window_quality=window_quality.quality,
        decision_confidence=evidence.confidence_label,
        decision_evidence=",".join(evidence.evidence)[:500],
    )
    db.add(db_incident)
    try:
        db.commit()
    except IntegrityError:
        # The real race-condition guard: two concurrent retries with the
        # same client_incident_id can both pass the lookup above (neither
        # sees the other's uncommitted row) and both reach this insert —
        # the DB's unique constraint on client_incident_id is what actually
        # ensures only one wins. The loser lands here: roll back its own
        # failed insert, fetch the winner's row, and return that instead of
        # creating a second Incident or (critically) starting a second
        # escalation ladder for the same physical crash.
        db.rollback()
        if submission.client_incident_id:
            existing = (
                db.query(Incident)
                .filter(Incident.client_incident_id == submission.client_incident_id)
                .first()
            )
            if existing:
                return CrashWindowResponse(
                    incident_id=existing.id,
                    confidence_score=float(existing.confidence_score),
                    scoring_method="duplicate_suppressed",
                    predicted_class=None,
                )
        raise
    db.refresh(db_incident)

    background_tasks.add_task(run_incident_escalation, db_incident.id)

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

@router.post("/{incident_id}/okay", response_model=IncidentResponse)
def incident_okay(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    incident_id: uuid.UUID
) -> Any:
    """Rider confirms they're fine — the L1 (in-app) resolution path.
    Setting status away from DETECTED/PENDING_VERIFICATION is what
    check_incident_cancelled() below watches for to halt escalation."""
    db_incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if db_incident.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to resolve this incident")

    # Rider's explicit word is authoritative — see incident_decision_engine.py.
    db_incident.status = decision_engine.resolve_verdict(
        rider_response="okay",
        confidence_label=db_incident.decision_confidence or "low",
    )
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return db_incident

def trigger_auto_claim(incident, db: Session):
    from db.models.claim import Claim
    from db.models.enums import ClaimStatus
    from db.models.audit import AuditEvent
    import random
    import string
    
    # Check if a claim already exists for this incident
    existing_claim = db.query(Claim).filter(Claim.incident_id == incident.id).first()
    if existing_claim:
        return existing_claim
        
    # Generate unique 6-8 char alphanumeric claim reference code
    claim_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Check uniqueness
    while db.query(Claim).filter(Claim.claim_number == claim_num).first() is not None:
        claim_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
    # Resolve coverage limits based on the shift's premium: 3->10k, 5->25k, 7->50k, 10->100k
    from db.models.shift import Shift
    shift = db.query(Shift).filter(Shift.id == incident.shift_id).first()
    premium = shift.premium_amount if shift else 5.0
    p = int(round(premium))
    if p <= 3:
        coverage = 10000.0
    elif p <= 5:
        coverage = 25000.0
    elif p <= 7:
        coverage = 50000.0
    else:
        coverage = 100000.0

    db_claim = Claim(
        id=uuid.uuid4(),
        incident_id=incident.id,
        rider_id=incident.rider_id,
        shift_id=incident.shift_id,
        claim_number=claim_num,
        status=ClaimStatus.SUBMITTED,
        claimed_amount=coverage,
        filed_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(db_claim)
    
    # Log audit event for claim submission
    audit = AuditEvent(
        id=uuid.uuid4(),
        performed_by_user_id=incident.rider_id,
        claim_id=db_claim.id,
        entity_type="claim",
        entity_id=db_claim.id,
        event_type="CLAIM_AUTO_GENERATED",
        new_state=ClaimStatus.SUBMITTED,
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()
    db.refresh(db_claim)
    print(f"[Claim Auto-Gen] Generated claim {claim_num} for incident {incident.id}")
    return db_claim

@router.post("/{incident_id}/help", response_model=IncidentResponse)
def incident_help(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    incident_id: uuid.UUID
) -> Any:
    """Rider explicitly requests help — an immediate, manual escalation
    to VERIFIED_ACCIDENT + emergency-contact voice call, bypassing the
    automated wait/WhatsApp/SMS ladder below (they don't need to be
    asked if they're okay; they already said no)."""
    db_incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if db_incident.rider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to escalate this incident")

    # Rider's explicit word is authoritative — see incident_decision_engine.py.
    db_incident.status = decision_engine.resolve_verdict(
        rider_response="help",
        confidence_label=db_incident.decision_confidence or "low",
    )
    db.add(db_incident)

    db.commit()

    # Auto-generate claim (downstream of the verdict — see incident_decision_engine.py)
    trigger_auto_claim(db_incident, db)

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
# Background Escalation Logic — the L1 (WhatsApp) -> L2 (SMS) -> L3 (voice
# call to emergency contact) verification/escalation ladder. This is the
# single Incident Decision Engine both incident-creation paths above
# (sparse POST /incidents and ML-scored POST /incidents/from-window)
# converge into via background_tasks.add_task(run_incident_escalation, ...)
# — neither path implements its own separate escalation logic.
# -----------------------------------------------------------------------------

async def check_incident_cancelled(incident_id: uuid.UUID) -> bool:
    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            return True
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

    # Step 4: No response -> Trigger SOS (voice call to emergency contact)
    print(f"[Escalation] Escalating incident {incident_id} to SOS. Making emergency contact voice call.")
    db = SessionLocal()
    emergency_phone = None
    lat_f = 0.0
    lng_f = 0.0
    evidence_summary = None
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            return

        # No response through the entire ladder — the unconditional safety
        # floor. resolve_verdict() always returns VERIFIED_ACCIDENT here
        # regardless of decision_confidence; see incident_decision_engine.py.
        incident.status = decision_engine.resolve_verdict(
            rider_response="no_response",
            confidence_label=incident.decision_confidence or "low",
        )
        db.add(incident)

        db.commit()

        # Auto-generate claim on escalation (downstream of the verdict)
        trigger_auto_claim(incident, db)

        lat_f = incident.latitude
        lng_f = incident.longitude
        evidence_summary = incident.decision_evidence
        profile = incident.rider.rider_profile
        emergency_phone = profile.emergency_contact_phone if profile else None
    finally:
        db.close()

    if emergency_phone:
        evidence_clause = (
            f" Supporting evidence: {evidence_summary}." if evidence_summary else ""
        )
        call_msg = (
            f"Emergency alert from RideShield. Our rider {rider_name} has experienced a potential accident "
            f"and has not responded. Location is latitude {lat_f}, longitude {lng_f}."
            f"{evidence_clause} Please check on them immediately."
        )
        await make_voice_call(emergency_phone, call_msg)


from pydantic import BaseModel

class SosPayload(BaseModel):
    incident_id: uuid.UUID
    live_gps: dict
    rider_id: uuid.UUID
    triggered_at: datetime

@router.post("/{incident_id}/sos")
def trigger_sos(
    *,
    db: Session = Depends(get_db),
    incident_id: uuid.UUID,
    payload: SosPayload,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    # Fetch incident
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    # Transition status — routed through the single decision authority, same
    # as incident_okay/incident_help/the chatbot handler, per the "rider's
    # explicit word is authoritative" rule in incident_decision_engine.py.
    # Manual SOS is functionally the same signal as tapping "I need help".
    incident.status = decision_engine.resolve_verdict(
        rider_response="help",
        confidence_label=incident.decision_confidence or "low",
    )
    db.add(incident)

    # Log audit event
    from db.models.audit import AuditEvent
    audit = AuditEvent(
        id=uuid.uuid4(),
        performed_by_user_id=current_user.id,
        entity_type="incident",
        entity_id=incident_id,
        event_type="SOS_TRIGGERED",
        new_state=incident.status,
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()
    db.refresh(incident)
    
    # Auto-generate claim
    trigger_auto_claim(incident, db)
    
    # Send Twilio SMS to emergency contact (background task)
    from app.services.whatsapp_service import send_emergency_sms
    background_tasks.add_task(
        send_emergency_sms,
        rider_id=incident.rider_id,
        incident_id=incident_id,
        lat=incident.latitude,
        lng=incident.longitude,
        db=db
    )
    
    return {"status": "ok", "message": "SOS triggered successfully"}
