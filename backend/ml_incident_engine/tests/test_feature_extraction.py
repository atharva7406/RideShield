"""
Tests for feature_extraction.py.

The `TestComputeFeaturesTsParity` class ports the exact test cases from
rider-app/src/crash-detection/__tests__/featureExtraction.test.ts, with the
same numbers, to verify the Python port behaves identically to the
on-device TS implementation it's meant to mirror.
"""

import numpy as np
import pytest

from ml_incident_engine import config as cfg
from ml_incident_engine.feature_extraction import (
    compute_accel_gyro_correlation,
    compute_duration_abnormal_motion_ms,
    compute_extended_features,
    compute_features_ts_parity,
    compute_jerk_peak,
    compute_post_impact_stillness,
    compute_speed_drop,
    extract_feature_vector,
)
from ml_incident_engine.generate_synthetic_data import generate_event, apply_random_rotation


# ---------------------------------------------------------------------------
# Helpers mirroring the TS test file's accel()/gyro()/gps() fixtures
# ---------------------------------------------------------------------------


def _accel_arrays(magnitudes, timestamps):
    """TS fixture used magnitude directly as gForce too (x=0,y=0,z=magnitude)."""
    mag = np.array(magnitudes, dtype=float)
    t = np.array(timestamps, dtype=float)
    return mag, mag.copy(), t  # accel_mag, accel_gforce, accel_t_ms


def _gyro_array(magnitudes):
    return np.array(magnitudes, dtype=float)


def _gps_arrays(speeds, timestamps):
    return np.array(speeds, dtype=float), np.array(timestamps, dtype=float)


# ---------------------------------------------------------------------------
# TS parity — ported 1:1 from featureExtraction.test.ts
# ---------------------------------------------------------------------------


class TestComputeFeaturesTsParity:
    def test_reports_zeros_for_empty_buffer(self):
        accel_mag, accel_gforce, accel_t = _accel_arrays([], [])
        gyro_mag = _gyro_array([])
        gps_speed, gps_t = _gps_arrays([], [])

        f = compute_features_ts_parity(accel_mag, accel_gforce, accel_t, gyro_mag, gps_speed, gps_t)

        assert f["accel_peak"] == 0
        assert f["accel_magnitude"] == 0
        assert f["speed_drop"] is None
        assert f["post_impact_stillness"] is False

    def test_finds_peak_and_high_peak_to_baseline_ratio_for_a_spike(self):
        accel_mag, accel_gforce, accel_t = _accel_arrays(
            [1.0, 1.0, 1.0, 5.0, 1.0], [0, 20, 40, 60, 80]
        )
        gyro_mag = _gyro_array([])
        gps_speed, gps_t = _gps_arrays([], [])

        f = compute_features_ts_parity(accel_mag, accel_gforce, accel_t, gyro_mag, gps_speed, gps_t)

        assert f["accel_peak"] == 5.0
        assert f["peak_to_baseline_ratio"] > 3

    def test_computes_jerk_as_largest_magnitude_delta_over_time(self):
        accel_mag, accel_gforce, accel_t = _accel_arrays([1.0, 1.0, 5.0], [0, 20, 40])
        # (5.0 - 1.0) / 0.02s = 200
        assert compute_jerk_peak(accel_mag, accel_t) == pytest.approx(200, abs=0.5)

    def test_gyro_variance_roughly_zero_for_constant_signal(self):
        accel_mag, accel_gforce, accel_t = _accel_arrays([], [])
        gyro_mag = _gyro_array([0.5, 0.5, 0.5])
        gps_speed, gps_t = _gps_arrays([], [])

        f = compute_features_ts_parity(accel_mag, accel_gforce, accel_t, gyro_mag, gps_speed, gps_t)
        assert f["gyro_variance"] == pytest.approx(0, abs=1e-5)

    def test_returns_none_speed_drop_with_fewer_than_2_gps_samples(self):
        gps_speed, gps_t = _gps_arrays([10], [0])
        assert compute_speed_drop(gps_speed, gps_t, anchor_timestamp_ms=None) is None

    def test_detects_a_real_speed_drop_within_the_window(self):
        gps_speed, gps_t = _gps_arrays([15, 15, 5, 4], [0, 500, 1000, 1500])
        drop = compute_speed_drop(gps_speed, gps_t, anchor_timestamp_ms=None)
        assert drop == pytest.approx(11, abs=0.5)

    def test_does_not_flag_stillness_without_enough_post_peak_data(self):
        accel_mag, accel_gforce, accel_t = _accel_arrays([1.0, 5.0], [0, 20])  # peak is last sample
        assert compute_post_impact_stillness(accel_mag, accel_t) is False

    def test_flags_stillness_when_post_peak_samples_settle_to_low_variance(self):
        accel_mag, accel_gforce, accel_t = _accel_arrays(
            [1.0, 5.0, 1.0, 1.01, 0.99, 1.0], [0, 100, 300, 500, 700, 900]
        )
        assert compute_post_impact_stillness(accel_mag, accel_t) is True


