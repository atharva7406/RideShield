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
from db.models.enums import UserRole, ClaimStatus, IncidentStatus, ShiftStatus
from app.services.evidence_verification_service import compute_evidence_verification_score, run_and_persist_evidence_verification, normalize_document_type

client = TestClient(app)

# Test UUIDs
RIDER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
INSURER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
HOSP_USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
HOSPITAL_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
SHIFT_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
INCIDENT_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
CLAIM_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


def setup_verification_db():
    db = SessionLocal()
    try:
        from db.models.audit import AuditEvent
        # Cleanup existing test records in dependency order
        db.query(AuditEvent).filter(AuditEvent.claim_id == CLAIM_ID).delete()
        db.query(ClaimMedicalReport).delete()
        db.query(Claim).filter(Claim.id == CLAIM_ID).delete()
        db.query(Incident).filter(Incident.id == INCIDENT_ID).delete()
        db.query(Shift).filter(Shift.id == SHIFT_ID).delete()
        db.query(User).filter(User.id.in_([RIDER_ID, INSURER_ID, HOSP_USER_ID])).delete()
        db.query(Hospital).filter(Hospital.id == HOSPITAL_ID).delete()
        db.commit()

        # Create Hospital
        hosp = Hospital(
            id=HOSPITAL_ID,
            name="Test Verification Hospital",
            locality="Mumbai Central",
            contact_number="9999999999",
            latitude=19.0760,
            longitude=72.8777
        )
        db.add(hosp)

        # Create Users
        rider = User(
            id=RIDER_ID,
            email="verification_rider@test.com",
            phone_number="9999999991",
            hashed_password="hashed",
            full_name="Rajesh Kumar",
            role=UserRole.RIDER,
            is_active=True
        )
        insurer = User(
            id=INSURER_ID,
            email="verification_insurer@test.com",
            phone_number="9999999992",
            hashed_password="hashed",
            full_name="Insurer Rep",
            role=UserRole.INSURER,
            is_active=True
        )
        hosp_user = User(
            id=HOSP_USER_ID,
            email="verification_hosp@test.com",
            phone_number="9999999993",
            hashed_password="hashed",
            full_name="Hospital Rep",
            role=UserRole.HOSPITAL_REP,
            hospital_id=HOSPITAL_ID,
            is_active=True
        )
        db.add_all([rider, insurer, hosp_user])
        db.commit()

        # Create Shift
        shift = Shift(
            id=SHIFT_ID,
            rider_id=RIDER_ID,
            status=ShiftStatus.ACTIVE,
            start_time=datetime.now(timezone.utc) - timedelta(hours=5)
        )
        db.add(shift)

        # Create Incident
        now = datetime.now(timezone.utc)
        incident = Incident(
            id=INCIDENT_ID,
            rider_id=RIDER_ID,
            shift_id=SHIFT_ID,
            status=IncidentStatus.DETECTED,
            locality="Mumbai Central",
            latitude=19.0760,
            longitude=72.8777,
            detected_at=now - timedelta(hours=1),
            confidence_score=0.92,
            peak_g_force=4.5
        )
        db.add(incident)

        # Create Claim
        claim = Claim(
            id=CLAIM_ID,
            incident_id=INCIDENT_ID,
            rider_id=RIDER_ID,
            shift_id=SHIFT_ID,
            claim_number="CLM-VERIF-1001",
            status=ClaimStatus.MEDICAL_REPORT_PENDING,
            claimed_amount=15000.00,
            filed_at=now - timedelta(minutes=30)
        )
        db.add(claim)
        db.commit()
    finally:
        db.close()


def get_token(user_id: uuid.UUID) -> str:
    from app.core.security import create_access_token
    return create_access_token(user_id)


