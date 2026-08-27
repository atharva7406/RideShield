import json
import uuid
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from db.models.claim import Claim
from db.models.claim_medical_report import ClaimMedicalReport
from db.models.evidence import IncidentEvidence
from db.models.enums import DocumentType, ClaimStatus
from db.models.audit import AuditEvent


def normalize_document_type(doc_type: str) -> str:
    if not doc_type:
        return "OTHER_SUPPORTING_DOCUMENT"
    raw = doc_type.strip().upper().replace(" ", "_")

    if raw in ["HOSPITAL_ADMISSION_REPORT", "ADMISSION_REPORT", "HOSPITAL_ADMISSION", "ADMISSION", "MEDICAL_REPORT", "FIR"]:
        return "HOSPITAL_ADMISSION_REPORT"
    elif raw in ["HOSPITAL_BILL", "BILL", "MEDICAL_BILL"]:
        return "HOSPITAL_BILL"
    elif raw in ["PRESCRIPTION", "DOCTOR_PRESCRIPTION"]:
        return "PRESCRIPTION"
    elif raw in ["DISCHARGE_SUMMARY", "DISCHARGE"]:
        return "DISCHARGE_SUMMARY"
    elif raw in ["OTHER_SUPPORTING_DOCUMENT", "OTHER", "SUPPORTING_DOCUMENT", "LAB_REPORT", "SCAN_REPORT"]:
        return "OTHER_SUPPORTING_DOCUMENT"
    else:
        return raw


