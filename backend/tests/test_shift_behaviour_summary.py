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
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.shift_behaviour_summary import ShiftBehaviourSummary
from db.models.telemetry import TelemetryBatch, TelemetrySample
from db.models.enums import UserRole, ShiftStatus
from app.core.security import create_access_token

client = TestClient(app)


@pytest.fixture(scope="module")
def test_rider_user():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id,
        email=f"test_behaviour_rider_{rand_str}@example.com",
        phone_number=f"+1997{rand_str}",
        hashed_password="hashed_test_pass",
        full_name="Test Behaviour Rider",
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
        db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.rider_id == user.id).delete()
        db.query(Shift).filter(Shift.rider_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_active_shift(rider_id, start_time=None):
    db = SessionLocal()
    shift = Shift(
        rider_id=rider_id,
        status=ShiftStatus.ACTIVE,
        start_time=start_time or (datetime.now(timezone.utc) - timedelta(minutes=10)),
        premium_amount=5.0,
        policy_number=f"POL-TESTBEH-{uuid.uuid4().hex[:8].upper()}",
        distance_km=0.0,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    shift_id = shift.id
    db.close()
    return shift_id


def _insert_telemetry(shift_id, points, start_time):
    """points: list of (lat, lng, speed, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z),
    one per second starting at start_time."""
    db = SessionLocal()
    batch = TelemetryBatch(
        shift_id=shift_id,
        batch_sequence=0,
        sample_count=len(points),
        start_timestamp=start_time,
        end_timestamp=start_time + timedelta(seconds=len(points) - 1),
    )
    db.add(batch)
    db.flush()
    for i, (lat, lng, speed, ax, ay, az, gx, gy, gz) in enumerate(points):
        db.add(TelemetrySample(
            batch_id=batch.id,
            timestamp=start_time + timedelta(seconds=i),
            latitude=lat, longitude=lng, gps_accuracy=5.0,
            speed=speed, accel_x=ax, accel_y=ay, accel_z=az,
            gyro_x=gx, gyro_y=gy, gyro_z=gz,
        ))
    db.commit()
    db.close()


def _cleanup_shift(shift_id):
    db = SessionLocal()
    try:
        db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.shift_id == shift_id).delete()
        batch_ids = [b.id for b in db.query(TelemetryBatch).filter(TelemetryBatch.shift_id == shift_id).all()]
        if batch_ids:
            db.query(TelemetrySample).filter(TelemetrySample.batch_id.in_(batch_ids)).delete(synchronize_session=False)
        db.query(TelemetryBatch).filter(TelemetryBatch.shift_id == shift_id).delete()
        db.query(Shift).filter(Shift.id == shift_id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class TestShiftEndCreatesBehaviourSummary:
    def test_creates_summary_with_sane_values(self, test_rider_user):
        _, token = test_rider_user
        start_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        shift_id = _create_active_shift(test_rider_user[0].id, start_time)
        points = [
            (19.0760 + i * 0.0001, 72.8777, 30.0, 0.0, 0.0, 9.81, 0.0, 0.0, 0.0)
            for i in range(20)
        ]
        _insert_telemetry(shift_id, points, start_time)

        response = client.post(
            f"/shifts/{shift_id}/end",
            headers=_auth_headers(token),
            json={},
        )
        assert response.status_code == 200, response.text

        db = SessionLocal()
        try:
            summary = db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.shift_id == shift_id).first()
            assert summary is not None
            assert summary.sample_count == 20
            assert summary.rider_id == test_rider_user[0].id
            assert float(summary.distance_km) > 0
            assert summary.average_speed == pytest.approx(30.0, abs=0.5)
        finally:
            db.close()
        _cleanup_shift(shift_id)

    def test_client_provided_distance_cannot_override_server_distance(self, test_rider_user):
        _, token = test_rider_user
        start_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        shift_id = _create_active_shift(test_rider_user[0].id, start_time)
        # A real, small GPS movement — server should compute a small distance,
        # nowhere near the huge bogus value the client will claim.
        points = [
            (19.0760, 72.8777, 20.0, 0.0, 0.0, 9.81, 0.0, 0.0, 0.0),
            (19.0761, 72.8778, 20.0, 0.0, 0.0, 9.81, 0.0, 0.0, 0.0),
        ]
        _insert_telemetry(shift_id, points, start_time)

        response = client.post(
            f"/shifts/{shift_id}/end",
            headers=_auth_headers(token),
            json={"distance_km": 999999.0},  # bogus client-supplied value
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["distance_km"] < 1.0  # nowhere near the claimed 999999

        db = SessionLocal()
        try:
            shift = db.query(Shift).filter(Shift.id == shift_id).first()
            assert float(shift.distance_km) < 1.0
            summary = db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.shift_id == shift_id).first()
            assert float(summary.distance_km) < 1.0
        finally:
            db.close()
        _cleanup_shift(shift_id)

    def test_shift_with_no_telemetry_still_completes(self, test_rider_user):
        _, token = test_rider_user
        shift_id = _create_active_shift(test_rider_user[0].id)

        response = client.post(f"/shifts/{shift_id}/end", headers=_auth_headers(token), json={})
        assert response.status_code == 200

        db = SessionLocal()
        try:
            summary = db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.shift_id == shift_id).first()
            assert summary is not None
            assert summary.sample_count == 0
            assert summary.is_valid is False  # zero samples must never be flagged valid
            assert float(summary.distance_km) == 0.0
        finally:
            db.close()
        _cleanup_shift(shift_id)

    def test_repeated_end_request_returns_400_and_does_not_duplicate_summary(self, test_rider_user):
        _, token = test_rider_user
        start_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        shift_id = _create_active_shift(test_rider_user[0].id, start_time)
        points = [(19.0760, 72.8777, 20.0, 0.0, 0.0, 9.81, 0.0, 0.0, 0.0) for _ in range(5)]
        _insert_telemetry(shift_id, points, start_time)

        first = client.post(f"/shifts/{shift_id}/end", headers=_auth_headers(token), json={})
        second = client.post(f"/shifts/{shift_id}/end", headers=_auth_headers(token), json={})

        assert first.status_code == 200
        assert second.status_code == 400  # already COMPLETED — existing shift-status guard

        db = SessionLocal()
        try:
            count = db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.shift_id == shift_id).count()
            assert count == 1
        finally:
            db.close()
        _cleanup_shift(shift_id)


