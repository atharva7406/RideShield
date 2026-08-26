import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from app.services.window_quality_service import assess_window_quality


def _accel(n, interval_ms=20.0):
    return [{"timestamp": i * interval_ms, "x": 0.1, "y": 0.1, "z": 9.81} for i in range(n)]


def _gyro(n, interval_ms=20.0):
    return [{"timestamp": i * interval_ms, "x": 1.0, "y": 1.0, "z": 1.0} for i in range(n)]


def _gps(n, interval_ms=200.0):
    return [{"timestamp": i * interval_ms, "latitude": 19.07, "longitude": 72.87, "speed": 20.0} for i in range(n)]


class TestWindowQualityService:
    def test_full_50hz_window_with_all_modalities_is_good(self):
        result = assess_window_quality(_accel(150), _gyro(150), _gps(25))
        assert result.quality == "good"
        assert result.reasons == []
        assert result.observed_accel_hz == _approx_50hz()

    def test_fewer_than_3_accel_samples_is_insufficient(self):
        result = assess_window_quality(_accel(2), [], [])
        assert result.quality == "insufficient"
        assert "too_few_accel_samples" in result.reasons

    def test_low_sample_count_is_degraded_not_insufficient(self):
        result = assess_window_quality(_accel(5), _gyro(5), _gps(2))
        assert result.quality == "degraded"
        assert "low_sample_count" in result.reasons

    def test_low_observed_rate_is_degraded(self):
        # 20 samples spread 500ms apart => 2Hz, well under the 20Hz floor
        result = assess_window_quality(_accel(20, interval_ms=500.0), _gyro(20, interval_ms=500.0), _gps(5))
        assert result.quality == "degraded"
        assert "low_sampling_rate" in result.reasons

    def test_missing_gyro_and_gps_are_flagged_but_still_degraded_not_rejected(self):
        result = assess_window_quality(_accel(50), [], [])
        assert result.quality == "degraded"
        assert "missing_gyro" in result.reasons
        assert "missing_gps" in result.reasons
        assert result.accel_sample_count == 50

    def test_non_monotonic_timestamps_are_flagged(self):
        samples = _accel(20)
        samples[5], samples[10] = samples[10], samples[5]  # scramble order
        result = assess_window_quality(samples, _gyro(20), _gps(5))
        assert result.quality == "degraded"
        assert "non_monotonic_timestamps" in result.reasons
        assert result.has_monotonic_timestamps is False

    def test_never_raises_on_degraded_input(self):
        # Duplicate timestamps -> zero span -> rate is None; must not throw.
        samples = [{"timestamp": 100.0, "x": 0, "y": 0, "z": 9.81} for _ in range(10)]
        result = assess_window_quality(samples, [], [])
        assert result.quality == "degraded"
        assert result.observed_accel_hz is None


def _approx_50hz():
    import pytest
    return pytest.approx(50.0, rel=0.05)