def compute_evidence_verification_score(claim: Claim, db: Session) -> Dict[str, Any]:
    """
    Computes a transparent, explainable 0-100 evidence verification score across 6 weighted factors:
    1. Patient identity match       30%
    2. Incident time match          20%
    3. Hospital/locality match      15%
    4. Document completeness        15%
    5. Diagnosis/injury consistency 10%
    6. Claim metadata consistency   10%

    Returns a dict containing total score, risk band, and per-factor breakdown.
    This service is a decision aid for insurers and does NOT decide claim outcomes by itself.
    """
    incident = claim.incident
    rider = claim.rider
    raw_medical_reports: List[ClaimMedicalReport] = claim.medical_reports or []

    # Sort reports deterministically by admittance_timestamp ASC, then id ASC
    def sort_key(r: ClaimMedicalReport):
        t = r.admittance_timestamp or r.uploaded_at
        if t and t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (t or datetime.max.replace(tzinfo=timezone.utc), r.id)

    medical_reports = sorted(raw_medical_reports, key=sort_key)

    # Get legacy evidence entries if any
    evidence_items = db.query(IncidentEvidence).filter(
        (IncidentEvidence.claim_id == claim.id) |
        ((IncidentEvidence.incident_id == claim.incident_id) & (IncidentEvidence.claim_id == None))
    ).all()

    # Factor 1: Patient Identity Match (30%)
    rider_name = (rider.full_name if rider and rider.full_name else "").strip().lower()
    rider_name_norm = re.sub(r'\s+', ' ', rider_name)

    patient_identifiers = []
    for r in medical_reports:
        pid = r.patient_identifier or r.notes
        if pid:
            norm_pid = re.sub(r'\s+', ' ', pid.strip().lower())
            patient_identifiers.append(norm_pid)

    for ev in evidence_items:
        if ev.file_url:
            try:
                data = json.loads(ev.file_url)
                if isinstance(data, dict) and "patient_identifier" in data:
                    norm_pid = re.sub(r'\s+', ' ', str(data["patient_identifier"]).strip().lower())
                    patient_identifiers.append(norm_pid)
            except Exception:
                pass

    score_identity = 0.0
    identity_detail = "No patient identifier provided"

    if not patient_identifiers:
        score_identity = 0.0
        identity_detail = "No patient identifier provided in medical evidence"
    elif rider_name_norm:
        rider_words = [w for w in rider_name_norm.split() if len(w) > 1]
        
        has_mismatch = False
        full_match_count = 0
        partial_match_count = 0

        for pid in patient_identifiers:
            if rider_name_norm in pid or pid in rider_name_norm:
                full_match_count += 1
            elif any(w in pid for w in rider_words):
                partial_match_count += 1
            else:
                has_mismatch = True

        if has_mismatch:
            score_identity = 0.0
            identity_detail = f"Explicit patient identifier mismatch detected vs rider '{rider.full_name}'"
        elif full_match_count == len(patient_identifiers):
            score_identity = 30.0
            identity_detail = f"Patient identifier matches rider '{rider.full_name}' across all documents"
        elif (full_match_count + partial_match_count) > 0:
            score_identity = 15.0
            identity_detail = f"Partial match between patient identifier and rider '{rider.full_name}'"
        else:
            score_identity = 0.0
            identity_detail = f"Mismatched patient identifier vs rider '{rider.full_name}'"

    # Factor 2: Incident Time Match (20%)
    score_time = 0.0
    time_detail = "No admittance timestamp available for comparison"

    if incident and incident.detected_at:
        incident_time = incident.detected_at
        if incident_time.tzinfo is None:
            incident_time = incident_time.replace(tzinfo=timezone.utc)

        admittance_timestamps = []
        for r in medical_reports:
            t = r.admittance_timestamp or r.uploaded_at
            if t:
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                admittance_timestamps.append(t)

        for ev in evidence_items:
            if ev.file_url:
                try:
                    data = json.loads(ev.file_url)
                    if isinstance(data, dict) and "admission_timestamp" in data:
                        t = datetime.fromisoformat(data["admission_timestamp"])
                        if t.tzinfo is None:
                            t = t.replace(tzinfo=timezone.utc)
                        admittance_timestamps.append(t)
                except Exception:
                    pass

        if admittance_timestamps:
            earliest_admittance = min(admittance_timestamps)
            delta_hours = (earliest_admittance - incident_time).total_seconds() / 3600.0

            if delta_hours < 0:
                score_time = 0.0
                time_detail = f"Admittance timestamp precedes incident detection time ({delta_hours:.1f} hours)"
            elif 0 <= delta_hours <= 4.0:
                score_time = 20.0
                time_detail = f"Hospital admittance within {delta_hours:.1f} hours of incident"
            elif 4.0 < delta_hours <= 12.0:
                score_time = 14.0
                time_detail = f"Hospital admittance within {delta_hours:.1f} hours of incident"
            elif 12.0 < delta_hours <= 24.0:
                score_time = 8.0
                time_detail = f"Hospital admittance within {delta_hours:.1f} hours of incident"
            else:
                score_time = 2.0
                time_detail = f"Large time gap ({delta_hours:.1f} hours) between incident and hospital admittance"
        else:
            score_time = 0.0
            time_detail = "No admittance timestamp available for comparison"

    # Factor 3: Hospital / Locality Match (15%)
    score_locality = 0.0
    locality_detail = "Locality information missing"

    inc_locality = (incident.locality if incident and incident.locality else "").strip().lower()
    inc_locality_norm = re.sub(r'\s+', ' ', inc_locality)

    if not inc_locality_norm or inc_locality_norm == "unknown":
        score_locality = 0.0
        locality_detail = "Incident locality unavailable."
    else:
        hosp_localities = []
        for r in medical_reports:
            loc = r.hospital_locality or (r.hospital.locality if r.hospital else None)
            if loc:
                hosp_localities.append(re.sub(r'\s+', ' ', loc.strip().lower()))

        if not hosp_localities:
            score_locality = 0.0
            locality_detail = "Hospital locality missing from submitted documents."
        else:
            has_locality_mismatch = False
            match_count = 0
            for hloc in hosp_localities:
                if inc_locality_norm in hloc or hloc in inc_locality_norm:
                    match_count += 1
                else:
                    has_locality_mismatch = True

            if has_locality_mismatch:
                score_locality = 0.0
                locality_detail = f"Locality mismatch: Incident in '{incident.locality}', Report in '{hosp_localities[0]}'"
            elif match_count > 0:
                score_locality = 15.0
                locality_detail = f"Locality match: '{incident.locality}' across submitted documents"

    # Factor 4: Document Completeness (15%)
    score_completeness = 0.0
    completeness_detail = "No medical documents attached"

    if medical_reports or evidence_items:
        doc_types = {normalize_document_type(r.document_type) for r in medical_reports}
        if evidence_items:
            doc_types.add("HOSPITAL_ADMISSION_REPORT")

        has_admission = "HOSPITAL_ADMISSION_REPORT" in doc_types
        has_supporting = any(t in ["HOSPITAL_BILL", "PRESCRIPTION", "DISCHARGE_SUMMARY", "OTHER_SUPPORTING_DOCUMENT"] for t in doc_types)

        if has_admission and has_supporting:
            score_completeness = 15.0
            completeness_detail = "Complete evidence bundle (admission report + supporting bill/prescription)"
        elif has_admission:
            score_completeness = 9.0
            completeness_detail = "Primary admission report attached; supporting bills/prescriptions pending"
        elif has_supporting:
            score_completeness = 4.5
            completeness_detail = "Supporting document attached; primary admission report missing"
        else:
            score_completeness = 0.0
            completeness_detail = "No medical documents attached"

    # Factor 5: Diagnosis / Injury Consistency (10%)
    score_diagnosis = 0.0
    diagnosis_detail = "No diagnosis or injury notes submitted"

    notes_list = [r.diagnosis_notes or r.notes for r in medical_reports if r.diagnosis_notes or r.notes]
    for ev in evidence_items:
        if ev.file_url:
            try:
                data = json.loads(ev.file_url)
                if isinstance(data, dict) and "injury_description" in data:
                    notes_list.append(data["injury_description"])
            except Exception:
                pass

    combined_notes = " ".join(filter(None, notes_list)).strip()
    if len(combined_notes) >= 15:
        score_diagnosis = 10.0
        diagnosis_detail = "Detailed diagnosis and injury notes provided"
    elif len(combined_notes) > 0:
        score_diagnosis = 5.0
        diagnosis_detail = "Brief injury notes provided"
    else:
        score_diagnosis = 0.0
        diagnosis_detail = "No diagnosis or injury notes submitted"

    # Factor 6: Claim Metadata Consistency (10%)
    score_metadata = 10.0
    metadata_detail = "Claim metadata fully consistent"

    if claim.claimed_amount <= 0:
        score_metadata = 0.0
        metadata_detail = "Invalid claimed amount"
    elif incident and claim.rider_id != incident.rider_id:
        score_metadata = 0.0
        metadata_detail = "Claim rider ID mismatch with incident"
    elif incident and claim.shift_id != incident.shift_id:
        score_metadata = 0.0
        metadata_detail = "Claim shift ID mismatch with incident"

    # Calculate Total Score (0 - 100)
    total_score = round(score_identity + score_time + score_locality + score_completeness + score_diagnosis + score_metadata, 1)

    # Determine Risk Band
    if total_score >= 90.0:
        risk_band = "STRONG EVIDENCE"
    elif total_score >= 75.0:
        risk_band = "GOOD EVIDENCE"
    elif total_score >= 50.0:
        risk_band = "REVIEW REQUIRED"
    else:
        risk_band = "HIGH RISK/MISMATCH"

    breakdown = {
        "patient_identity_match": {
            "score": round(score_identity, 1),
            "max": 30.0,
            "passed": score_identity >= 15.0,
            "detail": identity_detail
        },
        "incident_time_match": {
            "score": round(score_time, 1),
            "max": 20.0,
            "passed": score_time >= 10.0,
            "detail": time_detail
        },
        "hospital_locality_match": {
            "score": round(score_locality, 1),
            "max": 15.0,
            "passed": score_locality >= 10.0,
            "detail": locality_detail
        },
        "document_completeness": {
            "score": round(score_completeness, 1),
            "max": 15.0,
            "passed": score_completeness >= 9.0,
            "detail": completeness_detail
        },
        "diagnosis_consistency": {
            "score": round(score_diagnosis, 1),
            "max": 10.0,
            "passed": score_diagnosis >= 5.0,
            "detail": diagnosis_detail
        },
        "claim_metadata_consistency": {
            "score": round(score_metadata, 1),
            "max": 10.0,
            "passed": score_metadata >= 10.0,
            "detail": metadata_detail
        }
    }

    return {
        "score": total_score,
        "band": risk_band,
        "breakdown": breakdown
    }


def run_and_persist_evidence_verification(claim_id: uuid.UUID, db: Session) -> Dict[str, Any]:
    """
    Executes the evidence verification calculation for a claim and persists the result in an AuditEvent.
    If the claim is in a terminal state (APPROVED or REJECTED), raises 409 Conflict.
    """
    from fastapi import HTTPException
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return {"score": 0.0, "band": "HIGH RISK/MISMATCH", "breakdown": {}}

    if claim.status in [ClaimStatus.APPROVED, ClaimStatus.REJECTED]:
        raise HTTPException(
            status_code=409,
            detail=f"Claim {claim_id} is closed in terminal state {claim.status} and cannot be re-verified"
        )

    result = compute_evidence_verification_score(claim, db)

    # Persist in AuditEvent
    audit = AuditEvent(
        id=uuid.uuid4(),
        claim_id=claim.id,
        entity_type="claim",
        entity_id=claim.id,
        event_type="CLAIM_VERIFICATION_RUN",
        performed_by_user_id=claim.rider_id,
        metadata_json={
            "verification_score": result["score"],
            "verification_band": result["band"],
            "verification_details": result["breakdown"],
            "calculated_at": datetime.now(timezone.utc).isoformat()
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()

    return result
