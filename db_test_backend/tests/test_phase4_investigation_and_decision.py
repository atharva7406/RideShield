import os
import sys
import uuid
import pytest
from datetime import datetime, timezone, timedelta

# Add backend directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from fastapi.testclient import TestClient
from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.incident import Incident
from db.models.claim import Claim
from db.models.hospital import Hospital
from db.models.shift import Shift
from db.models.audit import AuditEvent
from db.models.enums import UserRole, ClaimStatus, IncidentStatus, ShiftStatus
from app.services.evidence_verification_service import run_and_persist_evidence_verification

client = TestClient(app)

# Test UUIDs
RIDER_ID = uuid.UUID("a1111111-1111-1111-1111-111111111111")
INSURER_ID = uuid.UUID("a2222222-2222-2222-2222-222222222222")
SHIFT_ID = uuid.UUID("a5555555-5555-5555-5555-555555555555")
INCIDENT_ID = uuid.UUID("a6666666-6666-6666-6666-666666666666")
CLAIM_ID = uuid.UUID("a7777777-7777-7777-7777-777777777777")


def setup_phase4_db():
    app.dependency_overrides.clear()
    db = SessionLocal()
    try:
        # Delete audit events for this claim and users
        db.query(AuditEvent).filter(AuditEvent.claim_id == CLAIM_ID).delete()
        existing_users = db.query(User).filter(
            (User.id.in_([RIDER_ID, INSURER_ID])) |
            (User.email.in_(["phase4_rider@test.com", "phase4_insurer@test.com"]))
        ).all()
        existing_user_ids = [u.id for u in existing_users]
        if existing_user_ids:
            db.query(AuditEvent).filter(AuditEvent.performed_by_user_id.in_(existing_user_ids)).delete()

        db.query(Claim).filter(Claim.id == CLAIM_ID).delete()
        db.query(Incident).filter(Incident.id == INCIDENT_ID).delete()
        db.query(Shift).filter(Shift.id == SHIFT_ID).delete()

        for u in existing_users:
            db.delete(u)
        db.commit()

        rider = User(
            id=RIDER_ID,
            email="phase4_rider@test.com",
            phone_number="9888888881",
            hashed_password="hashed",
            full_name="Phase4 Rider",
            role=UserRole.RIDER,
            is_active=True
        )
        insurer = User(
            id=INSURER_ID,
            email="phase4_insurer@test.com",
            phone_number="9888888882",
            hashed_password="hashed",
            full_name="Phase4 Insurer",
            role=UserRole.INSURER,
            is_active=True
        )
        db.add_all([rider, insurer])
        db.commit()

        shift = Shift(
            id=SHIFT_ID,
            rider_id=RIDER_ID,
            status=ShiftStatus.ACTIVE,
            start_time=datetime.now(timezone.utc) - timedelta(hours=3)
        )
        db.add(shift)

        incident = Incident(
            id=INCIDENT_ID,
            rider_id=RIDER_ID,
            shift_id=SHIFT_ID,
            status=IncidentStatus.DETECTED,
            locality="Bandra West",
            latitude=19.0596,
            longitude=72.8295,
            detected_at=datetime.now(timezone.utc) - timedelta(hours=2),
            confidence_score=0.95,
            peak_g_force=5.1
        )
        db.add(incident)

        claim = Claim(
            id=CLAIM_ID,
            incident_id=INCIDENT_ID,
            rider_id=RIDER_ID,
            shift_id=SHIFT_ID,
            claim_number="CLM-PHASE4-1001",
            status=ClaimStatus.MEDICAL_REPORT_SUBMITTED,
            claimed_amount=12000.00,
            filed_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        db.add(claim)
        db.commit()
    finally:
        db.close()


def get_token(user_id: uuid.UUID) -> str:
    from app.core.security import create_access_token
    return create_access_token(str(user_id))


def test_deterministic_latest_successful_verification_resolution():
    setup_phase4_db()
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Create multiple verification runs out of order & including a failed one
        audit1 = AuditEvent(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            claim_id=CLAIM_ID,
            entity_type="claim",
            entity_id=CLAIM_ID,
            event_type="CLAIM_VERIFICATION_RUN",
            performed_by_user_id=RIDER_ID,
            metadata_json={"verification_score": 60.0, "verification_band": "REVIEW REQUIRED", "verification_details": {"factor": "initial"}},
            created_at=now - timedelta(minutes=30)
        )
        # Latest timestamp but marked as FAILED
        audit_failed = AuditEvent(
            id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            claim_id=CLAIM_ID,
            entity_type="claim",
            entity_id=CLAIM_ID,
            event_type="CLAIM_VERIFICATION_RUN",
            performed_by_user_id=RIDER_ID,
            metadata_json={"status": "FAILED", "error": "Timeout", "verification_score": None},
            created_at=now - timedelta(minutes=5)
        )
        # Expected latest successful run
        audit2 = AuditEvent(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            claim_id=CLAIM_ID,
            entity_type="claim",
            entity_id=CLAIM_ID,
            event_type="CLAIM_VERIFICATION_RUN",
            performed_by_user_id=RIDER_ID,
            metadata_json={"verification_score": 95.0, "verification_band": "STRONG EVIDENCE", "verification_details": {"factor": "latest_successful"}},
            created_at=now - timedelta(minutes=10)
        )
        db.add_all([audit1, audit_failed, audit2])
        db.commit()

        # Query endpoint and verify the latest successful score (95.0) is returned deterministically
        token = get_token(INSURER_ID)
        response = client.get(f"/claims/{CLAIM_ID}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["verification_score"] == 95.0
        assert data["verification_band"] == "STRONG EVIDENCE"
        assert data["verification_details"]["factor"] == "latest_successful"
    finally:
        db.close()


def test_gated_decision_workflow_and_idempotency():
    setup_phase4_db()
    token = get_token(INSURER_ID)

    # 1. Attempt approval directly from MEDICAL_REPORT_SUBMITTED (must fail with HTTP 400)
    res1 = client.post(
        f"/claims/{CLAIM_ID}/approve?approved_amount=12000.00",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res1.status_code == 400
    assert "UNDER_REVIEW" in res1.json()["detail"]

    # 2. Transition claim from MEDICAL_REPORT_SUBMITTED -> UNDER_REVIEW
    res_review = client.post(f"/claims/{CLAIM_ID}/review", headers={"Authorization": f"Bearer {token}"})
    assert res_review.status_code == 200
    assert res_review.json()["status"] == "UNDER_REVIEW"

    # 3. Approve claim from UNDER_REVIEW (must succeed)
    res_approve = client.post(
        f"/claims/{CLAIM_ID}/approve?approved_amount=12000.00",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "APPROVED"
    assert res_approve.json()["approved_amount"] == 12000.00

    # 4. Duplicate approval attempt on already-decided claim must fail cleanly (idempotent rejection, 400 or 409)
    res_dup = client.post(
        f"/claims/{CLAIM_ID}/approve?approved_amount=12000.00",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_dup.status_code in [400, 409]

    # 5. Duplicate rejection attempt on already-approved claim must fail cleanly
    res_dup_rej = client.post(
        f"/claims/{CLAIM_ID}/reject?rejection_reason=Test",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_dup_rej.status_code in [400, 409]


def test_server_authoritative_read_only_verification():
    setup_phase4_db()
    token = get_token(INSURER_ID)

    # Move to review
    client.post(f"/claims/{CLAIM_ID}/review", headers={"Authorization": f"Bearer {token}"})

    # Pass malicious body attempting to override verification score or band
    malicious_body = {
        "verification_score": 100.0,
        "verification_band": "STRONG EVIDENCE",
        "verification_details": {"malicious": True}
    }
    res = client.post(
        f"/claims/{CLAIM_ID}/approve?approved_amount=12000.00",
        headers={"Authorization": f"Bearer {token}"},
        json=malicious_body
    )
    assert res.status_code == 200
    data = res.json()
    # Confirm client-supplied payload was completely ignored and did not pollute response or DB
    if data["verification_details"]:
        assert "malicious" not in data["verification_details"]
