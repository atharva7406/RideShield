from datetime import datetime, timezone
import uuid
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
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

@router.get("/checkout", response_class=HTMLResponse)
def get_checkout_page(
    order_id: str,
    amount: int,
    currency: str = "INR",
    key_id: str = ""
):
    """
    Renders a dynamic HTML page that loads Razorpay Checkout and opens it immediately.
    Once payment succeeds, it redirects to the success endpoint with URL query params.
    """
    key_to_use = key_id if key_id else settings.RAZORPAY_KEY_ID
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RideShield Secure Checkout</title>
        <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background-color: #f8fafc;
            }}
            .card {{
                background: white;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                text-align: center;
                max-width: 90%;
                width: 320px;
            }}
            .loader {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid #0f766e;
                border-radius: 50%;
                width: 36px;
                height: 36px;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px auto;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            h3 {{ margin: 0 0 8px 0; color: #1e293b; }}
            p {{ margin: 0; color: #64748b; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="loader"></div>
            <h3>Connecting to Gateway</h3>
            <p>Please wait, opening Razorpay checkout...</p>
        </div>
        
        <script>
            window.onload = function() {{
                var isMock = "{order_id}".indexOf("order_mock_") === 0;
                
                if (isMock) {{
                    console.log("Mock Payment active. Simulating successful checkout.");
                    setTimeout(function() {{
                        var mockPayId = "pay_mock_" + Math.random().toString(36).substring(2, 10).toUpperCase();
                        var mockSig = "sig_mock_" + Math.random().toString(36).substring(2, 10).toUpperCase();
                        var successUrl = "/payments/success?" + 
                            "razorpay_payment_id=" + mockPayId +
                            "&razorpay_order_id={order_id}" +
                            "&razorpay_signature=" + mockSig;
                        window.location.href = successUrl;
                    }}, 1500);
                    return;
                }}
                
                var options = {{
                    "key": "{key_to_use}",
                    "amount": {amount},
                    "currency": "{currency}",
                    "name": "RideShield Microinsurance",
                    "description": "Daily Shift Protection",
                    "order_id": "{order_id}",
                    "handler": function (response) {{
                        var successUrl = "/payments/success?" + 
                            "razorpay_payment_id=" + encodeURIComponent(response.razorpay_payment_id) +
                            "&razorpay_order_id=" + encodeURIComponent(response.razorpay_order_id) +
                            "&razorpay_signature=" + encodeURIComponent(response.razorpay_signature);
                        window.location.href = successUrl;
                    }},
                    "modal": {{
                        "ondismiss": function() {{
                            window.location.href = "/payments/cancel";
                        }}
                    }},
                    "theme": {{
                        "color": "#0f766e"
                    }}
                }};
                
                var rzp = new Razorpay(options);
                
                rzp.on('payment.failed', function (response){{
                    alert("Payment Failed: " + response.error.description);
                    window.location.href = "/payments/cancel";
                }});
                
                rzp.open();
            }};
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/success", response_class=HTMLResponse)
def get_success_page(
    razorpay_payment_id: str = "",
    razorpay_order_id: str = "",
    razorpay_signature: str = ""
):
    """
    Success redirection target. The mobile app reads the query parameters and verifies payment.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Successful</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                text-align: center;
                padding-top: 60px;
                background-color: #f0fdf4;
                color: #166534;
                margin: 0;
            }}
            .card {{
                background: white;
                border-radius: 12px;
                padding: 30px;
                margin: 0 auto;
                max-width: 90%;
                width: 320px;
                box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            }}
            h2 {{ margin-top: 0; color: #15803d; }}
            p {{ color: #166534; font-size: 14px; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Payment Successful!</h2>
            <p>Initializing your shift's coverage. Please do not close this window...</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/cancel", response_class=HTMLResponse)
def get_cancel_page():
    """
    Cancellation redirection target.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Cancelled</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                text-align: center;
                padding-top: 60px;
                background-color: #fef2f2;
                color: #991b1b;
                margin: 0;
            }
            .card {
                background: white;
                border-radius: 12px;
                padding: 30px;
                margin: 0 auto;
                max-width: 90%;
                width: 320px;
                box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            }
            h2 { margin-top: 0; color: #b91c1c; }
            p { color: #991b1b; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Payment Cancelled</h2>
            <p>Returning you back to checkout...</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

