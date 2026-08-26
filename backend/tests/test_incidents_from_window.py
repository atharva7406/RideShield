import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import threading
import uuid
from datetime import datetime, timezone
import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.incident import Incident
from db.models.enums import UserRole, ShiftStatus, IncidentStatus
from app.core.security import create_access_token
from app.schemas import CrashWindowSubmission
from app.services import ml_scoring_service
from app.api import incidents as incidents_api

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_real_escalation(monkeypatch):
    """POST /incidents/from-window schedules run_incident_escalation as a
    FastAPI background task, which TestClient runs synchronously as part
    of the request/response cycle — without this, every test hitting the
    endpoint would block for real (60+60+60s) on the WhatsApp/SMS/voice-
    call wait ladder. Replaced with a no-op so these tests only verify
    THIS endpoint's own behaviour; the escalation ladder itself has its
    own coverage where it belongs."""
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

    def test_client_incident_id_is_persisted_on_the_incident(self, test_rider_user, active_shift):
        """Phase 1 (offline incident queue): the client mints client_incident_id
        at Tier-0 detection time and it must survive to the stored Incident
        row unchanged, so a later retry/sync can be correlated back to the
        same physical event (Phase 2 will add uniqueness enforcement)."""
        _, token = test_rider_user
        client_id = "11111111-2222-4333-8444-555555555555"
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
                "client_incident_id": client_id,
            },
        )
        assert response.status_code == 200, response.text
        incident_id = response.json()["incident_id"]

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == uuid.UUID(incident_id)).first()
            assert incident is not None
            assert incident.client_incident_id == client_id
        finally:
            db.close()

    def test_client_incident_id_is_optional(self, test_rider_user, active_shift):
        """Old app builds that don't send client_incident_id yet must keep working."""
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
            },
        )
        assert response.status_code == 200, response.text

    def test_window_metadata_is_accepted_and_optional(self, test_rider_user, active_shift):
        """Phase 3 (PRE/IMPACT/POST capture): window_metadata is additive
        and backward-compatible — a submission with it must succeed exactly
        like one without it, and an incomplete-flagged window must NOT be
        rejected (only ml_scoring_service's own sample-count check does
        that, unchanged from before this phase)."""
        _, token = test_rider_user
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
                "window_metadata": {
                    "trigger_timestamp": 1000.0,
                    "window_start_timestamp": 1.0,
                    "window_end_timestamp": 2000.0,
                    "accel_sample_count": 50,
                    "gyro_sample_count": 0,
                    "gps_sample_count": 0,
                    "observed_accel_hz": 50.0,
                    "observed_gyro_hz": None,
                    "observed_gps_hz": None,
                    "completeness": {
                        "is_complete": False,
                        "has_pre_event_data": True,
                        "has_post_event_data": False,
                        "has_gyro": False,
                        "has_gps": False,
                        "is_low_sampling_rate": False,
                        "reasons": ["insufficient_post_event_samples", "missing_gyro", "missing_gps"],
                    },
                },
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["scoring_method"] in ("ml", "rule_based_fallback")

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


