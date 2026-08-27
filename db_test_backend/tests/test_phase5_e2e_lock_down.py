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
from db.models.claim_medical_report import ClaimMedicalReport
from db.models.hospital import Hospital
from db.models.shift import Shift
from db.models.audit import AuditEvent
from db.models.enums import UserRole, ClaimStatus, IncidentStatus, ShiftStatus, DocumentType
from app.services.evidence_verification_service import run_and_persist_evidence_verification
from app.core.security import create_access_token

client = TestClient(app)

# UUID Constants
RIDER_ID = uuid.UUID("b1111111-1111-1111-1111-111111111111")
INSURER_ID = uuid.UUID("b2222222-2222-2222-2222-222222222222")
HOSP_USER_ID = uuid.UUID("b3333333-3333-3333-3333-333333333333")
HOSPITAL_ID = uuid.UUID("b4444444-4444-4444-4444-444444444444")
SHIFT_ID = uuid.UUID("b5555555-5555-5555-5555-555555555555")

INCIDENT_A = uuid.UUID("b6666666-6666-6666-6666-666666666661")
CLAIM_A = uuid.UUID("b7777777-7777-7777-7777-777777777761")

INCIDENT_B = uuid.UUID("b6666666-6666-6666-6666-666666666662")
CLAIM_B = uuid.UUID("b7777777-7777-7777-7777-777777777762")

INCIDENT_C = uuid.UUID("b6666666-6666-6666-6666-666666666663")
CLAIM_C = uuid.UUID("b7777777-7777-7777-7777-777777777763")


