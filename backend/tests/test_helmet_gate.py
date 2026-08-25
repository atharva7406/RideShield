"""
Endpoint-level tests: POST /helmet/verify, and the mandatory gate wired
into POST /shifts/start and POST /payments/create-order +
POST /payments/verify. Pure service-layer coverage (record/consume/
expiry logic) already lives in test_helmet_verification_service.py —
this file verifies the WIRING through real HTTP requests.
"""
import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import hmac
import hashlib
import io
import uuid
from decimal import Decimal

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.payment import Payment
from db.models.premium_quote import PremiumQuoteRecord
from db.models.helmet_verification import HelmetVerification
from db.models.enums import UserRole, ShiftStatus, PaymentStatus
from app.core.config import settings
from app.core.security import create_access_token
from app.services import razorpay_service, helmet_verification_service as helmet_svc

client = TestClient(app)


@pytest.fixture
def mock_razorpay(monkeypatch):
    def mock_create(amount_inr, receipt: str, notes=None):
        amount_dec = amount_inr if isinstance(amount_inr, Decimal) else Decimal(str(amount_inr))
        return {
            "id": f"order_{uuid.uuid4().hex[:12]}",
            "amount": int((amount_dec * 100).to_integral_value(rounding="ROUND_HALF_UP")),
            "currency": "INR",
            "receipt": receipt,
            "notes": notes or {},
        }
    monkeypatch.setattr(razorpay_service, "create_razorpay_order", mock_create)


