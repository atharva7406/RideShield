"""
Final small Phase 7 addition — GET /shifts/premium-preview.

Read-only preview of PremiumPricingService's output, reusing
calculate_premium_quote() exactly (no formula duplication). These tests
focus on: authentication/isolation, zero side effects, and price parity
with the real payment flow — the pricing formula itself is already
covered exhaustively in test_premium_pricing_service.py.
"""
import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

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
from db.models.enums import UserRole, ShiftStatus
from app.core.security import create_access_token
from app.services import razorpay_service, rider_behaviour_profile_service
from app.services import helmet_verification_service as helmet_svc
from db.models.helmet_verification import HelmetVerification

client = TestClient(app)


def _make_user():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id, email=f"test_preview_{rand_str}@example.com",
        phone_number=f"+1992{rand_str}", hashed_password="hashed_test_pass",
        full_name="Preview Test Rider", role=UserRole.RIDER, wallet_balance=500.0, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    # This file tests premium PREVIEW wiring, not the helmet gate (see
    # test_helmet_gate.py) — grant a passed verification up front so the
    # tests that exercise the real /shifts/start or /payments/create-order
    # endpoints for parity checks aren't blocked by the mandatory gate.
    db2 = SessionLocal()
    result = helmet_svc.HelmetVerificationResult("full_face_helmet", 0.95, True, "test-v1")
    helmet_svc.record_verification(db2, rand_id, result)
    db2.commit()
    db2.close()

    return user, create_access_token(subject=str(user.id))


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