def test_single_document_completeness_add_and_delete_flow():
    setup_verification_db()
    token = get_token(HOSP_USER_ID)

    with open("temp_admission.pdf", "w") as f:
        f.write("admission pdf")
    with open("temp_bill.pdf", "w") as f:
        f.write("bill pdf")

    try:
        # 1. Upload Single Document (Admission Report)
        with open("temp_admission.pdf", "rb") as f:
            res1 = client.post(
                f"/claims/{CLAIM_ID}/reports",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("temp_admission.pdf", f, "application/pdf")},
                data={
                    "document_type": "HOSPITAL_ADMISSION_REPORT",
                    "patient_identifier": "Rajesh Kumar",
                    "facility_name": "Test Verification Hospital",
                    "hospital_locality": "Mumbai Central",
                    "admittance_timestamp": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
                    "diagnosis_notes": "Patient Rajesh Kumar admitted for observation following collision."
                }
            )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["verification_details"]["document_completeness"]["score"] == 9.0
        reports1 = data1["medical_reports"]
        assert len(reports1) == 1
        admission_report_id = reports1[0]["id"]

        # 2. Add Second Document (Bill)
        with open("temp_bill.pdf", "rb") as f:
            res2 = client.post(
                f"/claims/{CLAIM_ID}/reports",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("temp_bill.pdf", f, "application/pdf")},
                data={
                    "document_type": "HOSPITAL_BILL",
                    "patient_identifier": "Rajesh Kumar",
                    "facility_name": "Test Verification Hospital",
                    "hospital_locality": "Mumbai Central",
                    "admittance_timestamp": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
                    "diagnosis_notes": "Pharmacy bill and hospital charges."
                }
            )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["verification_details"]["document_completeness"]["score"] == 15.0
        reports2 = data2["medical_reports"]
        assert len(reports2) == 2
        bill_report_id = [r["id"] for r in reports2 if r["id"] != admission_report_id][0]

        # 3. Delete Second Document (Bill)
        res_del_bill = client.delete(
            f"/claims/{CLAIM_ID}/reports/{bill_report_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_del_bill.status_code == 200
        data3 = res_del_bill.json()
        assert data3["verification_details"]["document_completeness"]["score"] == 9.0
        assert len(data3["medical_reports"]) == 1
        assert data3["medical_reports"][0]["id"] == admission_report_id

        # 4. Delete Final Report (Admission Report)
        res_del_admission = client.delete(
            f"/claims/{CLAIM_ID}/reports/{admission_report_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_del_admission.status_code == 200
        data4 = res_del_admission.json()
        assert len(data4["medical_reports"]) == 0
        assert data4["verification_details"]["document_completeness"]["score"] == 0.0
        assert data4["verification_score"] == 10.0  # Only metadata consistency factor (10.0) remains
    finally:
        if os.path.exists("temp_admission.pdf"):
            os.remove("temp_admission.pdf")
        if os.path.exists("temp_bill.pdf"):
            os.remove("temp_bill.pdf")


def test_identity_mismatch_sensitivity():
    setup_verification_db()
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.id == CLAIM_ID).first()
        now = datetime.now(timezone.utc)

        # Mismatch case: Admission & Bill = Rajesh Kumar, Prescription = Rahul
        report1 = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=CLAIM_ID, hospital_id=HOSPITAL_ID, uploaded_by=HOSP_USER_ID,
            file_reference="path/to/adm.pdf", document_type="HOSPITAL_ADMISSION_REPORT",
            patient_identifier="Rajesh Kumar", hospital_locality="Mumbai Central", uploaded_at=now
        )
        report2 = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=CLAIM_ID, hospital_id=HOSPITAL_ID, uploaded_by=HOSP_USER_ID,
            file_reference="path/to/bill.pdf", document_type="HOSPITAL_BILL",
            patient_identifier="Rahul", hospital_locality="Mumbai Central", uploaded_at=now
        )
        db.add_all([report1, report2])
        db.commit()

        result_mismatch = compute_evidence_verification_score(claim, db)
        assert result_mismatch["breakdown"]["patient_identity_match"]["score"] == 0.0

        # All-matching case: All = Rajesh Kumar
        report2.patient_identifier = "Rajesh Kumar"
        db.commit()

        result_matching = compute_evidence_verification_score(claim, db)
        assert result_matching["breakdown"]["patient_identity_match"]["score"] == 30.0
    finally:
        db.close()