# ---------------------------------------------------------------------------
# Extension features (no TS equivalent)
# ---------------------------------------------------------------------------


class TestExtendedFeatures:
    def test_duration_abnormal_motion_zero_when_nothing_crosses_threshold(self):
        accel_gforce = np.array([1.0, 1.02, 0.98, 1.01, 1.0])
        accel_t = np.array([0, 20, 40, 60, 80], dtype=float)
        assert compute_duration_abnormal_motion_ms(accel_gforce, accel_t) == 0.0

    def test_duration_abnormal_motion_spans_the_elevated_samples(self):
        # baseline (excluding peak) ~1.0g, threshold 1.5x -> 1.5g
        accel_gforce = np.array([1.0, 1.0, 3.0, 3.0, 3.0, 1.0, 1.0])
        accel_t = np.array([0, 20, 40, 60, 80, 100, 120], dtype=float)
        duration = compute_duration_abnormal_motion_ms(accel_gforce, accel_t)
        assert duration == pytest.approx(40, abs=1)  # samples at t=40..80

    def test_accel_gyro_correlation_none_for_constant_series(self):
        accel_mag = np.array([1.0, 1.0, 1.0, 1.0])
        gyro_mag = np.array([0.5, 0.5, 0.5, 0.5])
        assert compute_accel_gyro_correlation(accel_mag, gyro_mag) is None

    def test_accel_gyro_correlation_positive_for_co_moving_series(self):
        t = np.linspace(0, 1, 50)
        accel_mag = 1.0 + t  # rises linearly
        gyro_mag = 0.5 + 2 * t  # also rises linearly -> perfectly correlated
        corr = compute_accel_gyro_correlation(accel_mag, gyro_mag)
        assert corr is not None
        assert corr == pytest.approx(1.0, abs=1e-6)

    def test_accel_gyro_correlation_none_on_length_mismatch(self):
        assert compute_accel_gyro_correlation(np.array([1.0, 2.0]), np.array([1.0])) is None

    def test_jerk_mean_never_exceeds_jerk_peak(self):
        accel_mag, accel_gforce, accel_t = _accel_arrays([1.0, 2.0, 8.0, 1.5, 1.0], [0, 20, 40, 60, 80])
        gyro_mag = _gyro_array([0.1, 0.2, 0.3, 0.2, 0.1])
        gps_speed, gps_t = _gps_arrays([], [])

        ext = compute_extended_features(
            accel_mag, accel_gforce, accel_t, gyro_mag, gps_speed, gps_t,
            gps_accuracy=np.array([]), accel_peak_timestamp_ms=40.0,
        )
        assert ext["jerk_mean"] <= compute_jerk_peak(accel_mag, accel_t) + 1e-6


# ---------------------------------------------------------------------------
# Orientation invariance (validates the design goal from generate_synthetic_data.py)
# ---------------------------------------------------------------------------


class TestOrientationInvariance:
    def test_rotating_raw_axes_leaves_magnitude_features_unchanged(self):
        rng = np.random.default_rng(123)
        window = generate_event("crash", rng, rider_id="r1", shift_id="s1")
        rotated = apply_random_rotation(window, np.random.default_rng(456))

        f_original = extract_feature_vector(window)
        f_rotated = extract_feature_vector(rotated)

        for key in ("accel_peak", "accel_peak_g", "jerk_peak", "gyro_peak",
                    "gyro_variance", "peak_to_baseline_ratio", "accel_mean", "accel_std"):
            assert f_original[key] == pytest.approx(f_rotated[key], rel=1e-4, abs=1e-4), key


