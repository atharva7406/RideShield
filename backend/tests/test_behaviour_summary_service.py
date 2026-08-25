import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.services import behaviour_summary_service, distance_service


@dataclass
class FakeSample:
    timestamp: datetime
    latitude: Optional[float] = 19.0760
    longitude: Optional[float] = 72.8777
    gps_accuracy: Optional[float] = 5.0
    speed: Optional[float] = 30.0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 9.81  # ~1g resting
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0


BASE_T = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _t(seconds: float) -> datetime:
    return BASE_T + timedelta(seconds=seconds)


def _normal_samples(n=20, dt=1.0, speed=30.0):
    return [FakeSample(_t(i * dt), speed=speed) for i in range(n)]


class TestComputeBehaviourMetrics:
    def test_empty_samples_returns_zeroed_metrics(self):
        m = behaviour_summary_service.compute_behaviour_metrics([])
        assert m.sample_count == 0
        assert m.hard_braking_count == 0
        assert m.hard_acceleration_count == 0
        assert m.overspeeding_count == 0
        assert m.sharp_turn_count == 0
        assert m.max_g == 0.0

    def test_sample_count_matches_input(self):
        m = behaviour_summary_service.compute_behaviour_metrics(_normal_samples(15))
        assert m.sample_count == 15

    def test_hard_acceleration_counted_by_threshold(self):
        samples = _normal_samples(5)
        # g = accel_magnitude / 9.81; want g > HARD_ACCEL_G_THRESHOLD (1.8)
        samples[2].accel_z = behaviour_summary_service.HARD_ACCEL_G_THRESHOLD * behaviour_summary_service.GRAVITY_MS2 * 1.2
        m = behaviour_summary_service.compute_behaviour_metrics(samples)
        assert m.hard_acceleration_count == 1

    def test_hard_braking_counted_by_threshold(self):
        samples = _normal_samples(5)
        # g < HARD_BRAKING_G_THRESHOLD (0.5) — near-zero total accel magnitude
        samples[2].accel_x = 0.0
        samples[2].accel_y = 0.0
        samples[2].accel_z = behaviour_summary_service.HARD_BRAKING_G_THRESHOLD * behaviour_summary_service.GRAVITY_MS2 * 0.5
        m = behaviour_summary_service.compute_behaviour_metrics(samples)
        assert m.hard_braking_count == 1

    def test_overspeeding_counted_by_threshold(self):
        samples = _normal_samples(5, speed=30.0)
        samples[3].speed = behaviour_summary_service.OVERSPEED_KMH_THRESHOLD + 10.0
        m = behaviour_summary_service.compute_behaviour_metrics(samples)
        assert m.overspeeding_count == 1

    def test_overspeeding_ignores_none_speed(self):
        samples = _normal_samples(5, speed=30.0)
        samples[3].speed = None
        m = behaviour_summary_service.compute_behaviour_metrics(samples)
        assert m.overspeeding_count == 0  # None speed never counts

    def test_sharp_turn_counted_by_gyro_threshold(self):
        samples = _normal_samples(5)
        samples[1].gyro_z = behaviour_summary_service.SHARP_TURN_GYRO_THRESHOLD_DEG_S * 1.5
        m = behaviour_summary_service.compute_behaviour_metrics(samples)
        assert m.sharp_turn_count == 1

    def test_average_and_max_speed(self):
        samples = [FakeSample(_t(i), speed=s) for i, s in enumerate([10.0, 20.0, 30.0, 40.0])]
        m = behaviour_summary_service.compute_behaviour_metrics(samples)
        assert m.average_speed == pytest.approx(25.0)
        assert m.max_speed == pytest.approx(40.0)

    def test_max_g_reflects_true_peak(self):
        samples = _normal_samples(5)
        samples[2].accel_z = 5 * behaviour_summary_service.GRAVITY_MS2  # ~5g spike
        m = behaviour_summary_service.compute_behaviour_metrics(samples)
        assert m.max_g == pytest.approx(5.0, abs=0.01)

    def test_accel_std_zero_for_constant_signal(self):
        m = behaviour_summary_service.compute_behaviour_metrics(_normal_samples(10))
        assert m.accel_std == pytest.approx(0.0, abs=1e-6)

    def test_metrics_are_order_independent_except_jerk(self):
        samples = _normal_samples(10)
        shuffled = list(reversed(samples))
        m1 = behaviour_summary_service.compute_behaviour_metrics(samples)
        m2 = behaviour_summary_service.compute_behaviour_metrics(shuffled)
        assert m1.hard_braking_count == m2.hard_braking_count
        assert m1.max_g == m2.max_g
        assert m1.average_speed == m2.average_speed