def test_earliest_admittance_timestamp_scoring():
    setup_verification_db()
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.id == CLAIM_ID).first()
        incident_time = claim.incident.detected_at  # t-1h

        # Report 1 uploaded at t+10h, but admittance_timestamp = t+1h (within 4 hours of incident)
        r1 = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=CLAIM_ID, hospital_id=HOSPITAL_ID, uploaded_by=HOSP_USER_ID,
            file_reference="p1.pdf", document_type="HOSPITAL_ADMISSION_REPORT",
            admittance_timestamp=incident_time + timedelta(hours=1),
            uploaded_at=incident_time + timedelta(hours=10)
        )
        # Report 2 uploaded at t+20h, admittance_timestamp = t+5h
        r2 = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=CLAIM_ID, hospital_id=HOSPITAL_ID, uploaded_by=HOSP_USER_ID,
            file_reference="p2.pdf", document_type="HOSPITAL_BILL",
            admittance_timestamp=incident_time + timedelta(hours=5),
            uploaded_at=incident_time + timedelta(hours=20)
        )
        db.add_all([r1, r2])
        db.commit()

        result = compute_evidence_verification_score(claim, db)
        # Time scoring must use EARLIEST admittance (t+1h -> within 4h -> 20.0/20) and not upload timestamp
        assert result["breakdown"]["incident_time_match"]["score"] == 20.0
    finally:
        db.close()


def test_locality_scoring_match_and_mismatch():
    setup_verification_db()
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.id == CLAIM_ID).first()

        # Match case: hospital_locality = "Mumbai Central" (incident locality = "Mumbai Central")
        r1 = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=CLAIM_ID, hospital_id=HOSPITAL_ID, uploaded_by=HOSP_USER_ID,
            file_reference="p.pdf", document_type="HOSPITAL_ADMISSION_REPORT",
            hospital_locality="Mumbai Central"
        )
        db.add(r1)
        db.commit()
        res_match = compute_evidence_verification_score(claim, db)
        assert res_match["breakdown"]["hospital_locality_match"]["score"] == 15.0

        # Mismatch case: hospital_locality = "Pune"
        r1.hospital_locality = "Pune"
        db.commit()
        res_mismatch = compute_evidence_verification_score(claim, db)
        assert res_mismatch["breakdown"]["hospital_locality_match"]["score"] == 0.0
    finally:
        db.close()


def test_document_type_normalization():
    assert normalize_document_type("Hospital Bill") == "HOSPITAL_BILL"
    assert normalize_document_type("HOSPITAL_BILL") == "HOSPITAL_BILL"
    assert normalize_document_type("Bill") == "HOSPITAL_BILL"
    assert normalize_document_type("Hospital Admission Report") == "HOSPITAL_ADMISSION_REPORT"
    assert normalize_document_type("Prescription") == "PRESCRIPTION"
    assert normalize_document_type("Discharge Summary") == "DISCHARGE_SUMMARY"


def test_target_e2e_suhaas_100_score():
    setup_verification_db()
    db = SessionLocal()
    try:
        # Create synthetic claim for rider "Suhaas" in locality "Mumbai"
        suhaas_rider_id = uuid.uuid4()
        suhaas_hosp_id = uuid.uuid4()
        suhaas_shift_id = uuid.uuid4()
        suhaas_inc_id = uuid.uuid4()
        suhaas_claim_id = uuid.uuid4()

        hosp = Hospital(
            id=suhaas_hosp_id, name="RideShield Demo Hospital", locality="Mumbai", contact_number="9876543210", latitude=19.0760, longitude=72.8777
        )
        rider = User(
            id=suhaas_rider_id, email=f"suhaas_{uuid.uuid4().hex[:6]}@test.com", phone_number=f"9{uuid.uuid4().int % 1000000009:09d}", hashed_password="pwd", full_name="Suhaas", role=UserRole.RIDER, is_active=True
        )
        shift = Shift(
            id=suhaas_shift_id, rider_id=suhaas_rider_id, status=ShiftStatus.ACTIVE, start_time=datetime.now(timezone.utc) - timedelta(hours=5)
        )
        db.add_all([hosp, rider, shift])
        db.commit()

        inc_time = datetime.now(timezone.utc) - timedelta(hours=1)
        inc = Incident(
            id=suhaas_inc_id, rider_id=suhaas_rider_id, shift_id=suhaas_shift_id, status=IncidentStatus.DETECTED, locality="Mumbai", latitude=19.0760, longitude=72.8777, detected_at=inc_time, confidence_score=0.95, peak_g_force=5.0
        )
        cl = Claim(
            id=suhaas_claim_id, incident_id=suhaas_inc_id, rider_id=suhaas_rider_id, shift_id=suhaas_shift_id, claim_number=f"CLM-SUHAAS-{uuid.uuid4().hex[:6]}", status=ClaimStatus.MEDICAL_REPORT_SUBMITTED, claimed_amount=20000.0, filed_at=inc_time + timedelta(minutes=30)
        )
        db.add_all([inc, cl])
        db.commit()

        adm = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=suhaas_claim_id, hospital_id=suhaas_hosp_id, uploaded_by=HOSP_USER_ID, file_reference="adm.pdf", document_type="HOSPITAL_ADMISSION_REPORT",
            patient_identifier="Suhaas", facility_name="RideShield Demo Hospital", hospital_locality="Mumbai", admittance_timestamp=inc_time + timedelta(hours=1), diagnosis_notes="ACL injury following road incident."
        )
        bill = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=suhaas_claim_id, hospital_id=suhaas_hosp_id, uploaded_by=HOSP_USER_ID, file_reference="bill.pdf", document_type="HOSPITAL_BILL",
            patient_identifier="Suhaas", facility_name="RideShield Demo Hospital", hospital_locality="Mumbai", admittance_timestamp=inc_time + timedelta(hours=1), diagnosis_notes="ACL injury treatment and hospital charges."
        )
        rx = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=suhaas_claim_id, hospital_id=suhaas_hosp_id, uploaded_by=HOSP_USER_ID, file_reference="rx.pdf", document_type="PRESCRIPTION",
            patient_identifier="Suhaas", facility_name="RideShield Demo Hospital", hospital_locality="Mumbai", admittance_timestamp=inc_time + timedelta(hours=1), diagnosis_notes="Medication prescribed for ACL injury."
        )
        db.add_all([adm, bill, rx])
        db.commit()

        result = compute_evidence_verification_score(cl, db)
        assert result["score"] == 100.0
        assert result["band"] == "STRONG EVIDENCE"
    finally:
        db.close()


