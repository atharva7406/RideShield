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
from app.services.whatsapp_service import send_sms_message, make_voice_call, normalize_phone_e164, is_test_phone_number

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
    normalized_phone = normalize_phone_e164(user_in.phone_number)
    user = db.query(User).filter(
        (User.email == user_in.email) | (User.phone_number == normalized_phone)
    ).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email or phone number already exists.",
        )
    
    # Create user
    db_user = User(
        email=user_in.email,
        phone_number=normalized_phone,
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
    elif user_in.role == UserRole.HOSPITAL_REP:
        latitude = 19.0760
        longitude = 72.8777
        try:
            import httpx
            headers = {"User-Agent": "RideShield-SIH2026-Hackathon-HospitalRegistration"}
            geo_response = httpx.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": user_in.hospital_address or "Mumbai", "format": "json", "limit": 1},
                headers=headers,
                timeout=5.0
            )
            if geo_response.status_code == 200:
                geo_data = geo_response.json()
                if geo_data:
                    latitude = float(geo_data[0]["lat"])
                    longitude = float(geo_data[0]["lon"])
                    print(f"[Hospital Geocoding] Resolved '{user_in.hospital_address}' to {latitude}, {longitude}")
        except Exception as e:
            print(f"[Hospital Geocoding Exception]: {e}")
            
        import uuid
        from db.models.hospital import Hospital
        db_hospital = Hospital(
            id=uuid.uuid4(),
            name=user_in.hospital_name or "General Hospital",
            locality=user_in.hospital_address or "Unknown Address",
            contact_number=user_in.hospital_phone or user_in.phone_number,
            latitude=latitude,
            longitude=longitude
        )
        db.add(db_hospital)
        db.flush()
        db_user.hospital_id = db_hospital.id
        db.add(db_user)
    
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
    normalized_phone = normalize_phone_e164(phone)
    
    # Test bypass validation
    if is_test_phone_number(normalized_phone):
        otp = "123456"
        stored_in_redis = False
        if redis_client:
            try:
                redis_client.setex(f"otp:{normalized_phone}", 300, otp)
                stored_in_redis = True
            except Exception as e:
                print(f"[Redis OTP Error]: {e}")
        if not stored_in_redis:
            OTP_STORE[normalized_phone] = {
                "code": otp,
                "expires_at": time.time() + 300
            }
        print(f"[FREE OTP TEST BYPASS] Test phone number {normalized_phone} auto-verifies with code: {otp}")
        return {"status": "success", "message": "Verification code sent (Test Bypass Mode)."}
        
    otp = f"{random.randint(100000, 999999)}"
    
    stored_in_redis = False
    if redis_client:
        try:
            redis_client.setex(f"otp:{normalized_phone}", 300, otp)
            stored_in_redis = True
        except Exception as e:
            print(f"[Redis OTP Error]: {e}")
            
    if not stored_in_redis:
        OTP_STORE[normalized_phone] = {
            "code": otp,
            "expires_at": time.time() + 300
        }
    
    msg_body = f"Your RideShield verification code is: {otp}. It is valid for 5 minutes."
    # Send a real SMS containing the OTP code
    success = await send_sms_message(normalized_phone, msg_body)
    
    if not success:
        print("="*60)
        print("[SMS ERROR FALLBACK] Failed to send SMS.")
        print(f"Fallback verification code generated: {otp}")
        print("="*60)
        
    return {"status": "success", "message": f"Verification code sent. (Fallback: read from terminal console if SMS provider failed)"}

@router.post("/verify-otp")
async def verify_otp(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    req: VerifyOTPRequest
) -> Any:
    phone = req.phone_number.strip()
    code = req.code.strip()
    normalized_phone = normalize_phone_e164(phone)
    
    # Test bypass validation
    if is_test_phone_number(normalized_phone) and code == "123456":
        stored_code = "123456"
    else:
        stored_code = None
        if redis_client:
            try:
                stored_code = redis_client.get(f"otp:{normalized_phone}")
            except Exception as e:
                print(f"[Redis OTP Get Error]: {e}")
                
        if stored_code is None:
            otp_data = OTP_STORE.get(normalized_phone)
            if otp_data and otp_data["expires_at"] > time.time():
                stored_code = otp_data["code"]
                
    if not stored_code or stored_code != code:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code."
        )
        
    user = db.query(User).filter(User.id == current_user.id).first()
    if user:
        user.phone_number = normalized_phone
        user.is_phone_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)
        
    if redis_client:
        try:
            redis_client.delete(f"otp:{normalized_phone}")
        except Exception:
            pass
    OTP_STORE.pop(normalized_phone, None)
    
    return {"status": "verified", "message": "Phone number verified successfully", "user": UserResponse.model_validate(user)}
