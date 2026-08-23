import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import uuid
import hmac
import hashlib
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.payment import Payment
from db.models.enums import UserRole, ShiftStatus, PaymentStatus, PaymentType
from app.core.config import settings
from app.core.security import create_access_token
from app.services import razorpay_service

client = TestClient(app)

@pytest.fixture(scope="module")
def test_rider_user():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id,
        email=f"test_rider_{rand_str}@example.com",
        phone_number=f"+1999{rand_str}",
        hashed_password="hashed_test_pass",
        full_name="Test Payment Rider",
        role=UserRole.RIDER,
        wallet_balance=500.0,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id))

    yield user, token

    # Cleanup
    try:
        db.query(Payment).filter(Payment.rider_id == user.id).delete()
        db.query(Shift).filter(Shift.rider_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

def clear_user_shifts(user_id):
    db = SessionLocal()
    try:
        db.query(Payment).filter(Payment.rider_id == user_id).delete()
        db.query(Shift).filter(Shift.rider_id == user_id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

def test_create_payment_order_success(test_rider_user):
    user, token = test_rider_user
    clear_user_shifts(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/payments/create-order", json={}, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()

    assert "order_id" in data
    assert data["order_id"].startswith("order_")
    assert data["amount"] == 500  # ₹5.00 = 500 paise
    assert data["currency"] == "INR"
    assert data["key_id"] == settings.RAZORPAY_KEY_ID

    # Verify PENDING Payment row created in DB
    db = SessionLocal()
    payment = db.query(Payment).filter(Payment.razorpay_order_id == data["order_id"]).first()
    assert payment is not None
    assert payment.rider_id == user.id
    assert payment.status == PaymentStatus.PENDING
    assert payment.amount == 5.0
    db.close()

def test_verify_payment_valid_signature(test_rider_user):
    user, token = test_rider_user
    clear_user_shifts(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create order
    create_res = client.post("/payments/create-order", json={}, headers=headers)
    assert create_res.status_code == 200
    order_data = create_res.json()
    order_id = order_data["order_id"]
    shift_id = order_data["shift_id"]

    # 2. Generate valid HMAC-SHA256 signature
    mock_payment_id = f"pay_test_{uuid.uuid4().hex[:8]}"
    secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
    msg = f"{order_id}|{mock_payment_id}".encode("utf-8")
    valid_signature = hmac.new(secret, msg, hashlib.sha256).hexdigest()

    # 3. Verify
    verify_res = client.post(
        "/payments/verify",
        json={
            "razorpay_payment_id": mock_payment_id,
            "razorpay_order_id": order_id,
            "razorpay_signature": valid_signature,
        },
        headers=headers,
    )
    assert verify_res.status_code == 200, verify_res.text
    vdata = verify_res.json()
    assert vdata["status"] == "verified"
    assert vdata["coverage_active"] is True

    # 4. Check DB row state
    db = SessionLocal()
    payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
    assert payment is not None
    assert payment.status == PaymentStatus.SUCCESSFUL
    assert payment.transaction_ref == mock_payment_id
    assert payment.razorpay_signature == valid_signature

    shift = db.query(Shift).filter(Shift.id == uuid.UUID(shift_id)).first()
    assert shift is not None
    assert shift.status == ShiftStatus.ACTIVE
    db.close()

def test_verify_payment_invalid_signature(test_rider_user):
    user, token = test_rider_user
    clear_user_shifts(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/payments/create-order", json={}, headers=headers)
    assert create_res.status_code == 200
    order_data = create_res.json()
    order_id = order_data["order_id"]
    shift_id = order_data["shift_id"]

    mock_payment_id = f"pay_test_{uuid.uuid4().hex[:8]}"
    invalid_signature = "invalid_fake_signature_12345"

    verify_res = client.post(
        "/payments/verify",
        json={
            "razorpay_payment_id": mock_payment_id,
            "razorpay_order_id": order_id,
            "razorpay_signature": invalid_signature,
        },
        headers=headers,
    )
    assert verify_res.status_code == 400
    assert "signature verification failed" in verify_res.json()["detail"].lower()

    # Verify status is FAILED and Shift remains PAUSED
    db = SessionLocal()
    payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
    assert payment.status == PaymentStatus.FAILED

    shift = db.query(Shift).filter(Shift.id == uuid.UUID(shift_id)).first()
    assert shift.status == ShiftStatus.PAUSED
    db.close()

def test_verify_payment_idempotency(test_rider_user):
    user, token = test_rider_user
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/payments/create-order", json={}, headers=headers)
    order_data = create_res.json()
    order_id = order_data["order_id"]

    mock_payment_id = f"pay_test_{uuid.uuid4().hex[:8]}"
    secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
    msg = f"{order_id}|{mock_payment_id}".encode("utf-8")
    valid_signature = hmac.new(secret, msg, hashlib.sha256).hexdigest()

    # First verification
    v1 = client.post(
        "/payments/verify",
        json={
            "razorpay_payment_id": mock_payment_id,
            "razorpay_order_id": order_id,
            "razorpay_signature": valid_signature,
        },
        headers=headers,
    )
    assert v1.status_code == 200
    assert v1.json()["status"] == "verified"

    # Second verification (idempotent call)
    v2 = client.post(
        "/payments/verify",
        json={
            "razorpay_payment_id": mock_payment_id,
            "razorpay_order_id": order_id,
            "razorpay_signature": valid_signature,
        },
        headers=headers,
    )
    assert v2.status_code == 200
    assert v2.json()["status"] == "already_verified"
    assert v2.json()["coverage_active"] is True