def _random_image_bytes() -> bytes:
    arr = (np.random.rand(300, 300, 3) * 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_user():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id, email=f"test_gate_{rand_str}@example.com",
        phone_number=f"+1990{rand_str}", hashed_password="x",
        full_name="Gate Test Rider", role=UserRole.RIDER, wallet_balance=500.0, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user, create_access_token(subject=str(user.id))


def _cleanup_user(user_id):
    db = SessionLocal()
    try:
        db.query(PremiumQuoteRecord).filter(PremiumQuoteRecord.rider_id == user_id).delete()
        db.query(HelmetVerification).filter(HelmetVerification.rider_id == user_id).delete()
        db.query(Payment).filter(Payment.rider_id == user_id).delete()
        db.query(Shift).filter(Shift.rider_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _grant_passed_verification(rider_id):
    """Directly inserts a passed, unconsumed verification — bypasses the
    ML call itself (already covered elsewhere) so gate-wiring tests don't
    depend on what this particular unvalidated model happens to predict
    for a random noise image."""
    db = SessionLocal()
    result = helmet_svc.HelmetVerificationResult("full_face_helmet", 0.95, True, "test-v1")
    helmet_svc.record_verification(db, rider_id, result)
    db.commit()
    db.close()


class TestVerifyEndpoint:
    def test_requires_authentication(self):
        res = client.post("/helmet/verify", files={"file": ("selfie.jpg", _random_image_bytes(), "image/jpeg")})
        assert res.status_code in (401, 403)

    def test_accepts_an_image_and_returns_a_verdict(self):
        user, token = _make_user()
        try:
            res = client.post(
                "/helmet/verify",
                files={"file": ("selfie.jpg", _random_image_bytes(), "image/jpeg")},
                headers=_auth(token),
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert "verification_id" in data
            assert isinstance(data["helmet_worn"], bool)
            assert data["predicted_class"]
            assert 0.0 <= data["confidence"] <= 1.0
            assert data["valid_for_minutes"] == helmet_svc.VERIFICATION_VALIDITY_MINUTES

            db = SessionLocal()
            record = db.query(HelmetVerification).filter(
                HelmetVerification.id == uuid.UUID(data["verification_id"])
            ).first()
            assert record is not None
            assert record.rider_id == user.id
            db.close()
        finally:
            _cleanup_user(user.id)

    def test_rejects_non_image_content_type(self):
        user, token = _make_user()
        try:
            res = client.post(
                "/helmet/verify",
                files={"file": ("notes.txt", b"hello world", "text/plain")},
                headers=_auth(token),
            )
            assert res.status_code == 400
        finally:
            _cleanup_user(user.id)

    def test_rejects_corrupt_image_bytes(self):
        user, token = _make_user()
        try:
            res = client.post(
                "/helmet/verify",
                files={"file": ("selfie.jpg", b"not actually a jpeg", "image/jpeg")},
                headers=_auth(token),
            )
            assert res.status_code == 422
        finally:
            _cleanup_user(user.id)


class TestShiftStartGate:
    def test_blocked_without_any_verification(self):
        user, token = _make_user()
        try:
            res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert res.status_code == 403
            assert "helmet" in res.json()["detail"].lower()
        finally:
            _cleanup_user(user.id)

    def test_allowed_with_a_passed_verification(self):
        user, token = _make_user()
        try:
            _grant_passed_verification(user.id)
            res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert res.status_code == 200, res.text
        finally:
            _cleanup_user(user.id)

    def test_verification_is_consumed_and_cannot_start_a_second_shift(self):
        user, token = _make_user()
        try:
            _grant_passed_verification(user.id)
            first = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert first.status_code == 200

            db = SessionLocal()
            db.query(Shift).filter(Shift.id == uuid.UUID(first.json()["id"])).update({"status": ShiftStatus.COMPLETED})
            db.commit()
            db.close()

            # No new verification granted — the old one is spent.
            second = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert second.status_code == 403
        finally:
            _cleanup_user(user.id)

    def test_failed_verification_does_not_satisfy_the_gate(self):
        user, token = _make_user()
        try:
            db = SessionLocal()
            result = helmet_svc.HelmetVerificationResult("no_helmet", 0.9, False, "test-v1")
            helmet_svc.record_verification(db, user.id, result)
            db.commit()
            db.close()

            res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert res.status_code == 403
        finally:
            _cleanup_user(user.id)

    def test_expired_verification_does_not_satisfy_the_gate(self):
        from datetime import datetime, timedelta, timezone
        user, token = _make_user()
        try:
            db = SessionLocal()
            result = helmet_svc.HelmetVerificationResult("full_face_helmet", 0.95, True, "test-v1")
            record = helmet_svc.record_verification(db, user.id, result)
            db.commit()
            record.created_at = datetime.now(timezone.utc) - timedelta(
                minutes=helmet_svc.VERIFICATION_VALIDITY_MINUTES + 1
            )
            db.commit()
            db.close()

            res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert res.status_code == 403
        finally:
            _cleanup_user(user.id)


class TestCreateOrderGate:
    def test_blocked_without_any_verification(self, mock_razorpay):
        user, token = _make_user()
        try:
            res = client.post("/payments/create-order", json={}, headers=_auth(token))
            assert res.status_code == 403
            assert "helmet" in res.json()["detail"].lower()
        finally:
            _cleanup_user(user.id)

    def test_allowed_with_a_passed_verification(self, mock_razorpay):
        user, token = _make_user()
        try:
            _grant_passed_verification(user.id)
            res = client.post("/payments/create-order", json={}, headers=_auth(token))
            assert res.status_code == 200, res.text
        finally:
            _cleanup_user(user.id)


class TestVerifyPaymentGate:
    def test_activation_blocked_if_verification_expires_before_payment_completes(self, mock_razorpay):
        from datetime import datetime, timedelta, timezone
        user, token = _make_user()
        try:
            _grant_passed_verification(user.id)
            order = client.post("/payments/create-order", json={}, headers=_auth(token))
            assert order.status_code == 200
            order_id = order.json()["order_id"]

            # Expire the verification AFTER order creation but BEFORE
            # payment verification — simulates a slow checkout.
            db = SessionLocal()
            rec = db.query(HelmetVerification).filter(HelmetVerification.rider_id == user.id).first()
            rec.created_at = datetime.now(timezone.utc) - timedelta(
                minutes=helmet_svc.VERIFICATION_VALIDITY_MINUTES + 1
            )
            db.commit()
            db.close()

            mock_payment_id = f"pay_test_{uuid.uuid4().hex[:8]}"
            secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
            msg = f"{order_id}|{mock_payment_id}".encode("utf-8")
            valid_signature = hmac.new(secret, msg, hashlib.sha256).hexdigest()

            verify_res = client.post(
                "/payments/verify",
                json={
                    "razorpay_payment_id": mock_payment_id,
                    "razorpay_order_id": order_id,
                    "razorpay_signature": valid_signature,
                },
                headers=_auth(token),
            )
            assert verify_res.status_code == 403
            assert "helmet" in verify_res.json()["detail"].lower()

            # Payment is NOT marked failed — money was genuinely captured;
            # it stays PENDING so the rider can re-verify and retry.
            db = SessionLocal()
            payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
            assert payment.status == PaymentStatus.PENDING
            shift = db.query(Shift).filter(Shift.id == payment.shift_id).first()
            assert shift.status == ShiftStatus.PAUSED
            db.close()
        finally:
            _cleanup_user(user.id)

    def test_activation_succeeds_and_consumes_verification(self, mock_razorpay):
        user, token = _make_user()
        try:
            _grant_passed_verification(user.id)
            order = client.post("/payments/create-order", json={}, headers=_auth(token))
            order_id = order.json()["order_id"]

            mock_payment_id = f"pay_test_{uuid.uuid4().hex[:8]}"
            secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
            msg = f"{order_id}|{mock_payment_id}".encode("utf-8")
            valid_signature = hmac.new(secret, msg, hashlib.sha256).hexdigest()

            verify_res = client.post(
                "/payments/verify",
                json={
                    "razorpay_payment_id": mock_payment_id,
                    "razorpay_order_id": order_id,
                    "razorpay_signature": valid_signature,
                },
                headers=_auth(token),
            )
            assert verify_res.status_code == 200, verify_res.text
            assert verify_res.json()["coverage_active"] is True

            db = SessionLocal()
            rec = db.query(HelmetVerification).filter(HelmetVerification.rider_id == user.id).first()
            assert rec.consumed_at is not None
            db.close()
        finally:
            _cleanup_user(user.id)
