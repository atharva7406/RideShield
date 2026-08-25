import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.services import rider_behaviour_profile_service as svc


@dataclass
class FakeSummary:
    created_at: datetime
    is_valid: bool = True
    average_speed: float = 30.0
    max_speed: float = 40.0
    hard_braking_rate: float = 2.0
    hard_acceleration_rate: float = 2.0
    overspeeding_rate: float = 1.0
    sharp_turn_rate: float = 1.0
    max_g: float = 1.5
    data_quality_score: float = 0.9


BASE_T = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _t(days_ago: float) -> datetime:
    return BASE_T - timedelta(days=days_ago)


def _safe_summary(days_ago: float) -> FakeSummary:
    return FakeSummary(
        created_at=_t(days_ago), hard_braking_rate=0.5, hard_acceleration_rate=0.5,
        overspeeding_rate=0.0, sharp_turn_rate=0.5, max_g=1.2, data_quality_score=0.95,
    )


def _aggressive_summary(days_ago: float) -> FakeSummary:
    return FakeSummary(
        created_at=_t(days_ago), hard_braking_rate=15.0, hard_acceleration_rate=12.0,
        overspeeding_rate=10.0, sharp_turn_rate=8.0, max_g=4.5, data_quality_score=0.9,
    )


class TestComputeTierAggregate:
    def test_empty_returns_zeroed_aggregate(self):
        agg = svc.compute_tier_aggregate([])
        assert agg.shift_count == 0
        assert agg.avg_speed == 0.0

    def test_known_average_of_two_shifts(self):
        summaries = [FakeSummary(_t(0), average_speed=20.0), FakeSummary(_t(1), average_speed=40.0)]
        agg = svc.compute_tier_aggregate(summaries)
        assert agg.avg_speed == pytest.approx(30.0)
        assert agg.shift_count == 2

    def test_max_speed_and_max_g_take_the_maximum_not_average(self):
        summaries = [FakeSummary(_t(0), max_speed=50.0, max_g=2.0), FakeSummary(_t(1), max_speed=80.0, max_g=5.0)]
        agg = svc.compute_tier_aggregate(summaries)
        assert agg.max_speed == 80.0
        assert agg.max_g == 5.0


class TestComputeConsistency:
    def test_fewer_than_2_summaries_returns_default(self):
        result = svc.compute_consistency([FakeSummary(_t(0))])
        assert result.consistency_score == 0.0

    def test_stable_rider_has_high_consistency(self):
        summaries = [FakeSummary(_t(i), hard_braking_rate=2.0, overspeeding_rate=1.0, average_speed=30.0)
                     for i in range(6)]
        result = svc.compute_consistency(summaries)
        assert result.consistency_score > 95.0  # near-perfectly steady

    def test_volatile_rider_has_lower_consistency_than_stable_rider(self):
        stable = [FakeSummary(_t(i), hard_braking_rate=2.0, overspeeding_rate=1.0, average_speed=30.0)
                  for i in range(6)]
        volatile = [
            FakeSummary(_t(0), hard_braking_rate=0.0, overspeeding_rate=0.0, average_speed=10.0),
            FakeSummary(_t(1), hard_braking_rate=20.0, overspeeding_rate=15.0, average_speed=60.0),
            FakeSummary(_t(2), hard_braking_rate=1.0, overspeeding_rate=0.0, average_speed=15.0),
            FakeSummary(_t(3), hard_braking_rate=25.0, overspeeding_rate=18.0, average_speed=55.0),
            FakeSummary(_t(4), hard_braking_rate=0.5, overspeeding_rate=0.0, average_speed=12.0),
            FakeSummary(_t(5), hard_braking_rate=22.0, overspeeding_rate=20.0, average_speed=58.0),
        ]
        stable_result = svc.compute_consistency(stable)
        volatile_result = svc.compute_consistency(volatile)
        assert stable_result.consistency_score > volatile_result.consistency_score

    def test_consistency_score_bounded_0_to_100(self):
        wild = [
            FakeSummary(_t(0), hard_braking_rate=0.0, overspeeding_rate=0.0),
            FakeSummary(_t(1), hard_braking_rate=1000.0, overspeeding_rate=1000.0),
        ]
        result = svc.compute_consistency(wild)
        assert 0.0 <= result.consistency_score <= 100.0

    def test_all_zero_rates_are_perfectly_consistent(self):
        summaries = [FakeSummary(_t(i), hard_braking_rate=0.0, overspeeding_rate=0.0, average_speed=0.0)
                     for i in range(4)]
        result = svc.compute_consistency(summaries)
        assert result.consistency_score == pytest.approx(100.0)