def setup_phase5_db():
    app.dependency_overrides.clear()
    db = SessionLocal()
    try:
        # Delete audit events and claims for test entities safely
        claim_ids = [CLAIM_A, CLAIM_B, CLAIM_C]
        user_ids = [RIDER_ID, INSURER_ID, HOSP_USER_ID]
        db.query(Claim).filter(Claim.id.in_(claim_ids)).update({"verification_run_id": None}, synchronize_session=False)
        db.commit()
        db.query(AuditEvent).filter(AuditEvent.claim_id.in_(claim_ids)).delete(synchronize_session=False)
        db.query(AuditEvent).filter(AuditEvent.performed_by_user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(ClaimMedicalReport).filter(ClaimMedicalReport.claim_id.in_(claim_ids)).delete(synchronize_session=False)
        db.query(Claim).filter(Claim.id.in_(claim_ids)).delete(synchronize_session=False)
        db.query(Incident).filter(Incident.id.in_([INCIDENT_A, INCIDENT_B, INCIDENT_C])).delete(synchronize_session=False)
        db.query(Shift).filter(Shift.id == SHIFT_ID).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.query(Hospital).filter(Hospital.id == HOSPITAL_ID).delete(synchronize_session=False)
        db.commit()

        # Create Hospital
        hosp = Hospital(
            id=HOSPITAL_ID,
            name="Phase5 City Hospital",
            locality="Andheri East",
            contact_number="9876543210"
        )
        db.add(hosp)
        db.commit()

        # Create Users
        rider = User(
            id=RIDER_ID,
            email="phase5_rider@test.com",
            phone_number="9777777771",
            hashed_password="hashed",
            full_name="Phase5 Rider",
            role=UserRole.RIDER,
            is_active=True
        )
        insurer = User(
            id=INSURER_ID,
            email="phase5_insurer@test.com",
            phone_number="9777777772",
            hashed_password="hashed",
            full_name="Phase5 Insurer",
            role=UserRole.INSURER,
            is_active=True
        )
        hosp_rep = User(
            id=HOSP_USER_ID,
            email="phase5_hosp@test.com",
            phone_number="9777777773",
            hashed_password="hashed",
            full_name="Phase5 HospRep",
            role=UserRole.HOSPITAL_REP,
            hospital_id=HOSPITAL_ID,
            is_active=True
        )
        db.add_all([rider, insurer, hosp_rep])
        db.commit()

        # Create Shift
        shift = Shift(
            id=SHIFT_ID,
            rider_id=RIDER_ID,
            status=ShiftStatus.ACTIVE,
            start_time=datetime.now(timezone.utc) - timedelta(hours=4)
        )
        db.add(shift)

        now = datetime.now(timezone.utc)
        # Create Incidents A, B, C
        inc_a = Incident(
            id=INCIDENT_A, rider_id=RIDER_ID, shift_id=SHIFT_ID, status=IncidentStatus.DETECTED,
            locality="Andheri East", latitude=19.1136, longitude=72.8697, detected_at=now - timedelta(hours=2),
            confidence_score=0.92, peak_g_force=4.8
        )
        inc_b = Incident(
            id=INCIDENT_B, rider_id=RIDER_ID, shift_id=SHIFT_ID, status=IncidentStatus.DETECTED,
            locality="Andheri East", latitude=19.1136, longitude=72.8697, detected_at=now - timedelta(hours=2),
            confidence_score=0.90, peak_g_force=4.2
        )
        inc_c = Incident(
            id=INCIDENT_C, rider_id=RIDER_ID, shift_id=SHIFT_ID, status=IncidentStatus.DETECTED,
            locality="Andheri East", latitude=19.1136, longitude=72.8697, detected_at=now - timedelta(hours=2),
            confidence_score=0.88, peak_g_force=3.9
        )
        db.add_all([inc_a, inc_b, inc_c])

        # Create Claims A, B, C
        cl_a = Claim(id=CLAIM_A, incident_id=INCIDENT_A, rider_id=RIDER_ID, shift_id=SHIFT_ID, claim_number="CLM-P5-100A", status=ClaimStatus.MEDICAL_REPORT_PENDING, claimed_amount=15000.0)
        cl_b = Claim(id=CLAIM_B, incident_id=INCIDENT_B, rider_id=RIDER_ID, shift_id=SHIFT_ID, claim_number="CLM-P5-100B", status=ClaimStatus.MEDICAL_REPORT_PENDING, claimed_amount=8000.0)
        cl_c = Claim(id=CLAIM_C, incident_id=INCIDENT_C, rider_id=RIDER_ID, shift_id=SHIFT_ID, claim_number="CLM-P5-100C", status=ClaimStatus.MEDICAL_REPORT_PENDING, claimed_amount=5000.0)
        db.add_all([cl_a, cl_b, cl_c])
        db.commit()
    finally:
        db.close()


def get_user_token(user_id: uuid.UUID) -> str:
    return create_access_token(str(user_id))


def test_full_happy_path_approve_chain_and_terminal_409_lock():
    setup_phase5_db()
    db = SessionLocal()
    try:
        hosp_token = get_user_token(HOSP_USER_ID)
        insurer_token = get_user_token(INSURER_ID)

        # 1. Evidence submitted
        with open("temp_p5_admission.pdf", "w") as f:
            f.write("Phase 5 Admission Report for Rider Phase5 Rider")

        with open("temp_p5_admission.pdf", "rb") as f:
            res_upload = client.post(
                f"/claims/{CLAIM_A}/reports",
                headers={"Authorization": f"Bearer {hosp_token}"},
                data={"document_type": "ADMISSION_REPORT", "notes": "Admission notes for Phase5 Rider"},
                files={"file": ("temp_p5_admission.pdf", f, "application/pdf")}
            )
        assert res_upload.status_code == 200, f"Upload failed: {res_upload.text}"

        # 2. Run verification -> Verification #N
        verif_res = run_and_persist_evidence_verification(CLAIM_A, db)
        assert verif_res["score"] > 0

        # Retrieve audit run ID #N from DB
        verif_run = db.query(AuditEvent).filter(AuditEvent.claim_id == CLAIM_A, AuditEvent.event_type == "CLAIM_VERIFICATION_RUN").order_by(AuditEvent.created_at.desc()).first()
        assert verif_run is not None
        verif_run_id = verif_run.id

        # 3. Insurer sees Verification #N on claim endpoint
        res_claim = client.get(f"/claims/{CLAIM_A}", headers={"Authorization": f"Bearer {insurer_token}"})
        assert res_claim.status_code == 200
        data_claim = res_claim.json()
        assert data_claim["verification_score"] == verif_res["score"]

        # 4. Start review -> UNDER_REVIEW
        res_review = client.post(f"/claims/{CLAIM_A}/review", headers={"Authorization": f"Bearer {insurer_token}"})
        assert res_review.status_code == 200
        assert res_review.json()["status"] == "UNDER_REVIEW"

        # 5. Insurer manually approves -> Decision references Verification #N
        res_approve = client.post(f"/claims/{CLAIM_A}/approve?approved_amount=15000.00", headers={"Authorization": f"Bearer {insurer_token}"})
        assert res_approve.status_code == 200
        data_appr = res_approve.json()
        assert data_appr["status"] == "APPROVED"
        assert data_appr["verification_run_id"] == str(verif_run_id)
        assert data_appr["decided_by"] == str(INSURER_ID)

        # Direct DB Column Verification for Claim A
        db_claim_a = db.query(Claim).filter(Claim.id == CLAIM_A).first()
        assert db_claim_a.status == ClaimStatus.APPROVED
        assert db_claim_a.decided_by == INSURER_ID
        assert db_claim_a.decided_at is not None
        assert db_claim_a.verification_run_id == verif_run_id

        # 6. Terminal State Lockouts (HTTP 409 Conflict)
        # a. Evidence upload -> 409 Conflict
        with open("temp_p5_admission.pdf", "rb") as f:
            res_up_409 = client.post(
                f"/claims/{CLAIM_A}/reports",
                headers={"Authorization": f"Bearer {hosp_token}"},
                data={"document_type": "HOSPITAL_BILL"},
                files={"file": ("temp_p5_admission.pdf", f, "application/pdf")}
            )
        assert res_up_409.status_code == 409
        assert "closed in terminal state" in res_up_409.json()["detail"]

        # b. Verification rerun -> 409 Conflict
        with pytest.raises(Exception) as exc_info:
            run_and_persist_evidence_verification(CLAIM_A, db)
        assert "409" in str(exc_info.value) or "terminal state" in str(exc_info.value)

        # c. Second decision -> 409 Conflict
        res_dec_409 = client.post(f"/claims/{CLAIM_A}/approve?approved_amount=15000.00", headers={"Authorization": f"Bearer {insurer_token}"})
        assert res_dec_409.status_code == 409
        assert "closed in terminal state" in res_dec_409.json()["detail"]

        if os.path.exists("temp_p5_admission.pdf"):
            os.remove("temp_p5_admission.pdf")
    finally:
        db.close()


def test_full_rejection_path_chain_and_terminal_409_lock():
    db = SessionLocal()
    try:
        hosp_token = get_user_token(HOSP_USER_ID)
        insurer_token = get_user_token(INSURER_ID)

        # 1. Evidence submitted
        with open("temp_p5_rej.pdf", "w") as f:
            f.write("Phase 5 Admission Report for Rider Phase5 Rider")

        with open("temp_p5_rej.pdf", "rb") as f:
            client.post(
                f"/claims/{CLAIM_B}/reports",
                headers={"Authorization": f"Bearer {hosp_token}"},
                data={"document_type": "ADMISSION_REPORT", "notes": "Discrepant notes"},
                files={"file": ("temp_p5_rej.pdf", f, "application/pdf")}
            )

        # 2. Run verification
        run_and_persist_evidence_verification(CLAIM_B, db)
        verif_run = db.query(AuditEvent).filter(AuditEvent.claim_id == CLAIM_B, AuditEvent.event_type == "CLAIM_VERIFICATION_RUN").order_by(AuditEvent.created_at.desc()).first()
        assert verif_run is not None

        # 3. Start review & Reject
        client.post(f"/claims/{CLAIM_B}/review", headers={"Authorization": f"Bearer {insurer_token}"})
        res_rej = client.post(f"/claims/{CLAIM_B}/reject?rejection_reason=Invalid%20documents", headers={"Authorization": f"Bearer {insurer_token}"})
        assert res_rej.status_code == 200
        data_rej = res_rej.json()
        assert data_rej["status"] == "REJECTED"
        assert data_rej["verification_run_id"] == str(verif_run.id)

        # Direct DB Column Verification for Claim B
        db_claim_b = db.query(Claim).filter(Claim.id == CLAIM_B).first()
        assert db_claim_b.status == ClaimStatus.REJECTED
        assert db_claim_b.decided_by == INSURER_ID
        assert db_claim_b.decided_at is not None
        assert db_claim_b.verification_run_id == verif_run.id

        # 4. Prove terminal state lock (409 Conflict)
        res_dup_rej = client.post(f"/claims/{CLAIM_B}/reject?rejection_reason=Dup", headers={"Authorization": f"Bearer {insurer_token}"})
        assert res_dup_rej.status_code == 409

        if os.path.exists("temp_p5_rej.pdf"):
            os.remove("temp_p5_rej.pdf")
    finally:
        db.close()


def test_claim_c_isolation():
    db = SessionLocal()
    try:
        cl_c = db.query(Claim).filter(Claim.id == CLAIM_C).first()
        assert cl_c is not None
        assert cl_c.status == ClaimStatus.MEDICAL_REPORT_PENDING
        assert cl_c.decided_by is None
        assert cl_c.verification_run_id is None
    finally:
        db.close()


def test_invalid_review_state_decision_refusal():
    insurer_token = get_user_token(INSURER_ID)
    # Claim C is MEDICAL_REPORT_PENDING -> Attempt decision must return HTTP 400
    res = client.post(f"/claims/{CLAIM_C}/approve?approved_amount=5000.00", headers={"Authorization": f"Bearer {insurer_token}"})
    assert res.status_code == 400
    assert "UNDER_REVIEW" in res.json()["detail"]


def test_out_of_order_verification_resolution():
    db = SessionLocal()
    try:
        insurer_token = get_user_token(INSURER_ID)
        now = datetime.now(timezone.utc)

        # Clear existing audit events for Claim C
        db.query(AuditEvent).filter(AuditEvent.claim_id == CLAIM_C).delete(synchronize_session=False)
        db.commit()

        # Add Medical Report to Claim C & update status
        cl_c = db.query(Claim).filter(Claim.id == CLAIM_C).first()
        cl_c.status = ClaimStatus.MEDICAL_REPORT_SUBMITTED
        rep = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=CLAIM_C, hospital_id=HOSPITAL_ID, uploaded_by=HOSP_USER_ID,
            document_type="HOSPITAL_ADMISSION_REPORT", file_reference="dummy.pdf", uploaded_at=now
        )
        db.add_all([cl_c, rep])
        db.commit()

        # Insert Run 1 (Older, score 75.0)
        run1 = AuditEvent(
            id=uuid.uuid4(), claim_id=CLAIM_C, entity_type="claim", entity_id=CLAIM_C,
            event_type="CLAIM_VERIFICATION_RUN", performed_by_user_id=RIDER_ID,
            metadata_json={"verification_score": 75.0, "verification_band": "MEDIUM RISK", "status": "SUCCESS"},
            created_at=now - timedelta(minutes=10)
        )
        # Insert Run 2 (Middle timestamp, FAILED)
        run2 = AuditEvent(
            id=uuid.uuid4(), claim_id=CLAIM_C, entity_type="claim", entity_id=CLAIM_C,
            event_type="CLAIM_VERIFICATION_RUN", performed_by_user_id=RIDER_ID,
            metadata_json={"verification_score": None, "verification_band": None, "status": "FAILED"},
            created_at=now - timedelta(minutes=5)
        )
        # Insert Run 3 (Latest timestamp, score 92.5)
        run3 = AuditEvent(
            id=uuid.uuid4(), claim_id=CLAIM_C, entity_type="claim", entity_id=CLAIM_C,
            event_type="CLAIM_VERIFICATION_RUN", performed_by_user_id=RIDER_ID,
            metadata_json={"verification_score": 92.5, "verification_band": "STRONG EVIDENCE", "status": "SUCCESS"},
            created_at=now - timedelta(minutes=1)
        )
        db.add_all([run1, run2, run3])
        db.commit()

        # Check claim endpoint resolves Run 3 (score 92.5)
        res_c = client.get(f"/claims/{CLAIM_C}", headers={"Authorization": f"Bearer {insurer_token}"})
        assert res_c.status_code == 200
        assert res_c.json()["verification_score"] == 92.5

        # Move Claim C to UNDER_REVIEW
        client.post(f"/claims/{CLAIM_C}/review", headers={"Authorization": f"Bearer {insurer_token}"})

        # Approve Claim C -> Must resolve to Run 3
        res_appr = client.post(f"/claims/{CLAIM_C}/approve?approved_amount=5000.00", headers={"Authorization": f"Bearer {insurer_token}"})
        assert res_appr.status_code == 200
        data_c = res_appr.json()
        assert data_c["verification_run_id"] == str(run3.id)
    finally:
        db.close()


def test_verify_no_orphaned_claims():
    db = SessionLocal()
    try:
        # Check decided Phase 5 test claims
        decided_p5_claims = db.query(Claim).filter(
            Claim.id.in_([CLAIM_A, CLAIM_B, CLAIM_C]),
            Claim.status.in_([ClaimStatus.APPROVED, ClaimStatus.REJECTED])
        ).all()
        assert len(decided_p5_claims) >= 2
        for cl in decided_p5_claims:
            assert cl.verification_run_id is not None, f"Decided claim {cl.id} missing verification_run_id"
            audit = db.query(AuditEvent).filter(AuditEvent.id == cl.verification_run_id).first()
            assert audit is not None, f"Claim {cl.id} verification_run_id {cl.verification_run_id} does not resolve to an AuditEvent"
    finally:
        db.close()
