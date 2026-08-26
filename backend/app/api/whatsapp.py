import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy.orm import Session
from db.core.session import get_db
from db.models.user import User
from db.models.incident import Incident
from db.models.enums import IncidentStatus
from db.models.claim import Claim
from db.models.enums import ClaimStatus
from app.core.config import settings
from app.services.whatsapp_service import (
    send_whatsapp_message,
    make_voice_call,
    normalize_phone_e164,
)
from app.services import incident_decision_engine as decision_engine

router = APIRouter()

async def handle_chatbot_message(user: User, reply: str, db: Session):
    """
    Process inbound messages to verify incident status and trigger alerts if needed.
    """
    reply_upper = reply.strip().upper()
    
    # Look for active incidents that need confirmation
    incident = (
        db.query(Incident)
        .filter(
            Incident.rider_id == user.id,
            Incident.status.in_([IncidentStatus.DETECTED, IncidentStatus.PENDING_VERIFICATION]),
        )
        .order_by(Incident.detected_at.desc())
        .first()
    )
    
    if not incident:
        print(f"[WhatsApp Chatbot] No active incident found for user: {user.full_name}")
        return

    # Check positive / safety check replies
    if reply_upper in ["YES", "OK", "OKAY", "RIDER OK", "I'M OKAY", "I AM OKAY", "OK - I'M SAFE"]:
        # Rider's explicit word is authoritative — see incident_decision_engine.py.
        incident.status = decision_engine.resolve_verdict(
            rider_response="okay",
            confidence_label=incident.decision_confidence or "low",
        )
        db.add(incident)
        db.commit()
        
        reply_text = "Ride Safe!!"
        await send_whatsapp_message(user.phone_number, reply_text)
        print(f"[WhatsApp Chatbot] Incident {incident.id} marked as FALSE_POSITIVE by rider confirmation.")
        
    # Check SOS / Emergency replies
    elif reply_upper in ["HELP", "SOS", "NEED HELP", "ASSISTANCE", "EMERGENCY", "HELP - NEED HELP"]:
        # Rider's explicit word is authoritative — see incident_decision_engine.py.
        incident.status = decision_engine.resolve_verdict(
            rider_response="help",
            confidence_label=incident.decision_confidence or "low",
        )
        db.add(incident)
        
        # File emergency claim automatically
        existing_claim = db.query(Claim).filter(Claim.incident_id == incident.id).first()
        if not existing_claim:
            claim_num = f"CLM-SOS-{uuid.uuid4().hex[:8].upper()}"
            db_claim = Claim(
                incident_id=incident.id,
                rider_id=incident.rider_id,
                shift_id=incident.shift_id,
                claim_number=claim_num,
                status=ClaimStatus.SUBMITTED,
                claimed_amount=10000.0
            )
            db.add(db_claim)
            
        db.commit()
        
        # Trigger emergency voice call in the background to emergency contact
        profile = user.rider_profile
        emergency_phone = profile.emergency_contact_phone if profile else None
        if emergency_phone:
            call_msg = (
                f"Emergency alert from RideShield. Our rider {user.full_name} has requested assistance. "
                f"Location is latitude {incident.latitude}, longitude {incident.longitude}."
            )
            # Run background task
            asyncio.create_task(make_voice_call(emergency_phone, call_msg))
            
        reply_text = "Emergency services are on the way"
        await send_whatsapp_message(user.phone_number, reply_text)
        print(f"[WhatsApp Chatbot] Incident {incident.id} escalated to VERIFIED_ACCIDENT. SOS triggered.")

@router.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    GET endpoint for Meta Webhook Verification.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        print("[WhatsApp Webhook] Verification successful!")
        return Response(content=hub_challenge, media_type="text/plain")
    
    print("[WhatsApp Webhook] Verification failed due to token mismatch.")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@router.post("/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    POST endpoint for Inbound Message Ingestion from Meta.
    """
    try:
        payload = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=400)

    # Inbound payload parsing according to Meta webhook guidelines
    entries = payload.get("entry", [])
    if not entries:
        return Response(content="EVENT_RECEIVED", status_code=200)

    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            
            # 1. Ignore status updates (e.g. read, delivered) to prevent 500 errors
            if "statuses" in value:
                continue
                
            messages = value.get("messages", [])
            if not messages:
                continue
                
            for msg in messages:
                # 2. Ignore non-text messages gracefully (e.g. images, audio, reactions)
                msg_type = msg.get("type")
                if msg_type != "text":
                    continue
                
                sender_phone = msg.get("from")
                text_obj = msg.get("text", {})
                message_body = text_obj.get("body", "")
                
                if not sender_phone or not message_body:
                    continue
                
                # Normalize phone and lookup user profile
                normalized_sender = normalize_phone_e164(sender_phone)
                user = db.query(User).filter(User.phone_number == normalized_sender).first()
                if not user:
                    # Fallback lookup (match last 10 digits)
                    user = db.query(User).filter(User.phone_number.like(f"%{normalized_sender[-10:]}")).first()
                    
                if not user:
                    print(f"[WhatsApp Webhook] Received message from unrecognized phone number: {normalized_sender}")
                    continue
                
                # 3. Pass message to safety confirmation handler
                await handle_chatbot_message(user, message_body, db)

    return Response(content="EVENT_RECEIVED", status_code=200)
