from datetime import timedelta
from typing import Any
import random
import time
import redis
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core import security
from app.core.config import settings
from app.api import deps
from app.schemas import UserRegister, UserLogin, Token, UserResponse
from db.core.session import get_db
from db.models.user import User
from db.models.rider_profile import RiderProfile
from db.models.enums import UserRole
from app.services.twilio_service import send_sms_message, make_voice_call

# Try initializing Redis Client
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None

OTP_STORE = {}  # Fallback: {phone_number: {"code": str, "expires_at": float}}

class SendOTPRequest(BaseModel):
    phone_number: str

class VerifyOTPRequest(BaseModel):
    phone_number: str
    code: str

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register(
    *,
    db: Session = Depends(get_db),
    user_in: UserRegister
) -> Any:
    # Check if user already exists
    user = db.query(User).filter(
        (User.email == user_in.email) | (User.phone_number == user_in.phone_number)
    ).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email or phone number already exists.",
        )
    
    # Create user
    db_user = User(
        email=user_in.email,
        phone_number=user_in.phone_number,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role
    )
    db.add(db_user)
    db.flush()  # Get user ID

    # Create rider profile if role is RIDER
    if user_in.role == UserRole.RIDER:
        db_profile = RiderProfile(
            user_id=db_user.id,
            vehicle_type=user_in.vehicle_type or "2-wheeler",
            license_number=user_in.license_number,
            emergency_contact_phone=user_in.emergency_contact_phone,
            safety_rating=5.0,
            kyc_status="APPROVED"  # Auto-approve for hackathon demo
        )
        db.add(db_profile)
    
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=Token)
def login(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

# Also support login via JSON body for mobile app simplicity
@router.post("/login/json", response_model=Token)
def login_json(
    *,
    db: Session = Depends(get_db),
    user_in: UserLogin
) -> Any:
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not security.verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.get("/me", response_model=UserResponse)
def read_user_me(
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    return current_user

@router.post("/send-otp")
async def send_otp(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    req: SendOTPRequest
) -> Any:
    phone = req.phone_number.strip()
    otp = f"{random.randint(100000, 999999)}"
    
    stored_in_redis = False
    if redis_client:
        try:
            redis_client.setex(f"otp:{phone}", 300, otp)
            stored_in_redis = True
        except Exception as e:
            print(f"[Redis OTP Error]: {e}")
            
    if not stored_in_redis:
        OTP_STORE[phone] = {
            "code": otp,
            "expires_at": time.time() + 300
        }
    
    msg_body = f"Your RideShield verification code is: {otp}. It is valid for 5 minutes."
    success = await send_sms_message(phone, msg_body)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send verification SMS via Twilio."
        )
        
    return {"status": "success", "message": f"Verification code sent to {phone}"}

@router.post("/verify-otp")
async def verify_otp(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    req: VerifyOTPRequest
) -> Any:
    phone = req.phone_number.strip()
    code = req.code.strip()
    
    stored_code = None
    if redis_client:
        try:
            stored_code = redis_client.get(f"otp:{phone}")
        except Exception as e:
            print(f"[Redis OTP Get Error]: {e}")
            
    if stored_code is None:
        otp_data = OTP_STORE.get(phone)
        if otp_data and otp_data["expires_at"] > time.time():
            stored_code = otp_data["code"]
            
    if not stored_code or stored_code != code:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code."
        )
        
    user = db.query(User).filter(User.id == current_user.id).first()
    if user:
        user.phone_number = phone
        user.is_phone_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)
        
    if redis_client:
        try:
            redis_client.delete(f"otp:{phone}")
        except Exception:
            pass
    OTP_STORE.pop(phone, None)
    
    return {"status": "verified", "message": "Phone number verified successfully", "user": user}

@router.post("/twilio-webhook")
def twilio_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db)
):
    from db.models.incident import Incident
    from db.models.enums import IncidentStatus
    import uuid
    
    phone = From.replace("whatsapp:", "").strip()
    reply = Body.strip().upper()
    
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user:
        user = db.query(User).filter(User.phone_number.like(f"%{phone[-10:]}")).first()
        
    if not user:
        return Response(content="<Response></Response>", media_type="application/xml")
        
    incident = db.query(Incident).filter(
        Incident.rider_id == user.id,
        Incident.status.in_([IncidentStatus.DETECTED, IncidentStatus.PENDING_VERIFICATION])
    ).order_by(Incident.detected_at.desc()).first()
    
    if not incident:
        return Response(content="<Response></Response>", media_type="application/xml")
        
    if reply in ["YES", "OK", "OKAY", "RIDER OK", "I'M OKAY", "I AM OKAY"]:
        incident.status = IncidentStatus.FALSE_POSITIVE
        db.add(incident)
        db.commit()
        
        twiml = "<Response><Message>Glad to hear you are okay! We have cancelled the emergency alert.</Message></Response>"
        return Response(content=twiml, media_type="application/xml")
        
    elif reply in ["HELP", "SOS", "NEED HELP", "ASSISTANCE", "EMERGENCY"]:
        incident.status = IncidentStatus.VERIFIED_ACCIDENT
        db.add(incident)
        
        from db.models.claim import Claim
        from db.models.enums import ClaimStatus
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
        
        import asyncio
        profile = user.rider_profile
        emergency_phone = profile.emergency_contact_phone if profile else None
        if emergency_phone:
            call_msg = (
                f"Emergency alert from RideShield. Our rider {user.full_name} has requested assistance. "
                f"Location is latitude {incident.latitude}, longitude {incident.longitude}."
            )
            asyncio.create_task(make_voice_call(emergency_phone, call_msg))
            
        twiml = "<Response><Message>Emergency services and your emergency contact have been notified. Help is on the way.</Message></Response>"
        return Response(content=twiml, media_type="application/xml")
        
    return Response(content="<Response></Response>", media_type="application/xml")
