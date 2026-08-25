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
import pytest
import app.core.config  # noqa: F401 — triggers load_dotenv("backend/env") before db.core.session reads DATABASE_URL
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.shift_behaviour_summary import ShiftBehaviourSummary
from db.models.rider_behaviour_profile import RiderBehaviourProfile
from db.models.enums import UserRole, ShiftStatus
from app.services import rider_behaviour_profile_service
from app.services import behaviour_risk_baseline_service as svc


@pytest.fixture
def test_rider():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id,
        email=f"test_risk_baseline_rider_{rand_str}@example.com",
        phone_number=f"+1995{rand_str}",
        hashed_password="hashed_test_pass",
        full_name="Test Risk Baseline Rider",
        role=UserRole.RIDER,
        wallet_balance=500.0,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    try:
        db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user.id).delete()
        db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.rider_id == user.id).delete()
        db.query(Shift).filter(Shift.rider_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _make_shift(rider_id):
    db = SessionLocal()
    shift = Shift(
        rider_id=rider_id, status=ShiftStatus.COMPLETED,
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        end_time=datetime.now(timezone.utc), premium_amount=5.0,
        policy_number=f"POL-RISKBASE-{uuid.uuid4().hex[:8].upper()}", distance_km=5.0,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    shift_id = shift.id
    db.close()
    return shift_id


def _insert_summary(rider_id, shift_id, created_at, hard_braking_rate=1.0, overspeeding_rate=0.5,
                     data_quality_score=0.9):
    db = SessionLocal()
    db.add(ShiftBehaviourSummary(
        shift_id=shift_id, rider_id=rider_id,
        duration_seconds=600, distance_km=5.0, sample_count=50,
        average_speed=30.0, max_speed=45.0,
        hard_braking_count=2, hard_acceleration_count=1, overspeeding_count=0, sharp_turn_count=1,
        hard_braking_rate=hard_braking_rate, hard_acceleration_rate=1.0,
        overspeeding_rate=overspeeding_rate, sharp_turn_rate=1.0,
        max_g=1.4, accel_std=0.2, jerk_mean=0.1,
        sampling_density=5.0, data_quality_score=data_quality_score, is_valid=True,
        created_at=created_at,
    ))
    db.commit()
    db.close()


class TestRealDbBackedProfileDecimalSafety:
    """This is the exact test category that caught a real Decimal/float
    bug in Phase 2 — plain-float unit fixtures cannot exercise
    SQLAlchemy's Numeric -> decimal.Decimal return type."""

    def test_assess_rider_risk_does_not_crash_on_a_real_orm_profile(self, test_rider):
        for i in range(6):
            shift_id = _make_shift(test_rider.id)
            _insert_summary(test_rider.id, shift_id, datetime.now(timezone.utc) - timedelta(hours=i))

        db = SessionLocal()
        rider_behaviour_profile_service.rebuild_rider_profile(db, test_rider.id)
        db.commit()

        profile = db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == test_rider.id).first()
        assert profile is not None

        # The actual regression check: every Numeric-typed field on a real
        # ORM row is decimal.Decimal, not float, until cast.
        import decimal
        assert isinstance(profile.recent_max_g, decimal.Decimal)
        assert isinstance(profile.overall_behaviour_score, decimal.Decimal)

        result = svc.assess_rider_risk(profile)  # must not raise
        assert result.risk_score is not None
        assert 0.0 <= result.risk_score <= 100.0
        db.close()

    def test_result_fields_are_plain_python_floats_not_decimal(self, test_rider):
        shift_id = _make_shift(test_rider.id)
        _insert_summary(test_rider.id, shift_id, datetime.now(timezone.utc))

        db = SessionLocal()
        rider_behaviour_profile_service.rebuild_rider_profile(db, test_rider.id)
        db.commit()
        profile = db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == test_rider.id).first()

        result = svc.assess_rider_risk(profile)
        assert isinstance(result.risk_score, float)
        assert isinstance(result.confidence, float)
        for c in result.contributors:
            assert isinstance(c.impact, float)
        db.close()


class TestColdStartWithRealDb:
    def test_rider_with_no_profile_row_gets_cold_start(self, test_rider):
        db = SessionLocal()
        profile = db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == test_rider.id).first()
        assert profile is None  # no shifts ended yet

        result = svc.assess_rider_risk(profile)
        assert result.is_cold_start is True
        db.close()


class TestRealMultiShiftAggregationFeedsRiskScore:
    def test_consistently_safe_history_scores_low_via_real_profile(self, test_rider):
        for i in range(8):
            shift_id = _make_shift(test_rider.id)
            _insert_summary(
                test_rider.id, shift_id, datetime.now(timezone.utc) - timedelta(hours=i),
                hard_braking_rate=0.3, overspeeding_rate=0.0, data_quality_score=0.95,
            )

        db = SessionLocal()
        rider_behaviour_profile_service.rebuild_rider_profile(db, test_rider.id)
        db.commit()
        profile = db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == test_rider.id).first()

        result = svc.assess_rider_risk(profile)
        assert result.risk_band in (svc.RISK_BAND_VERY_LOW, svc.RISK_BAND_LOW)
        assert result.confidence > 0.5
        db.close()

    def test_low_history_real_profile_has_low_confidence(self, test_rider):
        shift_id = _make_shift(test_rider.id)
        _insert_summary(test_rider.id, shift_id, datetime.now(timezone.utc))

        db = SessionLocal()
        rider_behaviour_profile_service.rebuild_rider_profile(db, test_rider.id)
        db.commit()
        profile = db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == test_rider.id).first()

        result = svc.assess_rider_risk(profile)
        assert result.confidence < 0.3  # only 1 valid shift
        assert result.risk_score is not None  # still a real estimate, not cold-start
        db.close()
