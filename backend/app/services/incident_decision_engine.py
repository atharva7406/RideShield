"""
Incident Decision Engine — Phase 4.

The single place that turns evidence (ML score, window quality, Tier-0-
style post-impact/GPS signals, rider response) into an IncidentStatus.
Before this phase, `incident.status = IncidentStatus.X` was written
directly in four different places (incidents.py's incident_okay/
incident_help/run_incident_escalation, whatsapp.py's chatbot handler) with
no shared logic — "two state machines" in spirit even though they used the
same enum. Everything that sets an automated verdict now goes through
resolve_verdict() below.

THE SAFETY FLOOR — read this before touching resolve_verdict():

  An unresponsive rider is itself the strongest safety signal there is.
  No combination of ML score, window quality, or supporting evidence is
  ever allowed to downgrade or skip the emergency escalation when the
  rider does not respond. resolve_verdict(rider_response="no_response",
  ...) therefore ALWAYS returns VERIFIED_ACCIDENT, unconditionally — full
  stop, not "usually", not "unless confidence is low". Evidence fusion in
  this module only ever affects `confidence_label` and `evidence` (what
  gets recorded and shown to a human reviewer), never the escalation
  decision itself. This is the concrete form of the project's own rule:
  "Tier 0 detects and protects. ML refines confidence. Decision Engine
  decides. Verification establishes trust." — refining confidence must
  never mean refining away the safety net.

  Similarly, an explicit rider response ("I'm okay" / "I need help") is
  authoritative and always wins over circumstantial evidence — a rider
  who says they're fine is trusted, not second-guessed by a high ML
  score; a rider who asks for help gets help immediately, not weighed
  against a low ML score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from db.models.enums import IncidentStatus

RiderResponse = Literal["okay", "help", "no_response"]

# Thresholds are simple and explainable by design — not hand-picked
# weights in a combined score. ml_scoring_service's own module docstring
# (and feature_extraction.py's) explicitly defer weight-tuning to a future
# properly-trained/calibrated stage; this module sticks to plain,
# auditable rules over the same signals, same spirit as the on-device
# rule engine (rider-app/src/crash-detection/crashDetector.ts).
_STRONG_ML_CONFIDENCE = 0.6
_MODERATE_ML_CONFIDENCE = 0.4
_RULE_CRASH_THRESHOLD_G = 4.0  # mirrors ml_scoring_service._RULE_CRASH_THRESHOLD_G
_STRONG_SPEED_DROP_KMH = 30.0


@dataclass
class EvidenceAssessment:
    confidence_label: str  # "high" | "medium" | "low"
    evidence: list[str] = field(default_factory=list)


def assess_evidence_confidence(
    *,
    scoring_method: str,  # "ml" | "rule_based_fallback"
    confidence_score: float,
    peak_g_force: float,
    window_quality: str,  # "good" | "degraded" | "insufficient"
    post_impact_stillness: Optional[bool],
    speed_drop: Optional[float],
) -> EvidenceAssessment:
    """Fuses ML score + window quality + Tier-0-style corroborating
    signals into a human-readable confidence label. Pure annotation — see
    module docstring. Called once at window-scoring time so the label is
    available immediately, before any rider response exists.
    """
    evidence: list[str] = []

    # A degraded window means the model saw an input distribution it
    # wasn't calibrated for (see window_quality_service.py's docstring) —
    # discount the ML score's weight rather than trusting it at face
    # value, and lean on the deterministic G-force rule instead, same as
    # the on-device Tier-0 detector already does.
    ml_trustworthy = scoring_method == "ml" and window_quality == "good"
    if not ml_trustworthy and scoring_method == "ml":
        evidence.append("window_quality_degraded_ml_confidence_discounted")

    corroborated = bool(post_impact_stillness) or (
        speed_drop is not None and speed_drop >= _STRONG_SPEED_DROP_KMH
    )
    if post_impact_stillness:
        evidence.append("post_impact_stillness")
    if speed_drop is not None and speed_drop >= _STRONG_SPEED_DROP_KMH:
        evidence.append(f"gps_speed_drop_{speed_drop:.0f}kmh")

    strong_ml = ml_trustworthy and confidence_score >= _STRONG_ML_CONFIDENCE
    strong_rule = peak_g_force >= _RULE_CRASH_THRESHOLD_G and corroborated

    if strong_ml:
        evidence.append(f"high_ml_confidence_{confidence_score:.2f}")
    if peak_g_force >= _RULE_CRASH_THRESHOLD_G:
        evidence.append(f"peak_g_force_{peak_g_force:.1f}_above_threshold")

    if strong_ml or strong_rule:
        confidence_label = "high"
    elif (ml_trustworthy and confidence_score >= _MODERATE_ML_CONFIDENCE) or peak_g_force >= _RULE_CRASH_THRESHOLD_G:
        confidence_label = "medium"
    else:
        confidence_label = "low"

    if window_quality != "good":
        evidence.append(f"window_quality_{window_quality}")

    return EvidenceAssessment(confidence_label=confidence_label, evidence=evidence)


def resolve_verdict(
    *,
    rider_response: RiderResponse,
    confidence_label: str,
) -> IncidentStatus:
    """The ONE place an automated/rider-driven Incident status transition
    is decided. See module docstring for the safety-floor rule this
    enforces — read it before changing this function.
    """
    if rider_response == "okay":
        return IncidentStatus.FALSE_POSITIVE
    if rider_response == "help":
        return IncidentStatus.VERIFIED_ACCIDENT
    # rider_response == "no_response": unconditional safety floor.
    # confidence_label is accepted as a parameter (not read here) purely
    # so callers are reminded it exists and gets recorded alongside this
    # verdict — it must never gate the branch above.
    return IncidentStatus.VERIFIED_ACCIDENT
