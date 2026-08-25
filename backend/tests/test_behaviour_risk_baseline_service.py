import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from dataclasses import dataclass

import pytest

from app.services import behaviour_risk_baseline_service as svc


@dataclass
class FakeProfile:
    recent_hard_braking_rate: float = 0.0
    recent_hard_acceleration_rate: float = 0.0
    recent_overspeeding_rate: float = 0.0
    recent_sharp_turn_rate: float = 0.0
    recent_max_g: float = 1.0
    long_term_hard_braking_rate: float = 0.0
    long_term_overspeeding_rate: float = 0.0
    behaviour_consistency_score: float = 100.0
    overall_behaviour_score: float = 100.0
    data_quality_score: float = 0.9
    confidence: float = 0.9
    based_on_shift_count: int = 15
    based_on_valid_shift_count: int = 15


def _very_safe_profile(**overrides) -> FakeProfile:
    return FakeProfile(**overrides)


def _aggressive_profile(**overrides) -> FakeProfile:
    defaults = dict(
        recent_hard_braking_rate=15.0, recent_hard_acceleration_rate=12.0,
        recent_overspeeding_rate=10.0, recent_sharp_turn_rate=8.0, recent_max_g=4.5,
        long_term_hard_braking_rate=14.0, long_term_overspeeding_rate=9.0,
        behaviour_consistency_score=30.0, overall_behaviour_score=25.0,
        data_quality_score=0.9, confidence=0.9,
        based_on_shift_count=15, based_on_valid_shift_count=15,
    )
    defaults.update(overrides)
    return FakeProfile(**defaults)


class TestColdStart:
    def test_none_profile_returns_cold_start(self):
        result = svc.assess_rider_risk(None)
        assert result.is_cold_start is True
        assert result.risk_score is None
        assert result.risk_band is None
        assert result.scoring_method == svc.SCORING_METHOD_COLD_START
        assert result.confidence == 0.0
        assert result.suggested_pricing_mode == "COLD_START_DEFAULT"

    def test_cold_start_does_not_fabricate_a_score(self):
        result = svc.assess_cold_start()
        assert result.risk_score is None
        assert result.contributors == []

    def test_cold_start_has_a_reason(self):
        result = svc.assess_rider_risk(None)
        assert result.cold_start_reason


class TestVerySafeVsAggressive:
    def test_safe_rider_scores_much_lower_than_aggressive(self):
        safe = svc.assess_rider_risk(_very_safe_profile())
        aggressive = svc.assess_rider_risk(_aggressive_profile())
        assert safe.risk_score < 20.0
        assert aggressive.risk_score > 60.0
        assert safe.risk_score < aggressive.risk_score

    def test_safe_rider_lands_in_very_low_band(self):
        result = svc.assess_rider_risk(_very_safe_profile())
        assert result.risk_band == svc.RISK_BAND_VERY_LOW

    def test_aggressive_rider_lands_in_high_or_very_high_band(self):
        result = svc.assess_rider_risk(_aggressive_profile())
        assert result.risk_band in (svc.RISK_BAND_HIGH, svc.RISK_BAND_VERY_HIGH)

    def test_scoring_method_is_baseline_not_cold_start(self):
        result = svc.assess_rider_risk(_very_safe_profile())
        assert result.scoring_method == svc.SCORING_METHOD_BASELINE
        assert result.is_cold_start is False


class TestMixedRecentAndOldBehaviour:
    def test_bad_recent_but_safe_long_term_scores_lower_than_bad_both(self):
        bad_recent_safe_long_term = _aggressive_profile(
            long_term_hard_braking_rate=0.5, long_term_overspeeding_rate=0.0,
        )
        bad_both = _aggressive_profile()

        result_mixed = svc.assess_rider_risk(bad_recent_safe_long_term)
        result_bad_both = svc.assess_rider_risk(bad_both)

        assert result_mixed.risk_score < result_bad_both.risk_score

    def test_safe_long_term_discount_appears_as_a_named_contributor(self):
        profile = _aggressive_profile(long_term_hard_braking_rate=0.0, long_term_overspeeding_rate=0.0)
        result = svc.assess_rider_risk(profile)
        discount = next(c for c in result.contributors if c.factor == "safe_long_term_behaviour")
        assert discount.impact < 0
        assert discount.direction == "reduces_risk"


