import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from db.models.enums import IncidentStatus
from app.services.incident_decision_engine import assess_evidence_confidence, resolve_verdict


class TestAssessEvidenceConfidence:
    def test_high_ml_confidence_on_good_window_is_high(self):
        result = assess_evidence_confidence(
            scoring_method="ml", confidence_score=0.9, peak_g_force=6.0,
            window_quality="good", post_impact_stillness=True, speed_drop=40.0,
        )
        assert result.confidence_label == "high"
        assert any("high_ml_confidence" in e for e in result.evidence)
        assert "post_impact_stillness" in result.evidence

    def test_strong_rule_based_evidence_without_ml_is_high(self):
        # No ML (rule_based_fallback), but peak-G above threshold AND corroborated.
        result = assess_evidence_confidence(
            scoring_method="rule_based_fallback", confidence_score=0.55, peak_g_force=7.0,
            window_quality="good", post_impact_stillness=True, speed_drop=None,
        )
        assert result.confidence_label == "high"

    def test_degraded_window_discounts_ml_confidence(self):
        # Same high ML confidence as the first test, but window is degraded —
        # must NOT reach "high" purely off the (untrustworthy) ML score.
        result = assess_evidence_confidence(
            scoring_method="ml", confidence_score=0.9, peak_g_force=2.0,
            window_quality="degraded", post_impact_stillness=False, speed_drop=None,
        )
        assert result.confidence_label != "high"
        assert any("window_quality_degraded" in e for e in result.evidence)

    def test_weak_evidence_all_around_is_low(self):
        result = assess_evidence_confidence(
            scoring_method="rule_based_fallback", confidence_score=0.1, peak_g_force=1.2,
            window_quality="good", post_impact_stillness=False, speed_drop=None,
        )
        assert result.confidence_label == "low"

    def test_never_raises_regardless_of_input_combination(self):
        # None values for optional evidence must not crash the assessment.
        result = assess_evidence_confidence(
            scoring_method="rule_based_fallback", confidence_score=0.0, peak_g_force=0.0,
            window_quality="insufficient", post_impact_stillness=None, speed_drop=None,
        )
        assert result.confidence_label in ("high", "medium", "low")


class TestResolveVerdict:
    def test_okay_is_always_false_positive(self):
        assert resolve_verdict(rider_response="okay", confidence_label="high") == IncidentStatus.FALSE_POSITIVE
        assert resolve_verdict(rider_response="okay", confidence_label="low") == IncidentStatus.FALSE_POSITIVE

    def test_help_is_always_verified_accident(self):
        assert resolve_verdict(rider_response="help", confidence_label="low") == IncidentStatus.VERIFIED_ACCIDENT
        assert resolve_verdict(rider_response="help", confidence_label="high") == IncidentStatus.VERIFIED_ACCIDENT

    def test_no_response_is_always_verified_accident_regardless_of_confidence(self):
        """The safety floor: this must hold for EVERY confidence_label,
        including 'low' — a weak evidence assessment must never suppress
        or downgrade the emergency escalation when the rider is silent."""
        for label in ("high", "medium", "low", "insufficient", "anything-unexpected"):
            assert resolve_verdict(rider_response="no_response", confidence_label=label) == IncidentStatus.VERIFIED_ACCIDENT
