from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core import security
from app.core.config import settings
from app.api import deps
from app.schemas import UserRegister, UserLogin, Token, UserResponse
from db.core.session import get_db
from db.models.user import User
from db.models.rider_profile import RiderProfile
from db.models.enums import UserRole

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