class TestExactlyOnceIncidentSync:
    """Phase 2: client_incident_id + retry queue -> exactly one Incident per
    physical crash, regardless of how many times the phone retries or
    whether two retries race each other."""

    def test_first_upload_creates_incident(self, test_rider_user, active_shift):
        _, token = test_rider_user
        client_id = f"once-{uuid.uuid4()}"
        response = client.post(
            "/incidents/from-window",
            headers=_auth_headers(token),
            json={
                "shift_id": str(active_shift),
                "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
                "client_incident_id": client_id,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["scoring_method"] in ("ml", "rule_based_fallback")

    def test_same_id_uploaded_twice_creates_one_incident(self, test_rider_user, active_shift):
        _, token = test_rider_user
        client_id = f"twice-{uuid.uuid4()}"
        payload = {
            "shift_id": str(active_shift),
            "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
            "client_incident_id": client_id,
        }
        first = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)
        second = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["incident_id"] == first.json()["incident_id"]
        assert second.json()["scoring_method"] == "duplicate_suppressed"

        db = SessionLocal()
        try:
            count = db.query(Incident).filter(Incident.client_incident_id == client_id).count()
            assert count == 1
        finally:
            db.close()

    def test_same_id_uploaded_many_times_still_one_incident(self, test_rider_user, active_shift):
        _, token = test_rider_user
        client_id = f"many-{uuid.uuid4()}"
        payload = {
            "shift_id": str(active_shift),
            "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
            "client_incident_id": client_id,
        }
        responses = [
            client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)
            for _ in range(8)
        ]
        assert all(r.status_code == 200 for r in responses)
        incident_ids = {r.json()["incident_id"] for r in responses}
        assert len(incident_ids) == 1
        assert [r.json()["scoring_method"] for r in responses][1:] == ["duplicate_suppressed"] * 7

    def test_different_ids_create_separate_incidents(self, test_rider_user, active_shift):
        _, token = test_rider_user
        payload_a = {
            "shift_id": str(active_shift),
            "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
            "client_incident_id": f"a-{uuid.uuid4()}",
        }
        payload_b = {
            "shift_id": str(active_shift),
            "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
            "client_incident_id": f"b-{uuid.uuid4()}",
        }
        # Different physical events aren't expected within the same 60s
        # window in real usage, so bypass the coarse shift-level heuristic
        # to isolate what this phase actually changed: exact-ID identity.
        import app.api.incidents as incidents_module
        original = incidents_module._recent_incident_for_shift
        incidents_module._recent_incident_for_shift = lambda db, shift_id: None
        try:
            first = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload_a)
            second = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload_b)
        finally:
            incidents_module._recent_incident_for_shift = original

        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["incident_id"] != second.json()["incident_id"]
        assert second.json()["scoring_method"] != "duplicate_suppressed"

    def test_retry_preserves_exact_same_client_incident_id_and_raw_window(self, test_rider_user, active_shift):
        _, token = test_rider_user
        client_id = f"preserve-{uuid.uuid4()}"
        accel = _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81))
        payload = {"shift_id": str(active_shift), "accel_samples": accel, "client_incident_id": client_id}

        first = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)
        # Simulated retry: same exact ID and same exact window, nothing regenerated.
        second = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)

        assert first.json()["incident_id"] == second.json()["incident_id"]
        assert first.json()["confidence_score"] == pytest.approx(second.json()["confidence_score"], abs=1e-9) \
            or second.json()["scoring_method"] == "duplicate_suppressed"

    def test_existing_incident_does_not_restart_escalation(self, monkeypatch, test_rider_user, active_shift):
        """A retry that returns an existing incident must not schedule a
        second run_incident_escalation — escalation is a one-shot ladder
        per physical crash, not per upload attempt."""
        calls = []

        async def _tracking_noop(incident_id):
            calls.append(incident_id)

        monkeypatch.setattr(incidents_api, "run_incident_escalation", _tracking_noop)

        _, token = test_rider_user
        client_id = f"no-restart-{uuid.uuid4()}"
        payload = {
            "shift_id": str(active_shift),
            "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
            "client_incident_id": client_id,
        }
        client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)
        client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)
        client.post("/incidents/from-window", headers=_auth_headers(token), json=payload)

        # TestClient runs BackgroundTasks synchronously, so by the time each
        # request above returns, its scheduled task (if any) has already run.
        assert len(calls) == 1

    def test_existing_incident_returns_deterministic_response(self, test_rider_user, active_shift):
        _, token = test_rider_user
        client_id = f"deterministic-{uuid.uuid4()}"
        payload = {
            "shift_id": str(active_shift),
            "accel_samples": _accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
            "client_incident_id": client_id,
        }
        first = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload).json()
        second = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload).json()
        third = client.post("/incidents/from-window", headers=_auth_headers(token), json=payload).json()

        assert second == third
        assert second["incident_id"] == first["incident_id"]
        assert second["scoring_method"] == "duplicate_suppressed"

    def test_database_unique_constraint_exists(self, test_rider_user, active_shift):
        """Proves the protection is a real DB constraint, not just app-level
        logic — inserting two Incident rows with the same client_incident_id
        directly via the ORM (bypassing the endpoint entirely) must fail."""
        user, _ = test_rider_user
        client_id = f"constraint-{uuid.uuid4()}"
        db = SessionLocal()
        try:
            db.add(Incident(
                shift_id=active_shift, rider_id=user.id, status=IncidentStatus.DETECTED,
                peak_g_force=5.0, confidence_score=0.5, latitude=0.0, longitude=0.0,
                client_incident_id=client_id,
            ))
            db.commit()

            db.add(Incident(
                shift_id=active_shift, rider_id=user.id, status=IncidentStatus.DETECTED,
                peak_g_force=5.0, confidence_score=0.5, latitude=0.0, longitude=0.0,
                client_incident_id=client_id,
            ))
            with pytest.raises(IntegrityError):
                db.commit()
        finally:
            db.rollback()
            db.close()

    def test_concurrent_uploads_with_same_id_create_exactly_one_incident(self, test_rider_user, active_shift):
        """The real target scenario: two requests race each other with the
        same client_incident_id. Widens the race window by synchronizing
        both threads on a barrier inside ml_scoring_service.score_window
        (called before the insert) so both reach db.commit() as close to
        simultaneously as possible — this is what actually exercises the DB
        unique constraint's IntegrityError path rather than the simple
        lookup-first fast path."""
        user, _ = test_rider_user
        client_id = f"race-{uuid.uuid4()}"
        barrier = threading.Barrier(2, timeout=5)
        original_score = ml_scoring_service.score_window

        def synced_score(*args, **kwargs):
            barrier.wait()
            return original_score(*args, **kwargs)

        results = []
        errors = []

        def worker():
            db = SessionLocal()
            try:
                current_user = db.query(User).filter(User.id == user.id).first()
                submission = CrashWindowSubmission(
                    shift_id=active_shift,
                    accel_samples=_accel_samples(n=50, spike_at=25, spike_mag=(45.0, 0.0, 9.81)),
                    client_incident_id=client_id,
                )
                background_tasks = BackgroundTasks()
                response = incidents_api.create_incident_from_window(
                    db=db,
                    current_user=current_user,
                    submission=submission,
                    background_tasks=background_tasks,
                )
                results.append((response, background_tasks))
            except Exception as e:  # pragma: no cover - failure surfaced via `errors`
                errors.append(e)
            finally:
                db.close()

        original_recent_check = incidents_api._recent_incident_for_shift
        incidents_api._recent_incident_for_shift = lambda db, shift_id: None
        ml_scoring_service.score_window = synced_score
        try:
            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)
        finally:
            incidents_api._recent_incident_for_shift = original_recent_check
            ml_scoring_service.score_window = original_score

        assert not errors, f"worker thread(s) raised: {errors}"
        assert len(results) == 2

        incident_ids = {r.incident_id for r, _ in results}
        assert len(incident_ids) == 1, "two concurrent requests produced two different incidents"

        db = SessionLocal()
        try:
            count = db.query(Incident).filter(Incident.client_incident_id == client_id).count()
            assert count == 1
        finally:
            db.close()

        # Exactly one of the two threads is the one that actually created the
        # row and scheduled escalation — the other must have taken the
        # IntegrityError fallback path and scheduled nothing.
        scheduled = [bg for _, bg in results if len(bg.tasks) > 0]
        assert len(scheduled) == 1
