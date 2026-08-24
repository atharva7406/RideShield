import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import pytest

from app.services import ml_scoring_service


def _make_samples(n, x=0.0, y=0.0, z=9.81, dt_ms=20.0):
    return [{"timestamp": i * dt_ms, "x": x, "y": y, "z": z} for i in range(n)]


class TestScoreWindowInputValidation:
    def test_returns_none_for_fewer_than_3_accel_samples(self):
        result = ml_scoring_service.score_window(
            shift_id="s1", accel_samples=_make_samples(2), gyro_samples=[], gps_samples=[],
        )
        assert result is None

    def test_works_with_exactly_3_accel_samples(self):
        result = ml_scoring_service.score_window(
            shift_id="s1", accel_samples=_make_samples(3), gyro_samples=[], gps_samples=[],
        )
        assert result is not None
        assert result["method"] in ("ml", "rule_based_fallback")


class TestScoreWindowOutputShape:
    def test_output_has_expected_keys(self):
        result = ml_scoring_service.score_window(
            shift_id="s1", accel_samples=_make_samples(10), gyro_samples=_make_samples(10), gps_samples=[],
        )
        assert set(result.keys()) == {"method", "peak_g_force", "confidence_score", "predicted_class"}
        assert 0.0 <= result["confidence_score"] <= 1.0
        assert result["peak_g_force"] >= 0.0

    def test_missing_gyro_and_gps_samples_do_not_crash_scoring(self):
        result = ml_scoring_service.score_window(
            shift_id="s1", accel_samples=_make_samples(5), gyro_samples=[], gps_samples=[],
        )
        assert result is not None


class TestRuleBasedFallback:
    def test_forced_fallback_used_when_ml_reports_unavailable(self, monkeypatch):
        monkeypatch.setattr(ml_scoring_service, "is_ml_available", lambda: False)
        # A clear high-G spike, well above the 4.0g rule threshold.
        samples = _make_samples(50, x=0, y=0, z=9.81)
        samples[25] = {"timestamp": 25 * 20.0, "x": 40.0, "y": 0.0, "z": 9.81}
        result = ml_scoring_service.score_window(
            shift_id="s1", accel_samples=samples, gyro_samples=[], gps_samples=[],
        )
        assert result["method"] == "rule_based_fallback"
        assert result["predicted_class"] is None

    def test_fallback_confidence_increases_with_peak_g(self, monkeypatch):
        monkeypatch.setattr(ml_scoring_service, "is_ml_available", lambda: False)

        low_spike = _make_samples(50)
        low_spike[25] = {"timestamp": 25 * 20.0, "x": 20.0, "y": 0.0, "z": 9.81}  # ~2g
        high_spike = _make_samples(50)
        high_spike[25] = {"timestamp": 25 * 20.0, "x": 60.0, "y": 0.0, "z": 9.81}  # ~6g

        low_result = ml_scoring_service.score_window("s1", low_spike, [], [])
        high_result = ml_scoring_service.score_window("s1", high_spike, [], [])

        assert high_result["confidence_score"] > low_result["confidence_score"]

    def test_fallback_confidence_capped_at_0_95(self, monkeypatch):
        monkeypatch.setattr(ml_scoring_service, "is_ml_available", lambda: False)
        samples = _make_samples(10)
        samples[5] = {"timestamp": 100.0, "x": 500.0, "y": 0.0, "z": 9.81}  # absurd spike
        result = ml_scoring_service.score_window("s1", samples, [], [])
        assert result["confidence_score"] <= 0.95

    def test_ml_scoring_exception_falls_back_gracefully(self, monkeypatch):
        # Simulate the model loading fine but throwing during predict —
        # the exact "single point of failure" scenario this exists to
        # protect against.
        monkeypatch.setattr(ml_scoring_service, "is_ml_available", lambda: True)

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated inference failure")

        monkeypatch.setattr(ml_scoring_service, "predict_from_features", _boom)
        result = ml_scoring_service.score_window(
            shift_id="s1", accel_samples=_make_samples(10), gyro_samples=[], gps_samples=[],
        )
        assert result is not None
        assert result["method"] == "rule_based_fallback"


class TestMlPathWhenAvailable:
    def test_uses_ml_when_available(self):
        if not ml_scoring_service.is_ml_available():
            pytest.skip("No trained model artifact present in this environment")
        result = ml_scoring_service.score_window(
            shift_id="s1", accel_samples=_make_samples(20), gyro_samples=_make_samples(20), gps_samples=[],
        )
        assert result["method"] == "ml"
        assert result["predicted_class"] is not None
