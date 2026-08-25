"""
Phase 7 — server-authoritative premium + Razorpay integration.

Focused, endpoint-level tests proving the client cannot influence the
rupee amount charged through either the wallet path (POST /shifts/start)
or the Razorpay/UPI path (POST /payments/create-order + /payments/verify
+ /payments/webhook). Pure-function coverage of PremiumPricingService
itself already lives in test_premium_pricing_service.py — this file does
not repeat that; it verifies the WIRING: that the endpoints actually call
the pricing service and actually ignore client-supplied price/risk
fields, end-to-end through the real HTTP layer.
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
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.payment import Payment
from db.models.premium_quote import PremiumQuoteRecord
from db.models.shift_behaviour_summary import ShiftBehaviourSummary
from db.models.rider_behaviour_profile import RiderBehaviourProfile
from db.models.enums import UserRole, ShiftStatus, PaymentStatus
from app.core.config import settings
from app.core.security import create_access_token
from app.services import razorpay_service, premium_pricing_service, rider_behaviour_profile_service
from app.services import helmet_verification_service as helmet_svc
from db.models.helmet_verification import HelmetVerification

client = TestClient(app)


@pytest.fixture
def mock_razorpay_create_order(monkeypatch):
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


def _make_user(role=UserRole.RIDER):
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id, email=f"test_p7_{rand_str}@example.com",
        phone_number=f"+1993{rand_str}", hashed_password="hashed_test_pass",
        full_name="Phase7 Test Rider", role=role, wallet_balance=500.0, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    token = create_access_token(subject=str(user.id))

    # This whole file is about premium/pricing wiring, not the helmet
    # gate (see test_helmet_gate.py) — grant a passed verification so
    # POST /shifts/start and /payments/create-order's mandatory gate
    # doesn't block every test here.
    db2 = SessionLocal()
    result = helmet_svc.HelmetVerificationResult("full_face_helmet", 0.95, True, "test-v1")
    helmet_svc.record_verification(db2, rand_id, result)
    db2.commit()
    db2.close()

    return user, token


def _cleanup_user(user_id):
    db = SessionLocal()
    try:
        db.query(PremiumQuoteRecord).filter(PremiumQuoteRecord.rider_id == user_id).delete()
        db.query(HelmetVerification).filter(HelmetVerification.rider_id == user_id).delete()
        db.query(Payment).filter(Payment.rider_id == user_id).delete()
        db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user_id).delete()
        db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.rider_id == user_id).delete()
        db.query(Shift).filter(Shift.rider_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _make_completed_shift_with_summary(rider_id, hard_braking_rate, overspeeding_rate, hours_ago=1):
    db = SessionLocal()
    shift = Shift(
        rider_id=rider_id, status=ShiftStatus.COMPLETED,
        start_time=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        end_time=datetime.now(timezone.utc) - timedelta(hours=hours_ago - 1),
        premium_amount=5.0,
        policy_number=f"POL-P7-{uuid.uuid4().hex[:8].upper()}", distance_km=5.0,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    shift_id = shift.id
    db.add(ShiftBehaviourSummary(
        shift_id=shift_id, rider_id=rider_id,
        duration_seconds=600, distance_km=5.0, sample_count=50,
        average_speed=30.0, max_speed=45.0,
        hard_braking_count=2, hard_acceleration_count=1, overspeeding_count=0, sharp_turn_count=1,
        hard_braking_rate=hard_braking_rate, hard_acceleration_rate=1.0,
        overspeeding_rate=overspeeding_rate, sharp_turn_rate=1.0,
        max_g=1.4, accel_std=0.2, jerk_mean=0.1,
        sampling_density=5.0, data_quality_score=0.9, is_valid=True,
        created_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    ))
    db.commit()
    db.close()
    return shift_id


def _build_profile(rider_id, n_shifts=6, hard_braking_rate=2.0, overspeeding_rate=0.5):
    for i in range(n_shifts):
        _make_completed_shift_with_summary(rider_id, hard_braking_rate, overspeeding_rate, hours_ago=n_shifts - i + 1)
    db = SessionLocal()
    rider_behaviour_profile_service.rebuild_rider_profile(db, rider_id)
    db.commit()
    db.close()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Wallet path: POST /shifts/start
# ---------------------------------------------------------------------------


class TestShiftStartServerAuthoritative:
    def test_cold_start_wallet_charges_base_premium_not_client_value(self):
        user, token = _make_user()
        try:
            res = client.post(
                "/shifts/start",
                json={"premium_amount": 99999, "payment_method": "wallet"},
                headers=_auth(token),
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert float(data["premium_amount"]) == 5.00  # server default, NOT 99999
        finally:
            _cleanup_user(user.id)

    def test_client_zero_premium_is_ignored(self):
        user, token = _make_user()
        try:
            res = client.post(
                "/shifts/start",
                json={"premium_amount": 0, "payment_method": "wallet"},
                headers=_auth(token),
            )
            assert res.status_code == 200, res.text
            assert float(res.json()["premium_amount"]) == 5.00
        finally:
            _cleanup_user(user.id)

    def test_omitted_premium_amount_still_works(self):
        """premium_amount is now Optional — omitting it entirely must not
        break the request."""
        user, token = _make_user()
        try:
            res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert res.status_code == 200, res.text
            assert float(res.json()["premium_amount"]) == 5.00
        finally:
            _cleanup_user(user.id)

    def test_fake_risk_fields_in_request_body_are_ignored(self):
        """The endpoint's schema has no risk_score/risk_band/pricing_mode
        field at all — sending them must have zero effect (Pydantic
        silently discards unknown fields)."""
        user, token = _make_user()
        try:
            res = client.post(
                "/shifts/start",
                json={
                    "payment_method": "wallet",
                    "risk_score": 0,
                    "risk_band": "VERY_LOW",
                    "pricing_mode": "PERSONALIZED",
                    "final_premium": 0.01,
                },
                headers=_auth(token),
            )
            assert res.status_code == 200, res.text
            assert float(res.json()["premium_amount"]) == 5.00
        finally:
            _cleanup_user(user.id)

    def test_wallet_deducted_by_server_premium_not_client_premium(self):
        user, token = _make_user()
        try:
            client.post(
                "/shifts/start",
                json={"premium_amount": 1, "payment_method": "wallet"},
                headers=_auth(token),
            )
            db = SessionLocal()
            refreshed = db.query(User).filter(User.id == user.id).first()
            assert refreshed.wallet_balance == pytest.approx(500.0 - 5.00)
            db.close()
        finally:
            _cleanup_user(user.id)

    def test_premium_quote_record_persisted_for_wallet_shift(self):
        user, token = _make_user()
        try:
            res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            shift_id = uuid.UUID(res.json()["id"])
            db = SessionLocal()
            record = db.query(PremiumQuoteRecord).filter(PremiumQuoteRecord.shift_id == shift_id).first()
            assert record is not None
            assert record.rider_id == user.id
            assert record.is_cold_start is True
            assert float(record.final_premium) == 5.00
            db.close()
        finally:
            _cleanup_user(user.id)

    def test_riskier_rider_pays_more_than_safer_rider_via_wallet(self):
        safe_user, safe_token = _make_user()
        risky_user, risky_token = _make_user()
        try:
            _build_profile(safe_user.id, hard_braking_rate=0.0, overspeeding_rate=0.0)
            _build_profile(risky_user.id, hard_braking_rate=15.0, overspeeding_rate=10.0)
            # Both riders' most recent shift premium is the ₹5.00 fixture
            # default (set in _make_completed_shift_with_summary), close
            # enough to the expected raw targets that the rate-of-change
            # cap does not swallow the risk-based difference.

            safe_res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(safe_token))
            risky_res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(risky_token))
            assert safe_res.status_code == 200 and risky_res.status_code == 200
            assert float(risky_res.json()["premium_amount"]) >= float(safe_res.json()["premium_amount"])
        finally:
            _cleanup_user(safe_user.id)
            _cleanup_user(risky_user.id)

    def test_insufficient_wallet_balance_uses_server_premium_in_check(self):
        db = SessionLocal()
        rand_id = uuid.uuid4()
        rand_str = str(rand_id.int)[:8]
        user = User(
            id=rand_id, email=f"test_p7_poor_{rand_str}@example.com",
            phone_number=f"+1994{rand_str}", hashed_password="x",
            full_name="Poor Rider", role=UserRole.RIDER, wallet_balance=1.00, is_active=True,
        )
        db.add(user)
        db.commit()
        token = create_access_token(subject=str(user.id))
        db.close()
        db2 = SessionLocal()
        result = helmet_svc.HelmetVerificationResult("full_face_helmet", 0.95, True, "test-v1")
        helmet_svc.record_verification(db2, rand_id, result)
        db2.commit()
        db2.close()
        try:
            # Client claims premium_amount=0 (which they COULD afford) —
            # server must still evaluate against its own ₹5.00 default
            # and correctly reject for insufficient balance.
            res = client.post(
                "/shifts/start",
                json={"premium_amount": 0, "payment_method": "wallet"},
                headers=_auth(token),
            )
            assert res.status_code == 400
            assert "insufficient" in res.json()["detail"].lower()
        finally:
            _cleanup_user(user.id)

    def test_unauthorized_request_rejected(self):
        res = client.post("/shifts/start", json={"payment_method": "wallet"})
        assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Razorpay/UPI path: POST /payments/create-order
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_razorpay_create_order")
class TestCreateOrderServerAuthoritative:
    def test_create_order_request_schema_has_no_price_or_risk_field(self):
        """Structural proof: CreateOrderRequest cannot carry a client
        amount/risk claim even if the client tries — the field doesn't
        exist on the schema."""
        from app.schemas import CreateOrderRequest
        fields = set(CreateOrderRequest.model_fields.keys())
        assert fields == {"shift_id"}

    def test_cold_start_order_amount_is_base_premium(self):
        user, token = _make_user()
        try:
            res = client.post("/payments/create-order", json={}, headers=_auth(token))
            assert res.status_code == 200, res.text
            assert res.json()["amount"] == 500  # paise
        finally:
            _cleanup_user(user.id)

    def test_riskier_rider_gets_higher_order_amount(self):
        safe_user, safe_token = _make_user()
        risky_user, risky_token = _make_user()
        try:
            _build_profile(safe_user.id, hard_braking_rate=0.0, overspeeding_rate=0.0)
            _build_profile(risky_user.id, hard_braking_rate=15.0, overspeeding_rate=10.0)

            safe_res = client.post("/payments/create-order", json={}, headers=_auth(safe_token))
            risky_res = client.post("/payments/create-order", json={}, headers=_auth(risky_token))
            assert safe_res.status_code == 200 and risky_res.status_code == 200
            assert risky_res.json()["amount"] >= safe_res.json()["amount"]
        finally:
            _cleanup_user(safe_user.id)
            _cleanup_user(risky_user.id)

    def test_retrying_with_shift_id_reuses_the_same_frozen_amount(self):
        user, token = _make_user()
        try:
            first = client.post("/payments/create-order", json={}, headers=_auth(token))
            shift_id = first.json()["shift_id"]
            second = client.post("/payments/create-order", json={"shift_id": shift_id}, headers=_auth(token))
            assert second.status_code == 200
            assert second.json()["amount"] == first.json()["amount"]
            # Exactly one quote row for this shift — retry did not create
            # (or need) a second one.
            db = SessionLocal()
            count = db.query(PremiumQuoteRecord).filter(
                PremiumQuoteRecord.shift_id == uuid.UUID(shift_id)
            ).count()
            db.close()
            assert count == 1
        finally:
            _cleanup_user(user.id)

    def test_premium_quote_record_matches_shift_premium_amount(self):
        user, token = _make_user()
        try:
            res = client.post("/payments/create-order", json={}, headers=_auth(token))
            shift_id = uuid.UUID(res.json()["shift_id"])
            db = SessionLocal()
            shift = db.query(Shift).filter(Shift.id == shift_id).first()
            record = db.query(PremiumQuoteRecord).filter(PremiumQuoteRecord.shift_id == shift_id).first()
            assert record is not None
            assert Decimal(str(record.final_premium)) == Decimal(str(shift.premium_amount))
            assert record.explanation  # human-readable explanation present
            assert record.model_version
            db.close()
        finally:
            _cleanup_user(user.id)


# ---------------------------------------------------------------------------
# Fallback safety: risk/ML failure must never open a client-controlled
# premium path.
# ---------------------------------------------------------------------------


class TestFallbackSafetyUnderModelFailure:
    def test_ml_scoring_failure_still_produces_a_valid_server_premium(self, monkeypatch):
        from app.services import rider_behaviour_risk_service as risk_svc

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated model failure")

        monkeypatch.setattr(risk_svc, "is_ml_available", lambda: True)
        monkeypatch.setattr(risk_svc, "predict_calibrated_from_features", _boom)

        user, token = _make_user()
        try:
            _build_profile(user.id, hard_braking_rate=5.0, overspeeding_rate=2.0)
            res = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert res.status_code == 200, res.text
            premium = float(res.json()["premium_amount"])
            assert premium_pricing_service.MIN_PREMIUM <= Decimal(str(premium)) <= premium_pricing_service.MAX_PREMIUM

            db = SessionLocal()
            record = db.query(PremiumQuoteRecord).filter(
                PremiumQuoteRecord.shift_id == uuid.UUID(res.json()["id"])
            ).first()
            # Fell back to the deterministic baseline, not a crash / not a
            # client-controlled value.
            assert record.scoring_method == "deterministic_baseline"
            db.close()
        finally:
            _cleanup_user(user.id)


# ---------------------------------------------------------------------------
# Razorpay boundary: no negative/zero/NaN/malformed premium can reach it.
# ---------------------------------------------------------------------------


class TestRazorpayAmountBoundarySafety:
    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            razorpay_service.create_razorpay_order(Decimal("-5.00"), receipt="r1")

    def test_nan_amount_rejected(self):
        with pytest.raises(ValueError):
            razorpay_service.create_razorpay_order(float("nan"), receipt="r2")

    def test_infinite_amount_rejected(self):
        with pytest.raises(ValueError):
            razorpay_service.create_razorpay_order(float("inf"), receipt="r3")

    def test_malformed_amount_rejected(self):
        with pytest.raises(ValueError):
            razorpay_service.create_razorpay_order("not-a-number", receipt="r4")

    @staticmethod
    def _fake_client(monkeypatch):
        """Stubs the Razorpay SDK client itself (not create_razorpay_order)
        so the real paise-conversion/validation logic in
        create_razorpay_order runs unmodified, with no real network call."""
        class _FakeOrders:
            def create(self, data):
                return {"id": "order_fake", **data}

        class _FakeClient:
            order = _FakeOrders()

        monkeypatch.setattr(razorpay_service, "get_razorpay_client", lambda: _FakeClient())

    def test_zero_amount_floored_to_minimum_paise(self, monkeypatch):
        self._fake_client(monkeypatch)
        result = razorpay_service.create_razorpay_order(Decimal("0.00"), receipt="r5")
        assert result["amount"] == 100  # Razorpay's own Rs.1.00 floor, not 0

    def test_decimal_amount_converted_exactly_no_float_drift(self, monkeypatch):
        self._fake_client(monkeypatch)
        result = razorpay_service.create_razorpay_order(Decimal("6.10"), receipt="r6")
        assert result["amount"] == 610


# ---------------------------------------------------------------------------
# Payment verification: signature verification, idempotency, authorized-
# rider isolation, and amount-mismatch rejection via the webhook.
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_razorpay_create_order")
class TestPaymentVerificationAndIsolation:
    def test_other_rider_cannot_verify_someone_elses_payment(self):
        owner, owner_token = _make_user()
        stranger, stranger_token = _make_user()
        try:
            order = client.post("/payments/create-order", json={}, headers=_auth(owner_token))
            order_id = order.json()["order_id"]
            mock_payment_id = f"pay_test_{uuid.uuid4().hex[:8]}"
            secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
            msg = f"{order_id}|{mock_payment_id}".encode("utf-8")
            valid_signature = hmac.new(secret, msg, hashlib.sha256).hexdigest()

            res = client.post(
                "/payments/verify",
                json={
                    "razorpay_payment_id": mock_payment_id,
                    "razorpay_order_id": order_id,
                    "razorpay_signature": valid_signature,
                },
                headers=_auth(stranger_token),
            )
            assert res.status_code == 403
        finally:
            _cleanup_user(owner.id)
            _cleanup_user(stranger.id)

    def test_webhook_amount_mismatch_does_not_activate_coverage(self):
        user, token = _make_user()
        try:
            order = client.post("/payments/create-order", json={}, headers=_auth(token))
            order_id = order.json()["order_id"]
            shift_id = order.json()["shift_id"]

            webhook_payload = {
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": f"pay_mismatch_{uuid.uuid4().hex[:8]}",
                            "order_id": order_id,
                            "amount": 999999,  # deliberately wrong
                        }
                    }
                },
            }
            res = client.post("/payments/webhook", json=webhook_payload)
            assert res.status_code == 200
            assert res.json().get("reason") == "amount_mismatch"

            db = SessionLocal()
            shift = db.query(Shift).filter(Shift.id == uuid.UUID(shift_id)).first()
            payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
            assert shift.status == ShiftStatus.PAUSED  # NOT activated
            assert payment.status == PaymentStatus.PENDING
            db.close()
        finally:
            _cleanup_user(user.id)

    def test_webhook_correct_amount_activates_coverage(self):
        user, token = _make_user()
        try:
            order = client.post("/payments/create-order", json={}, headers=_auth(token))
            order_id = order.json()["order_id"]
            shift_id = order.json()["shift_id"]
            correct_paise = order.json()["amount"]

            webhook_payload = {
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": f"pay_ok_{uuid.uuid4().hex[:8]}",
                            "order_id": order_id,
                            "amount": correct_paise,
                        }
                    }
                },
            }
            res = client.post("/payments/webhook", json=webhook_payload)
            assert res.status_code == 200
            assert res.json().get("reason") != "amount_mismatch"

            db = SessionLocal()
            shift = db.query(Shift).filter(Shift.id == uuid.UUID(shift_id)).first()
            payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
            assert shift.status == ShiftStatus.ACTIVE
            assert payment.status == PaymentStatus.SUCCESSFUL
            db.close()
        finally:
            _cleanup_user(user.id)
