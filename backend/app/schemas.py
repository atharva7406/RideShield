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
    
    # Hospital details for HOSPITAL_REP role
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None
    hospital_phone: Optional[str] = None

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
    is_phone_verified: bool
    wallet_balance: float
    created_at: datetime
    updated_at: datetime
    hospital_id: Optional[uuid.UUID] = None
    rider_profile: Optional[RiderProfileResponse] = None

    class Config:
        from_attributes = True

# Shift Schemas
class ShiftStart(BaseModel):
    # DEPRECATED (Phase 7): no longer authoritative. Accepted only for
    # backward compatibility with app builds that still send it (see
    # rider-app/src/services/shiftService.ts) — the server ALWAYS computes
    # the real premium itself via PremiumPricingService and silently
    # ignores whatever value (if any) is sent here. Optional so omitting
    # it entirely is also valid; ge=0 kept only to reject obviously
    # malformed payloads, not because the value is ever used.
    premium_amount: Optional[float] = Field(default=None, ge=0)
    payment_method: Optional[str] = "upi"

class ShiftEnd(BaseModel):
    # No longer authoritative — kept Optional for backward compatibility
    # with app builds that still send it, but the server now computes
    # Shift.distance_km itself from GPS telemetry (see
    # app/services/distance_service.py). This field is accepted and
    # ignored, never trusted.
    distance_km: Optional[float] = Field(default=None, ge=0)

class ShiftSummarySchema(BaseModel):
    duration: str
    distanceKm: float
    avgSpeedKmh: float
    peakSpeedKmh: float
    peakGForce: float
    incidentCount: int
    premiumPaidInr: float

class PremiumPreviewResponse(BaseModel):
    """Read-only preview of PremiumPricingService's output — see
    GET /shifts/premium-preview. Field set mirrors
    app/services/premium_pricing_service.PremiumQuote (minus internal
    bookkeeping like rider_id/previous_premium/contributors/computed_at)
    plus is_cold_start, so the rider app can render exactly what a
    subsequent POST /shifts/start or /payments/create-order would charge.
    """
    model_config = {"protected_namespaces": ()}  # allow the model_version field name

    base_premium: float
    risk_score: Optional[float] = None
    risk_band: Optional[str] = None
    confidence: float
    pricing_mode: str
    scoring_method: str
    model_version: str
    adjustment_amount: float
    final_premium: float
    is_cold_start: bool
    explanation: str

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
    # Populated by GET /shifts (list) so the rider app's "Incidents" filter
    # tab has something real to filter on — summary above is only ever set
    # transiently by POST /shifts/{id}/end's own response, never persisted,
    # so it's always None when a shift is fetched via the list endpoint.
    incident_count: int = 0

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
    rider_id: Optional[uuid.UUID] = None
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

# Helmet verification schemas — POST /helmet/verify.
# The upload itself is multipart (UploadFile, not JSON) so there's no
# request schema here; only the response is a Pydantic model.
class HelmetVerifyResponse(BaseModel):
    model_config = {"protected_namespaces": ()}  # allow the model_version field name

    verification_id: uuid.UUID
    helmet_worn: bool
    predicted_class: str
    confidence: float
    model_version: str
    valid_for_minutes: int
    message: str

# Crash-window submission schemas — POST /incidents/from-window.
# Unlike IncidentCreate, this carries the raw on-device sensor buffer
# (the CrashDetector's rolling ~5s window, already held in memory on-device
# for local detection) instead of a client-computed summary, so the
# backend can re-score with the trained ML model and compute peak_g_force/
# confidence itself rather than trusting client-supplied numbers.
class MotionSample(BaseModel):
    timestamp: float  # epoch ms
    x: float
    y: float
    z: float

class GpsWindowSample(BaseModel):
    timestamp: float  # epoch ms
    latitude: float
    longitude: float
    speed: float  # km/h
    accuracy: Optional[float] = None
    altitude: Optional[float] = None

class WindowCompleteness(BaseModel):
    """Phase 3 (PRE/IMPACT/POST capture) data-quality flags — see
    rider-app/src/crash-detection/incidentWindowCapture.ts's
    buildCompleteness(). Purely informational in this phase: the backend
    accepts and stores nothing extra based on it, and does not change ML
    scoring behavior — that's explicitly deferred to a future evidence-
    fusion phase. is_complete=False does NOT mean the window is rejected;
    ml_scoring_service's own `< 3 accel samples -> None -> 422` check is
    still the only hard rejection rule."""
    is_complete: bool = True
    has_pre_event_data: bool = True
    has_post_event_data: bool = True
    has_gyro: bool = True
    has_gps: bool = True
    is_low_sampling_rate: bool = False
    reasons: List[str] = []


class WindowMetadata(BaseModel):
    """Phase 3 — optional, additive. Old app builds simply omit this field;
    CrashWindowSubmission.window_metadata being None is the normal case for
    any submission sent before this phase shipped."""
    trigger_timestamp: Optional[float] = None  # epoch ms — the actual impact instant, not "now"
    window_start_timestamp: Optional[float] = None
    window_end_timestamp: Optional[float] = None
    accel_sample_count: Optional[int] = None
    gyro_sample_count: Optional[int] = None
    gps_sample_count: Optional[int] = None
    observed_accel_hz: Optional[float] = None
    observed_gyro_hz: Optional[float] = None
    observed_gps_hz: Optional[float] = None
    completeness: Optional[WindowCompleteness] = None


class CrashWindowSubmission(BaseModel):
    shift_id: uuid.UUID
    accel_samples: List[MotionSample] = Field(..., min_length=1)
    gyro_samples: List[MotionSample] = []
    gps_samples: List[GpsWindowSample] = []
    # Phase 1 (offline incident queue): minted client-side the instant Tier 0
    # fires, carried unchanged through local storage/retry/sync so the same
    # physical event always maps to the same ID. Phase 2 added a DB unique
    # constraint on Incident.client_incident_id plus idempotent create-or-
    # return-existing handling in incidents.py — see that file for details.
    client_incident_id: Optional[str] = None
    # Phase 3 — see WindowMetadata above.
    window_metadata: Optional[WindowMetadata] = None

class CrashWindowResponse(BaseModel):
    incident_id: uuid.UUID
    confidence_score: float
    scoring_method: str  # "ml" | "rule_based_fallback"
    predicted_class: Optional[str] = None

# Claim Schemas
class ClaimCreate(BaseModel):
    incident_id: uuid.UUID
    claimed_amount: float = Field(..., ge=0)

class ClaimMedicalReportResponse(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    hospital_id: uuid.UUID
    uploaded_by: uuid.UUID
    file_reference: str
    document_type: str
    notes: Optional[str]
    uploaded_at: datetime

    class Config:
        from_attributes = True

class IncidentEvidenceResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    claim_id: Optional[uuid.UUID] = None
    file_url: str
    file_type: str
    uploaded_at: datetime

    class Config:
        from_attributes = True

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
    medical_reports: Optional[List[ClaimMedicalReportResponse]] = []
    evidence: Optional[List[IncidentEvidenceResponse]] = []
    verification_score: Optional[float] = None

    class Config:
        from_attributes = True

# Payment Schemas
class CreateOrderRequest(BaseModel):
    shift_id: Optional[uuid.UUID] = None
    premium_amount: Optional[float] = 5.0

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
    shift_id: Optional[uuid.UUID] = None
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

class CreateRechargeRequest(BaseModel):
    amount: float = Field(..., gt=0)

class CreateRechargeResponse(BaseModel):
    order_id: str
    amount: int  # in paise
    currency: str
    key_id: str
    payment_id: uuid.UUID

