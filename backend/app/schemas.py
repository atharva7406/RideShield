from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, EmailStr, Field
from db.models.enums import UserRole, ShiftStatus, IncidentStatus, RiskLevel, ClaimStatus, PaymentStatus, PaymentType

# User Schemas
class UserRegister(BaseModel):
    email: EmailStr
    phone_number: str
    password: str
    full_name: str
    role: UserRole = UserRole.RIDER
    vehicle_type: Optional[str] = "2-wheeler"
    license_number: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

# RiderProfile Schema
class RiderProfileResponse(BaseModel):
    id: uuid.UUID
    vehicle_type: str
    license_number: Optional[str]
    emergency_contact_phone: Optional[str]
    safety_rating: float
    kyc_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# UserResponse Schema
class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    phone_number: str
    full_name: str
    role: UserRole
    is_active: bool
    wallet_balance: float
    created_at: datetime
    updated_at: datetime
    rider_profile: Optional[RiderProfileResponse] = None

    class Config:
        from_attributes = True

# Shift Schemas
class ShiftStart(BaseModel):
    premium_amount: float = Field(..., ge=0)
    payment_method: Optional[str] = "upi"

class ShiftEnd(BaseModel):
    distance_km: float = Field(..., ge=0)

class ShiftSummarySchema(BaseModel):
    duration: str
    distanceKm: float
    avgSpeedKmh: float
    peakSpeedKmh: float
    peakGForce: float
    incidentCount: int
    premiumPaidInr: float

class ShiftResponse(BaseModel):
    id: uuid.UUID
    rider_id: uuid.UUID
    status: ShiftStatus
    start_time: datetime
    end_time: Optional[datetime]
    distance_km: float
    premium_amount: float
    policy_number: Optional[str]
    created_at: datetime
    updated_at: datetime
    summary: Optional[ShiftSummarySchema] = None

    class Config:
        from_attributes = True

# Telemetry Schemas
class TelemetrySampleSchema(BaseModel):
    timestamp: float  # Epoch timestamp in seconds
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    speed: float
    accel_x: float
    accel_y: float
    accel_z: float
    gyro_x: float
    gyro_y: float
    gyro_z: float

class TelemetryBatchSchema(BaseModel):
    shift_id: uuid.UUID
    batch_sequence: int
    samples: List[TelemetrySampleSchema]

# Incident Schemas
class IncidentCreate(BaseModel):
    shift_id: uuid.UUID
    rider_id: uuid.UUID
    peak_g_force: float
    confidence_score: float
    latitude: float
    longitude: float

class IncidentResponse(BaseModel):
    id: uuid.UUID
    shift_id: uuid.UUID
    rider_id: uuid.UUID
    batch_id: Optional[uuid.UUID]
    status: IncidentStatus
    detected_at: datetime
    peak_g_force: float
    confidence_score: float
    latitude: float
    longitude: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Claim Schemas
class ClaimCreate(BaseModel):
    incident_id: uuid.UUID
    claimed_amount: float = Field(..., ge=0)

class ClaimResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    rider_id: uuid.UUID
    shift_id: uuid.UUID
    claim_number: str
    status: ClaimStatus
    claimed_amount: float
    approved_amount: Optional[float]
    rejection_reason: Optional[str]
    filed_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Payment Schemas
class CreateOrderRequest(BaseModel):
    shift_id: Optional[uuid.UUID] = None

class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int  # in paise
    currency: str
    key_id: str
    shift_id: uuid.UUID
    payment_id: uuid.UUID

class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str

class VerifyPaymentResponse(BaseModel):
    status: str
    message: str
    shift_id: uuid.UUID
    coverage_active: bool

class PaymentResponse(BaseModel):
    id: uuid.UUID
    shift_id: Optional[uuid.UUID]
    claim_id: Optional[uuid.UUID]
    amount: float
    status: PaymentStatus
    payment_type: PaymentType
    transaction_reference: Optional[str] = Field(default=None, alias="transaction_ref")
    razorpay_order_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