class TestComputeOverallBehaviourScore:
    def test_safe_behaviour_scores_higher_than_aggressive(self):
        safe = [_safe_summary(i) for i in range(6)]
        aggressive = [_aggressive_summary(i) for i in range(6)]

        safe_snapshot = svc.build_rider_profile_snapshot(safe, len(safe))
        aggressive_snapshot = svc.build_rider_profile_snapshot(aggressive, len(aggressive))

        assert safe_snapshot.overall_behaviour_score > aggressive_snapshot.overall_behaviour_score

    def test_score_bounded_0_to_100_even_for_extreme_input(self):
        extreme = [FakeSummary(_t(i), hard_braking_rate=500.0, hard_acceleration_rate=500.0,
                                overspeeding_rate=500.0, sharp_turn_rate=500.0, max_g=50.0)
                   for i in range(3)]
        snapshot = svc.build_rider_profile_snapshot(extreme, len(extreme))
        assert 0.0 <= snapshot.overall_behaviour_score <= 100.0

    def test_deterministic_same_input_same_output(self):
        summaries = [_aggressive_summary(i) for i in range(4)]
        s1 = svc.build_rider_profile_snapshot(list(summaries), len(summaries), computed_at=BASE_T)
        s2 = svc.build_rider_profile_snapshot(list(summaries), len(summaries), computed_at=BASE_T)
        assert s1.overall_behaviour_score == s2.overall_behaviour_score
        assert s1.confidence == s2.confidence

    def test_no_data_returns_neutral_baseline(self):
        empty_recent = svc.TierAggregate(shift_count=0)
        empty_medium = svc.TierAggregate(shift_count=0)
        empty_long = svc.TierAggregate(shift_count=0)
        score = svc.compute_overall_behaviour_score(empty_recent, empty_medium, empty_long, svc.ConsistencyResult())
        assert score == svc.BASELINE_SCORE

    def test_recent_behaviour_influences_score_more_than_a_flat_average_would(self):
        # 5 recent aggressive shifts, then a long tail of safe history —
        # recent should pull the score down more than a naive flat average
        # over all shifts would.
        recent_aggressive = [_aggressive_summary(i) for i in range(5)]
        old_safe = [_safe_summary(i) for i in range(20, 40)]
        mixed = recent_aggressive + old_safe

        snapshot = svc.build_rider_profile_snapshot(mixed, len(mixed))

        # A flat (unweighted) average over ALL shifts as a baseline comparison.
        flat_agg = svc.compute_tier_aggregate(mixed)
        flat_consistency = svc.compute_consistency(mixed)
        flat_score = svc.compute_overall_behaviour_score(flat_agg, flat_agg, flat_agg, flat_consistency)

        assert snapshot.overall_behaviour_score < flat_score

    def test_old_behaviour_still_contributes_not_ignored(self):
        # All-recent-safe, but long history of aggressive behaviour should
        # still drag the score down some relative to an all-safe rider.
        recent_safe = [_safe_summary(i) for i in range(5)]
        old_aggressive = [_aggressive_summary(i) for i in range(20, 40)]
        mixed = recent_safe + old_aggressive
        mixed_snapshot = svc.build_rider_profile_snapshot(mixed, len(mixed))

        all_safe = [_safe_summary(i) for i in range(25)]
        all_safe_snapshot = svc.build_rider_profile_snapshot(all_safe, len(all_safe))

        assert mixed_snapshot.overall_behaviour_score < all_safe_snapshot.overall_behaviour_score


class TestComputeConfidence:
    def test_zero_valid_shifts_gives_zero_confidence(self):
        assert svc.compute_confidence(0, 1.0) == 0.0

    def test_confidence_increases_with_shift_count_up_to_saturation(self):
        low = svc.compute_confidence(1, 1.0)
        mid = svc.compute_confidence(5, 1.0)
        saturated = svc.compute_confidence(svc.CONFIDENCE_SATURATION_SHIFT_COUNT, 1.0)
        beyond = svc.compute_confidence(svc.CONFIDENCE_SATURATION_SHIFT_COUNT * 3, 1.0)

        assert low < mid < saturated
        assert saturated == pytest.approx(beyond)  # saturates, doesn't keep growing

    def test_poor_data_quality_reduces_confidence(self):
        good_quality = svc.compute_confidence(10, 0.95)
        poor_quality = svc.compute_confidence(10, 0.35)
        assert poor_quality < good_quality

    def test_confidence_bounded_0_to_1(self):
        assert 0.0 <= svc.compute_confidence(1000, 1.0) <= 1.0
        assert 0.0 <= svc.compute_confidence(0, 0.0) <= 1.0


class TestBuildRiderProfileSnapshot:
    def test_empty_history_returns_none(self):
        assert svc.build_rider_profile_snapshot([], 0) is None

    def test_single_valid_shift_produces_a_profile(self):
        summaries = [_safe_summary(0)]
        snapshot = svc.build_rider_profile_snapshot(summaries, based_on_shift_count=1)
        assert snapshot is not None
        assert snapshot.based_on_valid_shift_count == 1
        assert snapshot.recent.shift_count == 1
        assert snapshot.medium.shift_count == 1
        assert snapshot.long_term.shift_count == 1
        # Degenerate windows -> all three tiers equal the single shift's own values.
        assert snapshot.recent.hard_braking_rate == snapshot.long_term.hard_braking_rate

    def test_recent_window_caps_at_configured_size(self):
        summaries = [_safe_summary(i) for i in range(30)]
        snapshot = svc.build_rider_profile_snapshot(summaries, based_on_shift_count=30)
        assert snapshot.recent.shift_count == svc.RECENT_WINDOW_SHIFT_COUNT
        assert snapshot.medium.shift_count == svc.MEDIUM_WINDOW_SHIFT_COUNT

    def test_based_on_shift_count_can_exceed_valid_count(self):
        summaries = [_safe_summary(i) for i in range(3)]
        snapshot = svc.build_rider_profile_snapshot(summaries, based_on_shift_count=10)  # 7 invalid, excluded upstream
        assert snapshot.based_on_shift_count == 10
        assert snapshot.based_on_valid_shift_count == 3

    def test_low_quality_shifts_lower_overall_data_quality_and_confidence(self):
        high_quality = [_safe_summary(i) for i in range(6)]
        for s in high_quality:
            s.data_quality_score = 0.95

        mixed_quality = [_safe_summary(i) for i in range(6)]
        for i, s in enumerate(mixed_quality):
            s.data_quality_score = 0.35 if i < 3 else 0.95

        high_snapshot = svc.build_rider_profile_snapshot(high_quality, 6)
        mixed_snapshot = svc.build_rider_profile_snapshot(mixed_quality, 6)

        assert mixed_snapshot.data_quality_score < high_snapshot.data_quality_score
        assert mixed_snapshot.confidence < high_snapshot.confidence