class TestComputeHourlyRate:
    def test_zero_duration_returns_zero(self):
        assert behaviour_summary_service.compute_hourly_rate(5, 0.0) == 0.0

    def test_negative_duration_returns_zero(self):
        assert behaviour_summary_service.compute_hourly_rate(5, -10.0) == 0.0

    def test_known_rate_scaling(self):
        # 3 events in 30 minutes (1800s) -> 6 events/hour
        rate = behaviour_summary_service.compute_hourly_rate(3, 1800.0)
        assert rate == pytest.approx(6.0)

    def test_zero_events_gives_zero_rate(self):
        assert behaviour_summary_service.compute_hourly_rate(0, 3600.0) == 0.0


class TestComputeDataQuality:
    def test_zero_duration_or_no_samples_gives_zero_score(self):
        result = behaviour_summary_service.compute_data_quality([], 0.0, distance_service.compute_distance_km([]))
        assert result.score == 0.0

    def test_dense_good_gps_samples_score_highly(self):
        # ~1 sample/sec matching EXPECTED_SAMPLES_PER_SECOND, full duration span, good accuracy.
        duration = 60.0
        samples = _normal_samples(n=60, dt=1.0)
        dist_result = distance_service.compute_distance_km(samples)
        result = behaviour_summary_service.compute_data_quality(samples, duration, dist_result)
        assert result.score > 0.8

    def test_sparse_samples_score_lower_on_density(self):
        duration = 300.0  # 5 minutes
        samples = _normal_samples(n=5, dt=60.0)  # only 5 samples across 5 minutes
        dist_result = distance_service.compute_distance_km(samples)
        result = behaviour_summary_service.compute_data_quality(samples, duration, dist_result)
        assert result.sampling_density_score < 0.5

    def test_poor_gps_accuracy_lowers_accuracy_score(self):
        duration = 20.0
        samples = [FakeSample(_t(i), gps_accuracy=500.0) for i in range(20)]
        dist_result = distance_service.compute_distance_km(samples)
        result = behaviour_summary_service.compute_data_quality(samples, duration, dist_result)
        assert result.gps_accuracy_score < 0.5

    def test_missing_gps_lowers_validity_score(self):
        duration = 20.0
        samples = [FakeSample(_t(i), latitude=None, longitude=None) for i in range(20)]
        dist_result = distance_service.compute_distance_km(samples)
        result = behaviour_summary_service.compute_data_quality(samples, duration, dist_result)
        assert result.gps_validity_score == pytest.approx(0.0)

    def test_score_always_bounded_0_to_1(self):
        duration = 20.0
        samples = _normal_samples(n=200, dt=0.1)  # denser than "expected" — must still clamp to 1.0 max
        dist_result = distance_service.compute_distance_km(samples)
        result = behaviour_summary_service.compute_data_quality(samples, duration, dist_result)
        assert 0.0 <= result.score <= 1.0
        assert 0.0 <= result.sampling_density_score <= 1.0

    def test_short_telemetry_span_lowers_duration_coverage(self):
        duration = 600.0  # shift lasted 10 minutes
        samples = _normal_samples(n=10, dt=1.0)  # but telemetry only spans ~10 seconds of it
        dist_result = distance_service.compute_distance_km(samples)
        result = behaviour_summary_service.compute_data_quality(samples, duration, dist_result)
        assert result.duration_coverage_score < 0.1


class TestIsSummaryValid:
    def test_valid_when_above_both_thresholds(self):
        assert behaviour_summary_service.is_summary_valid(
            behaviour_summary_service.MIN_SAMPLE_COUNT_FOR_VALID + 5,
            behaviour_summary_service.MIN_DATA_QUALITY_SCORE_FOR_VALID + 0.2,
        ) is True

    def test_invalid_when_too_few_samples(self):
        assert behaviour_summary_service.is_summary_valid(
            behaviour_summary_service.MIN_SAMPLE_COUNT_FOR_VALID - 1,
            1.0,
        ) is False

    def test_invalid_when_quality_score_too_low(self):
        assert behaviour_summary_service.is_summary_valid(
            100,
            behaviour_summary_service.MIN_DATA_QUALITY_SCORE_FOR_VALID - 0.01,
        ) is False

    def test_incomplete_telemetry_is_flagged_invalid_end_to_end(self):
        # Very sparse, short telemetry — should fail validity even though
        # it "computes" without error.
        duration = 3600.0  # rider claims a 1-hour shift
        samples = _normal_samples(n=2, dt=1.0)  # but only 2 samples exist
        dist_result = distance_service.compute_distance_km(samples)
        quality = behaviour_summary_service.compute_data_quality(samples, duration, dist_result)
        metrics = behaviour_summary_service.compute_behaviour_metrics(samples)
        assert behaviour_summary_service.is_summary_valid(metrics.sample_count, quality.score) is False
