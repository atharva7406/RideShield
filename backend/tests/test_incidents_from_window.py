import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.incident import Incident
from db.models.enums import UserRole, ShiftStatus
from app.core.security import create_access_token
from app.services import ml_scoring_service

client = TestClient(app)


@pytest.fixture(scope="module")
def test_rider_user():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id,
        email=f"test_window_rider_{rand_str}@example.com",
        phone_number=f"+1998{rand_str}",
        hashed_password="hashed_test_pass",
        full_name="Test Window Rider",
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
        db.query(Incident).filter(Incident.rider_id == user.id).delete()
        db.query(Shift).filter(Shift.rider_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@pytest.fixture
def active_shift(test_rider_user):
    user, token = test_rider_user
    db = SessionLocal()
    shift = Shift(
        rider_id=user.id,
        status=ShiftStatus.ACTIVE,
        start_time=datetime.now(timezone.utc),
        premium_amount=5.0,
        policy_number=f"POL-TESTWIN-{uuid.uuid4().hex[:8].upper()}",
        distance_km=0.0,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    shift_id = shift.id
    db.close()

    yield shift_id

    db = SessionLocal()
    try:
        db.query(Incident).filter(Incident.shift_id == shift_id).delete()
        db.query(Shift).filter(Shift.id == shift_id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _accel_samples(n=20, spike_at=None, spike_mag=(40.0, 0.0, 9.81)):
    samples = []
    for i in range(n):
        if spike_at is not None and i == spike_at:
            x, y, z = spike_mag
        else:
            x, y, z = 0.1, 0.1, 9.81
        samples.append({"timestamp": i * 20.0, "x": x, "y": y, "z": z})
    return samples


class TestCreateIncidentFromWindow:
    def test_requires_auth(self, active_shift):
        response = client.post("/incidents/from-window", json={
            "shift_id": str(active_shift),
            "accel_samples": _accel_samples(),
        })
        assert response.status_code == 401

    def test_404_for_nonexistent_shift(self, test_rider_user):
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(uuid.uuid4()),
                "accel_samples": _accel_samples(),
            },
        )
        assert response.status_code == 404

    def test_422_for_too_few_accel_samples(self, test_rider_user, active_shift):
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _accel_samples(n=2),
            },
        )
        assert response.status_code == 422

    def test_creates_incident_from_a_crash_like_window(self, test_rider_user, active_shift):
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _accel_samples(n=100, spike_at=50, spike_mag=(50.0, 0.0, 9.81)),
                "gyro_samples": _accel_samples(n=100, spike_at=50, spike_mag=(220.0, 0.0, 0.0)),
                "gps_samples": [
                    {"timestamp": i * 200.0, "latitude": 19.076 + i * 1e-5, "longitude": 72.877,
                     "speed": max(0.0, 30.0 - i * 3.0)}
                    for i in range(10)
                ],
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["scoring_method"] in ("ml", "rule_based_fallback")
        assert 0.0 <= body["confidence_score"] <= 1.0
        assert uuid.UUID(body["incident_id"])

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == uuid.UUID(body["incident_id"])).first()
            assert incident is not None
            assert incident.shift_id == active_shift
            assert float(incident.confidence_score) == pytest.approx(body["confidence_score"], abs=0.01)
        finally:
            db.close()

    def test_duplicate_within_60s_is_suppressed(self, test_rider_user, active_shift):
        _, token = test_rider_user
        payload = {
            "shift_id": str(active_shift),
            "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
        }
        first = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)
        second = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["incident_id"] == first.json()["incident_id"]
        assert second.json()["scoring_method"] == "duplicate_suppressed"

    def test_ml_unavailable_falls_back_and_still_creates_incident(self, monkeypatch, test_rider_user, active_shift):
        monkeypatch.setattr(ml_scoring_service, "is_ml_available", lambda: False)
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(50.0, 0.0, 9.81)),
            },
        )
        assert response.status_code == 200
        assert response.json()["scoring_method"] == "rule_based_fallback"
        assert response.json()["predicted_class"] is None