def test_unauthorized_delete_and_closed_claim_rejection():
    setup_verification_db()
    db = SessionLocal()
    try:
        # Create second hospital & user with unique credentials
        hosp2_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        hosp2 = Hospital(id=hosp2_id, name="Delhi Hospital", locality="Delhi", contact_number="8888888888", latitude=28.7, longitude=77.1)
        user2 = User(id=user2_id, email=f"hosp2_{uuid.uuid4().hex[:6]}@test.com", phone_number=f"8{uuid.uuid4().int % 1000000009:09d}", hashed_password="h", full_name="Hosp2", role=UserRole.HOSPITAL_REP, hospital_id=hosp2_id, is_active=True)
        db.add_all([hosp2, user2])

        r = ClaimMedicalReport(
            id=uuid.uuid4(), claim_id=CLAIM_ID, hospital_id=HOSPITAL_ID, uploaded_by=HOSP_USER_ID, file_reference="p.pdf", document_type="HOSPITAL_ADMISSION_REPORT", patient_identifier="Rajesh Kumar", hospital_locality="Mumbai Central"
        )
        db.add(r)
        db.commit()
        report_id = r.id

        token2 = get_token(user2_id)
        # Hospital B attempts to delete Hospital A's report -> 403
        res_unauth = client.delete(
            f"/claims/{CLAIM_ID}/reports/{report_id}",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert res_unauth.status_code == 403

        # Transition claim to UNDER_REVIEW
        claim = db.query(Claim).filter(Claim.id == CLAIM_ID).first()
        claim.status = ClaimStatus.UNDER_REVIEW
        db.commit()

        # Upload attempt on closed/under_review claim -> 409
        hosp1_token = get_token(HOSP_USER_ID)
        with open("dummy.pdf", "w") as f:
            f.write("d")
        with open("dummy.pdf", "rb") as f:
            res_closed_up = client.post(
                f"/claims/{CLAIM_ID}/reports",
                headers={"Authorization": f"Bearer {hosp1_token}"},
                files={"file": ("dummy.pdf", f, "application/pdf")},
                data={"document_type": "HOSPITAL_BILL"}
            )
        assert res_closed_up.status_code == 409
        if os.path.exists("dummy.pdf"):
            os.remove("dummy.pdf")

        # Delete attempt on closed/under_review claim -> 409
        res_closed_del = client.delete(
            f"/claims/{CLAIM_ID}/reports/{report_id}",
            headers={"Authorization": f"Bearer {hosp1_token}"}
        )
        assert res_closed_del.status_code == 409
    finally:
        db.close()