def _make_completed_shift_with_summary(rider_id, hard_braking_rate, overspeeding_rate, hours_ago):
    db = SessionLocal()
    shift = Shift(
        rider_id=rider_id, status=ShiftStatus.COMPLETED,
        start_time=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        end_time=datetime.now(timezone.utc) - timedelta(hours=hours_ago - 1),
        premium_amount=5.0,
        policy_number=f"POL-PREVIEW-{uuid.uuid4().hex[:8].upper()}", distance_km=5.0,
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


def _forbid_razorpay(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("razorpay_service.create_razorpay_order must NOT be called by the preview endpoint")
    monkeypatch.setattr(razorpay_service, "create_razorpay_order", _boom)


def _snapshot_counts(rider_id):
    db = SessionLocal()
    counts = {
        "shifts": db.query(Shift).filter(Shift.rider_id == rider_id).count(),
        "payments": db.query(Payment).filter(Payment.rider_id == rider_id).count(),
        "quotes": db.query(PremiumQuoteRecord).filter(PremiumQuoteRecord.rider_id == rider_id).count(),
    }
    wallet = db.query(User).filter(User.id == rider_id).first().wallet_balance
    db.close()
    return counts, wallet


class TestAuthAndIsolation:
    def test_unauthorized_request_rejected(self):
        res = client.get("/shifts/premium-preview")
        assert res.status_code in (401, 403)

    def test_two_riders_get_independent_previews(self, monkeypatch):
        _forbid_razorpay(monkeypatch)
        safe_user, safe_token = _make_user()
        risky_user, risky_token = _make_user()
        try:
            _build_profile(safe_user.id, hard_braking_rate=0.0, overspeeding_rate=0.0)
            _build_profile(risky_user.id, hard_braking_rate=15.0, overspeeding_rate=10.0)

            safe_res = client.get("/shifts/premium-preview", headers=_auth(safe_token))
            risky_res = client.get("/shifts/premium-preview", headers=_auth(risky_token))
            assert safe_res.status_code == 200 and risky_res.status_code == 200
            assert risky_res.json()["final_premium"] >= safe_res.json()["final_premium"]
        finally:
            _cleanup_user(safe_user.id)
            _cleanup_user(risky_user.id)


class TestZeroSideEffects:
    def test_preview_creates_nothing_and_deducts_nothing(self, monkeypatch):
        _forbid_razorpay(monkeypatch)
        user, token = _make_user()
        try:
            before_counts, before_wallet = _snapshot_counts(user.id)
            res = client.get("/shifts/premium-preview", headers=_auth(token))
            assert res.status_code == 200, res.text
            after_counts, after_wallet = _snapshot_counts(user.id)

            assert after_counts == before_counts == {"shifts": 0, "payments": 0, "quotes": 0}
            assert after_wallet == before_wallet == 500.0
        finally:
            _cleanup_user(user.id)

    def test_preview_after_building_real_history_still_has_zero_side_effects(self, monkeypatch):
        _forbid_razorpay(monkeypatch)
        user, token = _make_user()
        try:
            _build_profile(user.id, hard_braking_rate=5.0, overspeeding_rate=2.0)
            before_counts, before_wallet = _snapshot_counts(user.id)

            for _ in range(3):  # calling repeatedly must not accumulate anything
                res = client.get("/shifts/premium-preview", headers=_auth(token))
                assert res.status_code == 200

            after_counts, after_wallet = _snapshot_counts(user.id)
            assert after_counts == before_counts
            assert after_wallet == before_wallet

            db = SessionLocal()
            profile_before = db.query(RiderBehaviourProfile).filter(
                RiderBehaviourProfile.rider_id == user.id
            ).first()
            db.close()
            assert profile_before is not None  # unchanged, not deleted/reset either
        finally:
            _cleanup_user(user.id)


class TestPricingScenarios:
    def test_cold_start_preview(self, monkeypatch):
        _forbid_razorpay(monkeypatch)
        user, token = _make_user()
        try:
            res = client.get("/shifts/premium-preview", headers=_auth(token))
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["is_cold_start"] is True
            assert data["pricing_mode"] == "COLD_START_DEFAULT"
            assert data["final_premium"] == 5.00
            assert data["risk_score"] is None
            assert data["base_premium"] == 5.00
        finally:
            _cleanup_user(user.id)

    def test_safe_rider_preview(self, monkeypatch):
        _forbid_razorpay(monkeypatch)
        user, token = _make_user()
        try:
            _build_profile(user.id, hard_braking_rate=0.0, overspeeding_rate=0.0)
            res = client.get("/shifts/premium-preview", headers=_auth(token))
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["is_cold_start"] is False
            assert data["risk_score"] is not None
            assert data["final_premium"] <= data["base_premium"]  # safe rider: discount or neutral
        finally:
            _cleanup_user(user.id)

    def test_risky_rider_preview(self, monkeypatch):
        """Compares a risky rider AGAINST a safe rider, not against a fixed
        absolute threshold — the live model (XGBoost, unmodified per this
        task's constraints) may score a hand-crafted synthetic input
        differently than the simpler deterministic baseline would, so the
        only claim this test can safely make is the relative one: riskier
        behaviour never prices below safer behaviour, same pattern already
        used in test_phase7_server_authoritative_premium.py."""
        _forbid_razorpay(monkeypatch)
        safe_user, safe_token = _make_user()
        risky_user, risky_token = _make_user()
        try:
            _build_profile(safe_user.id, hard_braking_rate=0.0, overspeeding_rate=0.0)
            _build_profile(risky_user.id, hard_braking_rate=15.0, overspeeding_rate=10.0)

            safe_res = client.get("/shifts/premium-preview", headers=_auth(safe_token))
            risky_res = client.get("/shifts/premium-preview", headers=_auth(risky_token))
            assert safe_res.status_code == 200 and risky_res.status_code == 200

            risky_data = risky_res.json()
            assert risky_data["is_cold_start"] is False
            assert risky_data["risk_score"] is not None
            assert risky_data["explanation"]
            assert risky_data["final_premium"] >= safe_res.json()["final_premium"]
        finally:
            _cleanup_user(safe_user.id)
            _cleanup_user(risky_user.id)

    def test_ml_failure_falls_back_to_baseline_in_preview(self, monkeypatch):
        _forbid_razorpay(monkeypatch)
        from app.services import rider_behaviour_risk_service as risk_svc

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated model failure")

        monkeypatch.setattr(risk_svc, "is_ml_available", lambda: True)
        monkeypatch.setattr(risk_svc, "predict_calibrated_from_features", _boom)

        user, token = _make_user()
        try:
            _build_profile(user.id, hard_braking_rate=5.0, overspeeding_rate=2.0)
            res = client.get("/shifts/premium-preview", headers=_auth(token))
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["scoring_method"] == "deterministic_baseline"
            assert data["final_premium"] is not None
        finally:
            _cleanup_user(user.id)


class TestPreviewMatchesActualPayment:
    def test_preview_equals_wallet_start_premium(self, monkeypatch):
        _forbid_razorpay(monkeypatch)
        user, token = _make_user()
        try:
            _build_profile(user.id, hard_braking_rate=8.0, overspeeding_rate=4.0)

            preview = client.get("/shifts/premium-preview", headers=_auth(token))
            assert preview.status_code == 200
            previewed_premium = preview.json()["final_premium"]

            start = client.post("/shifts/start", json={"payment_method": "wallet"}, headers=_auth(token))
            assert start.status_code == 200
            charged_premium = float(start.json()["premium_amount"])

            assert previewed_premium == pytest.approx(charged_premium)
        finally:
            _cleanup_user(user.id)

    def test_preview_equals_create_order_amount(self, monkeypatch):
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

        user, token = _make_user()
        try:
            _build_profile(user.id, hard_braking_rate=8.0, overspeeding_rate=4.0)

            preview = client.get("/shifts/premium-preview", headers=_auth(token))
            previewed_paise = round(preview.json()["final_premium"] * 100)

            order = client.post("/payments/create-order", json={}, headers=_auth(token))
            assert order.status_code == 200
            assert order.json()["amount"] == previewed_paise
        finally:
            _cleanup_user(user.id)
