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
from db.models.claim import Claim
from db.models.enums import UserRole, ShiftStatus, IncidentStatus
from app.core.security import create_access_token
from app.services import ml_scoring_service
from app.api import incidents as incidents_api

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_real_escalation(monkeypatch):
    async def _noop(incident_id):
        return None
    monkeypatch.setattr(incidents_api, "run_incident_escalation", _noop)


@pytest.fixture(scope="module")
def test_rider_user():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id,
        email=f"test_decision_engine_{rand_str}@example.com",
        phone_number=f"+1997{rand_str}",
        hashed_password="hashed_test_pass",
        full_name="Test Decision Engine Rider",
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
        db.query(Claim).filter(Claim.rider_id == user.id).delete()
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
        policy_number=f"POL-DECISION-{uuid.uuid4().hex[:8].upper()}",
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
        db.query(Claim).filter(Claim.shift_id == shift_id).delete()
        db.query(Incident).filter(Incident.shift_id == shift_id).delete()
        db.query(Shift).filter(Shift.id == shift_id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _good_quality_accel_samples(n=100, spike_at=50, spike_mag=(50.0, 0.0, 9.81)):
    """~50Hz, well-formed, with a real spike — a 'good' window."""
    samples = []
    for i in range(n):
        x, y, z = spike_mag if i == spike_at else (0.1, 0.1, 9.81)
        samples.append({"timestamp": i * 20.0, "x": x, "y": y, "z": z})
    return samples


def _good_quality_gyro_samples(n=100, spike_at=50):
    samples = []
    for i in range(n):
        x = 220.0 if i == spike_at else 1.0
        samples.append({"timestamp": i * 20.0, "x": x, "y": 0.0, "z": 0.0})
    return samples


def _good_quality_gps_samples(n=10):
    return [
        {"timestamp": i * 200.0, "latitude": 19.076 + i * 1e-5, "longitude": 72.877, "speed": max(0.0, 40.0 - i * 4.0)}
        for i in range(n)
    ]


def _poor_quality_accel_samples():
    """Sparse, far-apart, well under the 20Hz floor — a 'degraded' window."""
    return [
        {"timestamp": 0.0, "x": 0.1, "y": 0.1, "z": 9.81},
        {"timestamp": 800.0, "x": 0.1, "y": 0.1, "z": 9.81},
        {"timestamp": 1600.0, "x": 45.0, "y": 0.0, "z": 9.81},
        {"timestamp": 2400.0, "x": 0.1, "y": 0.1, "z": 9.81},
    ]


class TestGoodQualityOnlineCrash:
    def test_creates_incident_with_good_window_quality_and_recorded_evidence(self, test_rider_user, active_shift):
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _good_quality_accel_samples(),
                "gyro_samples": _good_quality_gyro_samples(),
                "gps_samples": _good_quality_gps_samples(),
            },
        )
        assert response.status_code == 200, response.text
        incident_id = response.json()["incident_id"]

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == uuid.UUID(incident_id)).first()
            assert incident.window_quality == "good"
            assert incident.decision_confidence in ("high", "medium", "low")
            # Evidence should be recorded, not left blank, for a real spike.
            assert incident.decision_evidence is not None
        finally:
            db.close()


class TestPoorQualityWindow:
    def test_degraded_window_still_creates_incident_and_is_flagged_not_rejected(self, test_rider_user, active_shift):
        """The critical safety property: a poor-quality window must NEVER
        be silently rejected/discarded — Tier 0 already alerted the rider
        on-device before this window even reached the backend."""
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={"shift_id": str(active_shift), "accel_samples": _poor_quality_accel_samples()},
        )
        assert response.status_code == 200, response.text
        incident_id = response.json()["incident_id"]

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == uuid.UUID(incident_id)).first()
            assert incident.window_quality == "degraded"
            assert incident.status == IncidentStatus.DETECTED  # created and escalatable, not discarded
        finally:
            db.close()


class TestMlFailureFallback:
    def test_ml_unavailable_still_produces_a_confidence_label_and_creates_incident(
        self, monkeypatch, test_rider_user, active_shift
    ):
        monkeypatch.setattr(ml_scoring_service, "is_ml_available", lambda: False)
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _good_quality_accel_samples(),
                "gyro_samples": _good_quality_gyro_samples(),
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["scoring_method"] == "rule_based_fallback"

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == uuid.UUID(response.json()["incident_id"])).first()
            assert incident.decision_confidence in ("high", "medium", "low")
        finally:
            db.close()


class TestFalsePositiveNoClaimEligibility:
    def test_false_positive_incident_cannot_have_a_claim_filed(self, test_rider_user, active_shift):
        _, token = test_rider_user
        create_resp = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={"shift_id": str(active_shift), "accel_samples": _good_quality_accel_samples()},
        )
        incident_id = create_resp.json()["incident_id"]

        okay_resp = client.post(f"/incidents/{incident_id}/okay", headers=_auth_headers(token))
        assert okay_resp.status_code == 200
        assert okay_resp.json()["status"] == "FALSE_POSITIVE"

        claim_resp = client.post(
            "/claims",
            headers=_auth_headers(token),
            json={"incident_id": incident_id, "claimed_amount": 5000.0},
        )
        assert claim_resp.status_code == 400
        assert "false positive" in claim_resp.json()["detail"].lower()


class TestVerifiedAccidentClaimEligibility:
    def test_verified_accident_incident_can_have_a_claim_filed(self, test_rider_user, active_shift):
        _, token = test_rider_user
        create_resp = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={"shift_id": str(active_shift), "accel_samples": _good_quality_accel_samples()},
        )
        incident_id = create_resp.json()["incident_id"]

        help_resp = client.post(f"/incidents/{incident_id}/help", headers=_auth_headers(token))
        assert help_resp.status_code == 200
        assert help_resp.json()["status"] == "VERIFIED_ACCIDENT"

        claim_resp = client.post(
            "/claims",
            headers=_auth_headers(token),
            json={"incident_id": incident_id, "claimed_amount": 5000.0},
        )
        assert claim_resp.status_code == 200, claim_resp.text


class TestDuplicateRetryStillOneIncidentUnderDecisionEngine:
    def test_duplicate_retry_with_evidence_fields_still_one_incident(self, test_rider_user, active_shift):
        """Regression: Phase 4's new fields must not interfere with Phase 2's
        exactly-once idempotency guarantee."""
        _, token = test_rider_user
        client_id = f"decision-engine-retry-{uuid.uuid4()}"
        payload = {
            "shift_id": str(active_shift),
            "accel_samples": _good_quality_accel_samples(),
            "client_incident_id": client_id,
        }
        first = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)
        second = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)

        assert first.json()["incident_id"] == second.json()["incident_id"]

        db = SessionLocal()
        try:
            count = db.query(Incident).filter(Incident.client_incident_id == client_id).count()
            assert count == 1
        finally:
            db.close()