class TestIndividualHighSignals:
    def test_high_overspeeding_is_a_dominant_contributor(self):
        profile = _very_safe_profile(recent_overspeeding_rate=15.0)
        result = svc.assess_rider_risk(profile)
        contributor = next(c for c in result.contributors if c.factor == "recent_overspeeding_rate")
        assert contributor.impact > 0
        assert result.risk_score > 0

    def test_high_hard_braking_rate_increases_score(self):
        safe = svc.assess_rider_risk(_very_safe_profile())
        high_braking = svc.assess_rider_risk(_very_safe_profile(recent_hard_braking_rate=12.0))
        assert high_braking.risk_score > safe.risk_score

    def test_high_sharp_turn_rate_increases_score(self):
        safe = svc.assess_rider_risk(_very_safe_profile())
        high_turns = svc.assess_rider_risk(_very_safe_profile(recent_sharp_turn_rate=12.0))
        assert high_turns.risk_score > safe.risk_score

    def test_high_max_g_increases_score(self):
        safe = svc.assess_rider_risk(_very_safe_profile())
        high_g = svc.assess_rider_risk(_very_safe_profile(recent_max_g=5.0))
        assert high_g.risk_score > safe.risk_score

    def test_max_g_at_baseline_contributes_nothing(self):
        result = svc.assess_rider_risk(_very_safe_profile(recent_max_g=1.0))
        g_contributor = next(c for c in result.contributors if c.factor == "recent_max_g")
        assert g_contributor.impact == pytest.approx(0.0)

    def test_single_extreme_rate_cannot_dominate_unboundedly(self):
        profile = _very_safe_profile(recent_overspeeding_rate=100000.0)
        result = svc.assess_rider_risk(profile)
        contributor = next(c for c in result.contributors if c.factor == "recent_overspeeding_rate")
        assert contributor.impact <= svc.MAX_TERM_CONTRIBUTION


class TestDataQualityAndConfidence:
    def test_excellent_data_quality_gives_high_confidence_with_enough_history(self):
        result = svc.assess_rider_risk(_very_safe_profile(data_quality_score=0.98, confidence=0.95))
        assert result.confidence > 0.8

    def test_poor_data_quality_reduces_confidence_but_still_returns_a_score(self):
        result = svc.assess_rider_risk(_very_safe_profile(data_quality_score=0.2, confidence=0.15))
        assert result.confidence < 0.3
        assert result.risk_score is not None  # estimate preserved, per spec item 6
        assert result.is_cold_start is False

    def test_low_shift_history_has_lower_confidence_than_extensive_history(self):
        low_history = svc.assess_rider_risk(_very_safe_profile(
            based_on_valid_shift_count=1, based_on_shift_count=1, confidence=0.09,
        ))
        high_history = svc.assess_rider_risk(_very_safe_profile(
            based_on_valid_shift_count=50, based_on_shift_count=50, confidence=0.97,
        ))
        assert low_history.confidence < high_history.confidence

    def test_never_crashes_on_zero_confidence_or_quality(self):
        result = svc.assess_rider_risk(_very_safe_profile(data_quality_score=0.0, confidence=0.0))
        assert result.risk_score is not None


class TestRiskBandBoundaries:
    @pytest.mark.parametrize("score,expected_band", [
        (0.0, svc.RISK_BAND_VERY_LOW),
        (19.999, svc.RISK_BAND_VERY_LOW),
        (20.0, svc.RISK_BAND_LOW),
        (39.999, svc.RISK_BAND_LOW),
        (40.0, svc.RISK_BAND_MODERATE),
        (59.999, svc.RISK_BAND_MODERATE),
        (60.0, svc.RISK_BAND_HIGH),
        (79.999, svc.RISK_BAND_HIGH),
        (80.0, svc.RISK_BAND_VERY_HIGH),
        (100.0, svc.RISK_BAND_VERY_HIGH),
    ])
    def test_boundary_values(self, score, expected_band):
        assert svc.compute_risk_band(score) == expected_band