# ---------------------------------------------------------------------------
# Sanity: extract_feature_vector runs end-to-end on every class
# ---------------------------------------------------------------------------


class TestExtractFeatureVectorSmoke:
    @pytest.mark.parametrize("class_label", cfg.EVENT_CLASSES)
    def test_runs_without_error_and_no_nans(self, class_label):
        rng = np.random.default_rng(7)
        window = generate_event(class_label, rng, rider_id="r1", shift_id="s1")
        features = extract_feature_vector(window)

        assert set(features.keys()) == {
            "accel_magnitude", "accel_peak", "accel_peak_g", "jerk_peak",
            "gyro_magnitude", "gyro_peak", "gyro_variance", "peak_to_baseline_ratio",
            "speed_drop", "post_impact_stillness",
            "accel_mean", "accel_std", "jerk_mean", "speed_before", "speed_after",
            "post_impact_accel_variance", "post_impact_gyro_variance",
            "duration_abnormal_motion_ms", "gps_accuracy_mean", "accel_gyro_correlation",
        }
        for key, value in features.items():
            if isinstance(value, float):
                assert np.isfinite(value), f"{key} is not finite: {value}"

    def test_crash_events_have_higher_peak_g_than_normal_on_average(self):
        rng = np.random.default_rng(99)
        crash_peaks = [
            extract_feature_vector(generate_event("crash", rng, rider_id="r", shift_id="s"))["accel_peak_g"]
            for _ in range(30)
        ]
        normal_peaks = [
            extract_feature_vector(generate_event("normal", rng, rider_id="r", shift_id="s"))["accel_peak_g"]
            for _ in range(30)
        ]
        assert np.mean(crash_peaks) > np.mean(normal_peaks)

    def test_crash_events_more_often_show_post_impact_stillness_than_pothole(self):
        rng = np.random.default_rng(101)
        crash_still = [
            extract_feature_vector(generate_event("crash", rng, rider_id="r", shift_id="s"))["post_impact_stillness"]
            for _ in range(40)
        ]
        pothole_still = [
            extract_feature_vector(generate_event("pothole", rng, rider_id="r", shift_id="s"))["post_impact_stillness"]
            for _ in range(40)
        ]
        assert sum(crash_still) > sum(pothole_still)


class TestStillnessIsNotALabelLeak:
    """Regression guard for the "post_impact_stillness = crash" shortcut a
    model could otherwise learn instead of the intended multi-signal
    pattern: crash must show a high stillness rate, but never anywhere
    near 100% (a real crash doesn't always settle), and the other classes
    must stay low but not hard-zero (a stop/quiet patch can occasionally
    happen for any of them). Bounds are deliberately generous — this test
    exists to catch a full regression back to "always" or "never", not to
    pin exact probabilities."""

    N = 300

    @staticmethod
    def _stillness_rate(class_label: str, seed: int) -> float:
        rng = np.random.default_rng(seed)
        results = [
            extract_feature_vector(
                generate_event(class_label, rng, rider_id="r", shift_id="s")
            )["post_impact_stillness"]
            for _ in range(TestStillnessIsNotALabelLeak.N)
        ]
        return sum(results) / len(results)

    def test_crash_stillness_rate_is_high_but_not_saturated(self):
        rate = self._stillness_rate("crash", seed=2024)
        assert 0.5 < rate < 0.95, f"crash stillness rate {rate} is out of the intended non-trivial range"

    @pytest.mark.parametrize("class_label", ["normal", "hard_braking", "pothole", "sharp_turn"])
    def test_non_crash_classes_stay_low_but_nonzero_capable(self, class_label):
        rate = self._stillness_rate(class_label, seed=99)
        assert rate < 0.35, f"{class_label} stillness rate {rate} is too close to crash's — no longer a hard negative"
