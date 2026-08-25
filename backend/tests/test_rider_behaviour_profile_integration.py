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
from fastapi.testclient import TestClient
from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.shift_behaviour_summary import ShiftBehaviourSummary
from db.models.rider_behaviour_profile import RiderBehaviourProfile
from db.models.telemetry import TelemetryBatch, TelemetrySample
from db.models.enums import UserRole, ShiftStatus
from app.core.security import create_access_token
from app.services import rider_behaviour_profile_service as svc

client = TestClient(app)


@pytest.fixture
def test_rider():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id,
        email=f"test_profile_rider_{rand_str}@example.com",
        phone_number=f"+1996{rand_str}",
        hashed_password="hashed_test_pass",
        full_name="Test Profile Rider",
        role=UserRole.RIDER,
        wallet_balance=500.0,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id))
    yield user, token
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


def _insert_summary(rider_id, shift_id, created_at, is_valid=True, hard_braking_rate=2.0,
                     data_quality_score=0.9):
    db = SessionLocal()
    db.add(ShiftBehaviourSummary(
        shift_id=shift_id, rider_id=rider_id,
        duration_seconds=600, distance_km=5.0, sample_count=50,
        average_speed=30.0, max_speed=45.0,
        hard_braking_count=2, hard_acceleration_count=1, overspeeding_count=0, sharp_turn_count=1,
        hard_braking_rate=hard_braking_rate, hard_acceleration_rate=1.0,
        overspeeding_rate=0.5, sharp_turn_rate=1.0,
        max_g=1.5, accel_std=0.2, jerk_mean=0.1,
        sampling_density=5.0, data_quality_score=data_quality_score, is_valid=is_valid,
        created_at=created_at,
    ))
    db.commit()
    db.close()


def _make_dummy_shift(rider_id):
    db = SessionLocal()
    shift = Shift(
        rider_id=rider_id, status=ShiftStatus.COMPLETED,
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        end_time=datetime.now(timezone.utc), premium_amount=5.0,
        policy_number=f"POL-TESTPROF-{uuid.uuid4().hex[:8].upper()}", distance_km=5.0,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    shift_id = shift.id
    db.close()
    return shift_id


class TestRebuildRiderProfileColdStart:
    def test_no_summaries_returns_none_and_creates_no_row(self, test_rider):
        user, _ = test_rider
        db = SessionLocal()
        result = svc.rebuild_rider_profile(db, user.id)
        db.commit()
        assert result is None
        count = db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user.id).count()
        assert count == 0
        db.close()

    def test_only_invalid_summaries_returns_none(self, test_rider):
        user, _ = test_rider
        shift_id = _make_dummy_shift(user.id)
        _insert_summary(user.id, shift_id, datetime.now(timezone.utc), is_valid=False)

        db = SessionLocal()
        result = svc.rebuild_rider_profile(db, user.id)
        db.commit()
        assert result is None
        db.close()


class TestRebuildRiderProfilePersistence:
    def test_single_valid_summary_creates_a_profile(self, test_rider):
        user, _ = test_rider
        shift_id = _make_dummy_shift(user.id)
        _insert_summary(user.id, shift_id, datetime.now(timezone.utc))

        db = SessionLocal()
        profile = svc.rebuild_rider_profile(db, user.id)
        db.commit()
        assert profile is not None
        assert profile.based_on_valid_shift_count == 1
        db.close()

    def test_exactly_one_profile_row_per_rider(self, test_rider):
        user, _ = test_rider
        for i in range(3):
            shift_id = _make_dummy_shift(user.id)
            _insert_summary(user.id, shift_id, datetime.now(timezone.utc) - timedelta(hours=i))

        db = SessionLocal()
        svc.rebuild_rider_profile(db, user.id)
        db.commit()
        db.close()

        db2 = SessionLocal()
        count = db2.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user.id).count()
        assert count == 1
        db2.close()

    def test_repeated_rebuild_does_not_duplicate_rows(self, test_rider):
        user, _ = test_rider
        shift_id = _make_dummy_shift(user.id)
        _insert_summary(user.id, shift_id, datetime.now(timezone.utc))

        db = SessionLocal()
        svc.rebuild_rider_profile(db, user.id)
        db.commit()
        svc.rebuild_rider_profile(db, user.id)
        db.commit()
        svc.rebuild_rider_profile(db, user.id)
        db.commit()
        db.close()

        db2 = SessionLocal()
        count = db2.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user.id).count()
        assert count == 1
        db2.close()

    def test_profile_updates_after_a_new_shift(self, test_rider):
        user, _ = test_rider
        shift_id_1 = _make_dummy_shift(user.id)
        _insert_summary(user.id, shift_id_1, datetime.now(timezone.utc) - timedelta(hours=1), hard_braking_rate=2.0)

        db = SessionLocal()
        first_profile = svc.rebuild_rider_profile(db, user.id)
        db.commit()
        first_id = first_profile.id
        first_valid_count = first_profile.based_on_valid_shift_count
        db.close()

        shift_id_2 = _make_dummy_shift(user.id)
        _insert_summary(user.id, shift_id_2, datetime.now(timezone.utc), hard_braking_rate=20.0)

        db2 = SessionLocal()
        second_profile = svc.rebuild_rider_profile(db2, user.id)
        db2.commit()

        assert second_profile.id == first_id  # same row, updated in place
        assert second_profile.based_on_valid_shift_count == first_valid_count + 1
        db2.close()