class TestDuplicateSummaryPreventedAtDbLevel:
    """Exercises the UNIQUE constraint directly — the hard backstop behind
    the endpoint's existing_summary pre-check, for the race-condition case
    two concurrent end-shift requests could hit (both reading "no summary
    yet" before either commits)."""

    def test_unique_constraint_blocks_a_second_summary_for_the_same_shift(self, test_rider_user):
        shift_id = _create_active_shift(test_rider_user[0].id)
        db = SessionLocal()
        try:
            db.add(ShiftBehaviourSummary(
                shift_id=shift_id, rider_id=test_rider_user[0].id,
                duration_seconds=60, distance_km=1.0, sample_count=5,
                average_speed=20.0, max_speed=25.0,
                hard_braking_count=0, hard_acceleration_count=0,
                overspeeding_count=0, sharp_turn_count=0,
                hard_braking_rate=0.0, hard_acceleration_rate=0.0,
                overspeeding_rate=0.0, sharp_turn_rate=0.0,
                max_g=1.0, accel_std=0.0, jerk_mean=0.0,
                sampling_density=5.0, data_quality_score=0.9, is_valid=True,
            ))
            db.commit()

            db.add(ShiftBehaviourSummary(
                shift_id=shift_id, rider_id=test_rider_user[0].id,
                duration_seconds=60, distance_km=1.0, sample_count=5,
                average_speed=20.0, max_speed=25.0,
                hard_braking_count=0, hard_acceleration_count=0,
                overspeeding_count=0, sharp_turn_count=0,
                hard_braking_rate=0.0, hard_acceleration_rate=0.0,
                overspeeding_rate=0.0, sharp_turn_rate=0.0,
                max_g=1.0, accel_std=0.0, jerk_mean=0.0,
                sampling_density=5.0, data_quality_score=0.9, is_valid=True,
            ))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
        _cleanup_shift(shift_id)