class TestScoreBounds:
    def test_score_never_below_zero(self):
        result = svc.assess_rider_risk(_very_safe_profile(
            behaviour_consistency_score=100.0, overall_behaviour_score=100.0,
            based_on_valid_shift_count=100, based_on_shift_count=100,
        ))
        assert result.risk_score >= 0.0

    def test_score_never_above_100(self):
        extreme = _aggressive_profile(
            recent_hard_braking_rate=500.0, recent_hard_acceleration_rate=500.0,
            recent_overspeeding_rate=500.0, recent_sharp_turn_rate=500.0, recent_max_g=50.0,
            behaviour_consistency_score=0.0, overall_behaviour_score=0.0,
        )
        result = svc.assess_rider_risk(extreme)
        assert result.risk_score <= 100.0


class TestDeterminism:
    def test_same_input_produces_same_output(self):
        profile = _aggressive_profile()
        r1 = svc.assess_rider_risk(profile)
        r2 = svc.assess_rider_risk(profile)
        assert r1.risk_score == r2.risk_score
        assert r1.risk_band == r2.risk_band
        assert [c.impact for c in r1.contributors] == [c.impact for c in r2.contributors]


class TestContributorExplanations:
    def test_contributors_sum_to_unclamped_raw_score(self):
        # Pick inputs guaranteed not to hit the final [0,100] clamp, so the
        # contributor sum must equal risk_score exactly.
        profile = _very_safe_profile(
            recent_hard_braking_rate=3.0, recent_overspeeding_rate=2.0,
            behaviour_consistency_score=80.0, overall_behaviour_score=70.0,
        )
        result = svc.assess_rider_risk(profile)
        total_impact = sum(c.impact for c in result.contributors)
        assert result.risk_score == pytest.approx(total_impact, abs=1e-9)

    def test_every_contributor_has_a_valid_direction(self):
        result = svc.assess_rider_risk(_aggressive_profile())
        for c in result.contributors:
            assert c.direction in ("increases_risk", "reduces_risk", "neutral")

    def test_contributors_present_for_every_documented_factor(self):
        result = svc.assess_rider_risk(_aggressive_profile())
        factors = {c.factor for c in result.contributors}
        assert factors == {
            "recent_hard_braking_rate", "recent_hard_acceleration_rate",
            "recent_overspeeding_rate", "recent_sharp_turn_rate", "recent_max_g",
            "behaviour_consistency", "historical_profile_score", "safe_long_term_behaviour",
        }


class TestNoInvalidTelemetryFields:
    def test_only_uses_fields_that_exist_on_rider_behaviour_profile(self):
        from db.models.rider_behaviour_profile import RiderBehaviourProfile
        profile_columns = {c.name for c in RiderBehaviourProfile.__table__.columns}
        used_fields = {
            "recent_hard_braking_rate", "recent_hard_acceleration_rate", "recent_overspeeding_rate",
            "recent_sharp_turn_rate", "recent_max_g", "long_term_hard_braking_rate",
            "long_term_overspeeding_rate", "behaviour_consistency_score", "overall_behaviour_score",
            "data_quality_score", "confidence", "based_on_valid_shift_count", "based_on_shift_count",
        }
        assert used_fields.issubset(profile_columns)


class TestIsolationFromCrashMlEngine:
    def test_service_module_does_not_import_ml_incident_engine(self):
        import ast
        import app.services.behaviour_risk_baseline_service as module

        with open(module.__file__, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        assert not any("ml_incident_engine" in m for m in imported_modules)
        assert not any("ml_scoring_service" in m for m in imported_modules)


class TestDegenerateAllZeroProfile:
    def test_all_zero_valued_profile_does_not_crash(self):
        # The real schema forbids NULLs (all columns NOT NULL with
        # defaults) — this is the schema's actual "degenerate" case: a
        # profile where every field is at its zero-ish default.
        profile = FakeProfile(
            recent_hard_braking_rate=0.0, recent_hard_acceleration_rate=0.0,
            recent_overspeeding_rate=0.0, recent_sharp_turn_rate=0.0, recent_max_g=0.0,
            long_term_hard_braking_rate=0.0, long_term_overspeeding_rate=0.0,
            behaviour_consistency_score=0.0, overall_behaviour_score=0.0,
            data_quality_score=0.0, confidence=0.0,
            based_on_shift_count=0, based_on_valid_shift_count=0,
        )
        result = svc.assess_rider_risk(profile)
        assert result.risk_score is not None
        assert 0.0 <= result.risk_score <= 100.0
        assert result.confidence == 0.0