class TestAntiLeakage:
    def test_summaries_after_as_of_cutoff_are_excluded(self, test_rider):
        user, _ = test_rider
        cutoff = datetime.now(timezone.utc)

        shift_before = _make_dummy_shift(user.id)
        _insert_summary(user.id, shift_before, cutoff - timedelta(hours=1))

        shift_after = _make_dummy_shift(user.id)
        _insert_summary(user.id, shift_after, cutoff + timedelta(hours=1))  # "future" relative to cutoff

        db = SessionLocal()
        profile = svc.rebuild_rider_profile(db, user.id, as_of=cutoff)
        db.commit()

        assert profile.based_on_shift_count == 1  # only the "before" shift counted
        db.close()

    def test_default_as_of_includes_everything_existing(self, test_rider):
        user, _ = test_rider
        shift_id = _make_dummy_shift(user.id)
        _insert_summary(user.id, shift_id, datetime.now(timezone.utc) - timedelta(minutes=1))

        db = SessionLocal()
        profile = svc.rebuild_rider_profile(db, user.id)  # no as_of given
        db.commit()
        assert profile.based_on_shift_count == 1
        db.close()


class TestShiftEndTriggersProfileRebuild:
    def test_ending_a_shift_creates_or_updates_the_rider_profile(self, test_rider):
        user, token = test_rider
        db = SessionLocal()
        shift = Shift(
            rider_id=user.id, status=ShiftStatus.ACTIVE,
            start_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            premium_amount=5.0, policy_number=f"POL-TRIGGER-{uuid.uuid4().hex[:8].upper()}",
            distance_km=0.0,
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)
        shift_id = shift.id

        batch = TelemetryBatch(
            shift_id=shift_id, batch_sequence=0, sample_count=5,
            start_timestamp=shift.start_time, end_timestamp=datetime.now(timezone.utc),
        )
        db.add(batch)
        db.flush()
        for i in range(5):
            db.add(TelemetrySample(
                batch_id=batch.id, timestamp=shift.start_time + timedelta(seconds=i),
                latitude=19.0760 + i * 0.0001, longitude=72.8777, gps_accuracy=5.0,
                speed=25.0, accel_x=0.0, accel_y=0.0, accel_z=9.81, gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
            ))
        db.commit()
        db.close()

        response = client.post(
            f"/shifts/{shift_id}/end",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert response.status_code == 200, response.text

        db2 = SessionLocal()
        try:
            profile = db2.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user.id).first()
            assert profile is not None
            assert profile.based_on_valid_shift_count >= 1
        finally:
            db2.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user.id).delete()
            db2.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.shift_id == shift_id).delete()
            batch_ids = [b.id for b in db2.query(TelemetryBatch).filter(TelemetryBatch.shift_id == shift_id).all()]
            if batch_ids:
                db2.query(TelemetrySample).filter(TelemetrySample.batch_id.in_(batch_ids)).delete(synchronize_session=False)
            db2.query(TelemetryBatch).filter(TelemetryBatch.shift_id == shift_id).delete()
            db2.query(Shift).filter(Shift.id == shift_id).delete()
            db2.commit()
            db2.close()


class TestIsolationFromCrashMlEngine:
    def test_service_module_does_not_import_ml_incident_engine(self):
        # Checks actual import statements only — the module's own docstring
        # names ml_incident_engine specifically to document that it's NOT
        # imported, so a bare substring check flags itself; parse imports
        # via ast instead.
        import ast
        import app.services.rider_behaviour_profile_service as module

        with open(module.__file__, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        assert not any("ml_incident_engine" in m for m in imported_modules)
        assert not any("ml_scoring_service" in m for m in imported_modules)
