import os
import sys
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import text
from fastapi.testclient import TestClient

# Add backend directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from main import app
from db.core.session import SessionLocal
from db.models.enums import UserRole, ClaimStatus, IncidentStatus
from db.models.claim import Claim

client = TestClient(app)

HOSPITAL_ID_1 = uuid.uuid4()
HOSPITAL_ID_2 = uuid.uuid4()
HOSP_USER_ID_1 = uuid.uuid4()
HOSP_USER_ID_2 = uuid.uuid4()
RIDER_ID = uuid.uuid4()
INSURER_ID = uuid.uuid4()
SHIFT_ID = uuid.uuid4()
INCIDENT_ID_1 = uuid.uuid4()
INCIDENT_ID_2 = uuid.uuid4()
CLAIM_ID_1 = uuid.uuid4()
CLAIM_ID_2 = uuid.uuid4()

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db = SessionLocal()
    try:
        # Create Hospitals
        db.execute(text(f"INSERT INTO hospitals (id, name, locality, contact_number, created_at) VALUES ('{HOSPITAL_ID_1}', 'Apollo Hospital', 'Mumbai', '1234567890', NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO hospitals (id, name, locality, contact_number, created_at) VALUES ('{HOSPITAL_ID_2}', 'Fortis', 'Delhi', '0987654321', NOW()) ON CONFLICT DO NOTHING;"))
        
        # Create Users
        rand = uuid.uuid4().hex[:4]
        hosp1_email = f"hosp1_{rand}@example.com"
        hosp2_email = f"hosp2_{rand}@example.com"
        rider_email = f"rider_{rand}@example.com"
        insurer_email = f"insurer_{rand}@example.com"
        
        db.execute(text(f"INSERT INTO users (id, email, hashed_password, full_name, phone_number, role, hospital_id, wallet_balance, is_active, created_at, updated_at) VALUES ('{HOSP_USER_ID_1}', '{hosp1_email}', 'hash', 'Apollo Rep', '+911{rand}', 'HOSPITAL_REP', '{HOSPITAL_ID_1}', 0.0, true, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO users (id, email, hashed_password, full_name, phone_number, role, hospital_id, wallet_balance, is_active, created_at, updated_at) VALUES ('{HOSP_USER_ID_2}', '{hosp2_email}', 'hash', 'Fortis Rep', '+912{rand}', 'HOSPITAL_REP', '{HOSPITAL_ID_2}', 0.0, true, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO users (id, email, hashed_password, full_name, phone_number, role, wallet_balance, is_active, created_at, updated_at) VALUES ('{RIDER_ID}', '{rider_email}', 'hash', 'Test Rider', '+913{rand}', 'RIDER', 500.0, true, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO users (id, email, hashed_password, full_name, phone_number, role, wallet_balance, is_active, created_at, updated_at) VALUES ('{INSURER_ID}', '{insurer_email}', 'hash', 'Test Insurer', '+914{rand}', 'INSURER', 0.0, true, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        
        # Create RiderProfile and Shift
        db.execute(text(f"INSERT INTO rider_profiles (id, user_id, vehicle_type, safety_rating, kyc_status, created_at, updated_at) VALUES ('{RIDER_ID}', '{RIDER_ID}', 'Bicycle', 5.00, 'PENDING', NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO shifts (id, rider_id, status, start_time, distance_km, premium_amount, created_at, updated_at) VALUES ('{SHIFT_ID}', '{RIDER_ID}', 'ACTIVE', NOW(), 0.0, 0.0, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        
        # Create Incidents (One in Mumbai, One in Delhi)
        db.execute(text(f"INSERT INTO incidents (id, shift_id, rider_id, status, detected_at, peak_g_force, confidence_score, latitude, longitude, locality, created_at, updated_at) VALUES ('{INCIDENT_ID_1}', '{SHIFT_ID}', '{RIDER_ID}', 'VERIFIED_ACCIDENT', NOW(), 2.5, 0.9, 19.07, 72.87, 'Mumbai', NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO incidents (id, shift_id, rider_id, status, detected_at, peak_g_force, confidence_score, latitude, longitude, locality, created_at, updated_at) VALUES ('{INCIDENT_ID_2}', '{SHIFT_ID}', '{RIDER_ID}', 'VERIFIED_ACCIDENT', NOW(), 2.5, 0.9, 28.70, 77.10, 'Delhi', NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        
        # Create Claims
        db.execute(text(f"INSERT INTO claims (id, incident_id, rider_id, shift_id, claim_number, status, claimed_amount, filed_at, updated_at) VALUES ('{CLAIM_ID_1}', '{INCIDENT_ID_1}', '{RIDER_ID}', '{SHIFT_ID}', 'CLM-1-{rand}', 'MEDICAL_REPORT_PENDING', 1000.0, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO claims (id, incident_id, rider_id, shift_id, claim_number, status, claimed_amount, filed_at, updated_at) VALUES ('{CLAIM_ID_2}', '{INCIDENT_ID_2}', '{RIDER_ID}', '{SHIFT_ID}', 'CLM-2-{rand}', 'MEDICAL_REPORT_PENDING', 1000.0, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

# Mock JWT token generation for testing
def get_auth_headers(user_id: uuid.UUID):
    # The actual implementation creates a JWT, we can mock get_current_user in fastapi
    from app.api import deps
    from db.models.user import User
    
    def override_get_current_user():
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        user = db.query(User).options(joinedload(User.hospital), joinedload(User.rider_profile)).filter(User.id == user_id).first()
        db.close()
        return user
        
    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    return {}

def test_hospital_locality_filtering():
    get_auth_headers(HOSP_USER_ID_1)
    response = client.get("/claims")
    assert response.status_code == 200
    claims = response.json()
    assert len(claims) >= 1
    assert any(c['id'] == str(CLAIM_ID_1) for c in claims)

def test_hospital_claim_id_tampering():
    get_auth_headers(HOSP_USER_ID_1)
    # Try to read CLAIM_ID_2 which belongs to Delhi
    response = client.get(f"/claims/{CLAIM_ID_2}")
    assert response.status_code == 403

def test_cross_role_route_denial():
    # Insurer tries to upload report
    get_auth_headers(INSURER_ID)
    with open("dummy.pdf", "w") as f:
        f.write("dummy")
    
    with open("dummy.pdf", "rb") as f:
        files = {"file": ("dummy.pdf", f, "application/pdf")}
        data = {"document_type": "FIR"}
        response = client.post(f"/claims/{CLAIM_ID_1}/reports", files=files, data=data)
        
    assert response.status_code == 403
    os.remove("dummy.pdf")

def test_medical_report_upload_state_transition_and_download():
    # Verify CLAIM_ID_2 is initially MEDICAL_REPORT_PENDING
    get_auth_headers(INSURER_ID)
    res_b_before = client.get(f"/claims/{CLAIM_ID_2}")
    assert res_b_before.status_code == 200
    assert res_b_before.json()["status"] == "MEDICAL_REPORT_PENDING"
    assert len(res_b_before.json()["medical_reports"]) == 0

    # Hospital uploads report for CLAIM_ID_1
    get_auth_headers(HOSP_USER_ID_1)
    with open("dummy.pdf", "w") as f:
        f.write("dummy content")
    
    with open("dummy.pdf", "rb") as f:
        files = {"file": ("dummy.pdf", f, "application/pdf")}
        data = {"document_type": "FIR", "notes": "Test"}
        response = client.post(f"/claims/{CLAIM_ID_1}/reports", files=files, data=data)
        
    assert response.status_code == 200
    claim_a = response.json()
    assert claim_a["status"] == "MEDICAL_REPORT_SUBMITTED"
    assert len(claim_a["medical_reports"]) > 0
    report_id = claim_a["medical_reports"][0]["id"]
    os.remove("dummy.pdf")

    # Verify CLAIM_ID_2 remains MEDICAL_REPORT_PENDING and has 0 medical reports
    get_auth_headers(INSURER_ID)
    res_b_after = client.get(f"/claims/{CLAIM_ID_2}")
    assert res_b_after.status_code == 200
    assert res_b_after.json()["status"] == "MEDICAL_REPORT_PENDING"
    assert len(res_b_after.json()["medical_reports"]) == 0

    # Test Insurer downloading report via Claim 1
    dl_response = client.get(f"/claims/{CLAIM_ID_1}/reports/{report_id}/download")
    assert dl_response.status_code == 200
    assert dl_response.content == b"dummy content"

    # Security check: Download report for Claim 1 using Claim 2's ID must fail with 404
    dl_response_cross = client.get(f"/claims/{CLAIM_ID_2}/reports/{report_id}/download")
    assert dl_response_cross.status_code == 404

def test_decision_boundaries_and_review_flow():
    get_auth_headers(INSURER_ID)
    
    # Try to approve CLAIM_ID_1 which is MEDICAL_REPORT_SUBMITTED, not UNDER_REVIEW
    response = client.post(f"/claims/{CLAIM_ID_1}/approve", params={"approved_amount": 1000})
    assert response.status_code == 400
    assert "UNDER_REVIEW" in response.json()["detail"]
    
    # Try to reject CLAIM_ID_1 which is MEDICAL_REPORT_SUBMITTED
    response = client.post(f"/claims/{CLAIM_ID_1}/reject", params={"rejection_reason": "No reason"})
    assert response.status_code == 400
    assert "UNDER_REVIEW" in response.json()["detail"]
    
    # Hospital rep tries to approve -> 403
    get_auth_headers(HOSP_USER_ID_1)
    response = client.post(f"/claims/{CLAIM_ID_1}/approve", params={"approved_amount": 1000})
    assert response.status_code == 403

    # Insurer moves claim to UNDER_REVIEW
    get_auth_headers(INSURER_ID)
    review_res = client.post(f"/claims/{CLAIM_ID_1}/review")
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "UNDER_REVIEW"

    # Insurer approves claim from UNDER_REVIEW -> 200
    approve_res = client.post(f"/claims/{CLAIM_ID_1}/approve", params={"approved_amount": 1000})
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

def test_separation_of_escalation_from_claims():
    get_auth_headers(RIDER_ID)
    
    # Trigger run_incident_escalation by posting to /incidents/{id}/help
    # Ensure it doesn't auto-create a claim
    # Creating a new incident for this test
    NEW_INCIDENT_ID = uuid.uuid4()
    db = SessionLocal()
    db.execute(text(f"INSERT INTO incidents (id, shift_id, rider_id, status, detected_at, peak_g_force, confidence_score, latitude, longitude, locality, created_at, updated_at) VALUES ('{NEW_INCIDENT_ID}', '{SHIFT_ID}', '{RIDER_ID}', 'DETECTED', NOW(), 2.5, 0.9, 19.07, 72.87, 'Mumbai', NOW(), NOW()) ON CONFLICT DO NOTHING;"))
    db.commit()
    db.close()
    
    response = client.post(f"/incidents/{NEW_INCIDENT_ID}/help")
    assert response.status_code == 200
    
    # Verify no claim exists for this incident
    db = SessionLocal()
    claim = db.query(Claim).filter(Claim.incident_id == str(NEW_INCIDENT_ID)).first()
    db.close()
    assert claim is None
