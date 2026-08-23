from datetime import datetime, timezone
import uuid
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.api import deps
from app.core.config import settings
from app.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    PaymentResponse,
)
from app.services import razorpay_service
from db.core.session import get_db
from db.models.user import User
from db.models.shift import Shift
from db.models.payment import Payment
from db.models.enums import ShiftStatus, PaymentStatus, PaymentType

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/create-order", response_model=CreateOrderResponse)
def create_payment_order(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    order_in: CreateOrderRequest
) -> Any:
    """
    Creates a Razorpay TEST Order for shift premium collection.
    If shift_id is provided, validates existing shift; otherwise creates a PAUSED shift awaiting payment.
    Server computes premium_amount from trusted DB data — never from client input.
    """
    db_shift = None
    if order_in.shift_id:
        db_shift = db.query(Shift).filter(
            Shift.id == order_in.shift_id,
            Shift.rider_id == current_user.id
        ).first()
        if not db_shift:
            raise HTTPException(status_code=404, detail="Specified shift not found")
        if db_shift.status == ShiftStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Shift is already active")

    if not db_shift:
        # Check if rider already has an active shift
        active = db.query(Shift).filter(
            Shift.rider_id == current_user.id,
            Shift.status == ShiftStatus.ACTIVE
        ).first()
        if active:
            raise HTTPException(status_code=400, detail="You already have an active shift")

        # Create shift in PAUSED status awaiting payment verification
        policy_num = f"POL-{uuid.uuid4().hex[:8].upper()}"
        db_shift = Shift(
            rider_id=current_user.id,
            status=ShiftStatus.PAUSED,
            start_time=datetime.now(timezone.utc),
            premium_amount=5.00,  # Canonical daily premium
            policy_number=policy_num,
            distance_km=0.0
        )
        db.add(db_shift)
        db.flush()

    premium = float(db_shift.premium_amount) if float(db_shift.premium_amount) > 0 else 5.00

    # Call Razorpay service to create order
    try:
        receipt = f"rcpt_{db_shift.id.hex[:12]}"
        razorpay_order = razorpay_service.create_razorpay_order(
            amount_inr=premium,
            receipt=receipt,
            notes={
                "shift_id": str(db_shift.id),
                "rider_id": str(current_user.id),
                "policy_number": db_shift.policy_number or ""
            }
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Razorpay order creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize Razorpay checkout order")

    # Persist PENDING payment record with Razorpay Order ID
    db_payment = Payment(
        shift_id=db_shift.id,
        rider_id=current_user.id,
        payment_type=PaymentType.PREMIUM_COLLECTION,
        amount=premium,
        currency="INR",
        status=PaymentStatus.PENDING,
        razorpay_order_id=razorpay_order["id"],
        transaction_ref=f"ORD-{razorpay_order['id']}"
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    return CreateOrderResponse(
        order_id=razorpay_order["id"],
        amount=razorpay_order["amount"],  # in paise
        currency=razorpay_order.get("currency", "INR"),
        key_id=settings.RAZORPAY_KEY_ID,
        shift_id=db_shift.id,
        payment_id=db_payment.id
    )

@router.post("/verify", response_model=VerifyPaymentResponse)
def verify_payment(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    verify_in: VerifyPaymentRequest
) -> Any:
    """
    Verifies Razorpay HMAC-SHA256 payment signature.
    Looks up the expected PENDING order from DB — never trusting client amount or order ID.
    On success: marks Payment SUCCESSFUL, updates transaction_ref, activates coverage (Shift -> ACTIVE).
    Idempotent: if payment is already SUCCESSFUL, returns verified without re-processing.
    """
    # Look up payment record by server-side stored razorpay_order_id
    payment_record = db.query(Payment).filter(
        Payment.razorpay_order_id == verify_in.razorpay_order_id
    ).first()

    if not payment_record:
        raise HTTPException(status_code=404, detail="Payment order record not found")

    if payment_record.rider_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorized to verify this payment")

    # IDEMPOTENCY CHECK: If already successful, return active state directly
    if payment_record.status == PaymentStatus.SUCCESSFUL:
        db_shift = db.query(Shift).filter(Shift.id == payment_record.shift_id).first()
        if db_shift and db_shift.status != ShiftStatus.ACTIVE:
            db_shift.status = ShiftStatus.ACTIVE
            db.commit()
        return VerifyPaymentResponse(
            status="already_verified",
            message="Payment was previously verified. Coverage is active.",
            shift_id=payment_record.shift_id,
            coverage_active=True
        )

    # Constant-time HMAC-SHA256 signature verification
    is_valid = razorpay_service.verify_razorpay_signature(
        razorpay_order_id=verify_in.razorpay_order_id,
        razorpay_payment_id=verify_in.razorpay_payment_id,
        razorpay_signature=verify_in.razorpay_signature
    )

    if not is_valid:
        payment_record.status = PaymentStatus.FAILED
        payment_record.processed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Payment signature verification failed. Coverage was not activated."
        )

    # SUCCESSFUL PAYMENT: Update payment & activate shift in single atomic transaction
    payment_record.status = PaymentStatus.SUCCESSFUL
    payment_record.transaction_ref = verify_in.razorpay_payment_id
    payment_record.razorpay_signature = verify_in.razorpay_signature
    payment_record.processed_at = datetime.now(timezone.utc)

    db_shift = db.query(Shift).filter(Shift.id == payment_record.shift_id).first()
    if db_shift:
        db_shift.status = ShiftStatus.ACTIVE
        db_shift.updated_at = datetime.now(timezone.utc)

    db.commit()

    return VerifyPaymentResponse(
        status="verified",
        message="Payment verified successfully. Insurance coverage is now ACTIVE.",
        shift_id=payment_record.shift_id,
        coverage_active=True
    )

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    """
    Webhook handler for asynchronous Razorpay event notifications (payment.captured, payment.failed, order.paid).
    Verifies Razorpay webhook signature if header is present.
    Executes idempotent payment updates and shift activation.
    """
    body_bytes = await request.body()
    sig_header = request.headers.get("X-Razorpay-Signature")

    # If webhook secret is configured, verify signature
    webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
    if webhook_secret and sig_header:
        if not razorpay_service.verify_webhook_signature(body_bytes, sig_header, webhook_secret):
            logger.warning("Razorpay webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    import json
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return {"status": "ignored", "reason": "invalid json payload"}

    event = data.get("event")
    logger.info(f"Received Razorpay webhook event: {event}")

    if event in ["payment.captured", "order.paid"]:
        payload = data.get("payload", {})
        payment_entity = payload.get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id") or payload.get("order", {}).get("entity", {}).get("id")
        payment_id = payment_entity.get("id")

        if order_id:
            db_payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
            if db_payment and db_payment.status != PaymentStatus.SUCCESSFUL:
                db_payment.status = PaymentStatus.SUCCESSFUL
                if payment_id:
                    db_payment.transaction_ref = payment_id
                db_payment.processed_at = datetime.now(timezone.utc)

                db_shift = db.query(Shift).filter(Shift.id == db_payment.shift_id).first()
                if db_shift:
                    db_shift.status = ShiftStatus.ACTIVE

                db.commit()
                logger.info(f"Webhook activated shift {db_payment.shift_id} via order {order_id}")

    elif event == "payment.failed":
        payload = data.get("payload", {})
        payment_entity = payload.get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        if order_id:
            db_payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
            if db_payment and db_payment.status == PaymentStatus.PENDING:
                db_payment.status = PaymentStatus.FAILED
                db_payment.processed_at = datetime.now(timezone.utc)
                db.commit()

    return {"status": "ok", "event": event}
