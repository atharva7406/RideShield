import numpy as np
import pytest

from behaviour_risk_engine import calibration as calib


def _synthetic_biased_predictions(n=80, seed=1):
    """raw predictions systematically UNDER-predict true values at the
    high end — a realistic miscalibration shape isotonic regression
    should be able to correct."""
    rng = np.random.default_rng(seed)
    true = rng.uniform(0, 100, n)
    bias = np.where(true > 70, -8.0, 0.0)  # underprediction concentrated above 70
    raw = np.clip(true + bias + rng.normal(0, 3, n), 0, 100)
    return raw, true


class TestFitIsotonicCalibration:
    def test_fit_returns_a_fitted_estimator(self):
        raw, true = _synthetic_biased_predictions()
        iso = calib.fit_isotonic_calibration(raw, true)
        assert hasattr(iso, "X_thresholds_")
        assert hasattr(iso, "y_thresholds_")

    def test_calibration_corrects_the_known_bias(self):
        raw, true = _synthetic_biased_predictions(n=300, seed=2)
        iso = calib.fit_isotonic_calibration(raw, true)
        breakpoints = calib.calibration_breakpoints(iso)

        high_band_mask = true > 70
        raw_error = np.abs(raw[high_band_mask] - true[high_band_mask]).mean()
        calibrated = np.array([calib.apply_calibration(r, breakpoints) for r in raw[high_band_mask]])
        calibrated_error = np.abs(calibrated - true[high_band_mask]).mean()

        assert calibrated_error < raw_error


class TestApplyCalibrationMatchesSklearn:
    def test_np_interp_reproduces_isotonic_predict_exactly(self):
        raw, true = _synthetic_biased_predictions(n=200, seed=3)
        iso = calib.fit_isotonic_calibration(raw, true)
        breakpoints = calib.calibration_breakpoints(iso)

        sample_x = np.linspace(0, 100, 51)
        sklearn_pred = iso.predict(sample_x)
        interp_pred = np.array([calib.apply_calibration(x, breakpoints) for x in sample_x])

        np.testing.assert_allclose(sklearn_pred, interp_pred, atol=1e-8)

    def test_out_of_range_inputs_clip_same_as_sklearn(self):
        raw, true = _synthetic_biased_predictions(n=100, seed=4)
        iso = calib.fit_isotonic_calibration(raw, true)
        breakpoints = calib.calibration_breakpoints(iso)

        for extreme in (-50.0, 150.0, -1000.0, 1000.0):
            sklearn_val = float(iso.predict([extreme])[0])
            interp_val = calib.apply_calibration(extreme, breakpoints)
            assert interp_val == pytest.approx(sklearn_val, abs=1e-6)


class TestApplyCalibrationBounds:
    def test_output_always_clamped_to_0_100(self):
        raw, true = _synthetic_biased_predictions(n=100, seed=5)
        iso = calib.fit_isotonic_calibration(raw, true)
        breakpoints = calib.calibration_breakpoints(iso)
        for x in (-1e9, 0.0, 50.0, 100.0, 1e9):
            result = calib.apply_calibration(x, breakpoints)
            assert 0.0 <= result <= 100.0

    def test_boundary_zero_and_hundred(self):
        raw, true = _synthetic_biased_predictions(n=150, seed=6)
        iso = calib.fit_isotonic_calibration(raw, true)
        breakpoints = calib.calibration_breakpoints(iso)
        assert 0.0 <= calib.apply_calibration(0.0, breakpoints) <= 100.0
        assert 0.0 <= calib.apply_calibration(100.0, breakpoints) <= 100.0


class TestSaveLoadRoundTrip:
    def test_round_trip_preserves_predictions(self, tmp_path):
        raw, true = _synthetic_biased_predictions(n=100, seed=7)
        iso = calib.fit_isotonic_calibration(raw, true)
        breakpoints = calib.calibration_breakpoints(iso)

        path = tmp_path / "cal.json"
        calib.save_calibration(breakpoints, path)
        loaded = calib.load_calibration(path)

        for x in np.linspace(0, 100, 11):
            assert calib.apply_calibration(x, breakpoints) == pytest.approx(
                calib.apply_calibration(x, loaded), abs=1e-9
            )

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(Exception):
            calib.load_calibration(tmp_path / "does_not_exist.json")

    def test_malformed_file_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text('{"not_the_right_keys": true}')
        with pytest.raises(ValueError):
            calib.load_calibration(path)

    def test_mismatched_array_lengths_raise(self, tmp_path):
        import json
        path = tmp_path / "bad2.json"
        path.write_text(json.dumps({"x_thresholds": [1, 2, 3], "y_thresholds": [1, 2]}))
        with pytest.raises(ValueError):
            calib.load_calibration(path)


class TestDeterminism:
    def test_same_input_same_output(self):
        raw, true = _synthetic_biased_predictions(n=100, seed=8)
        iso = calib.fit_isotonic_calibration(raw, true)
        breakpoints = calib.calibration_breakpoints(iso)
        for x in (12.3, 45.6, 78.9):
            r1 = calib.apply_calibration(x, breakpoints)
            r2 = calib.apply_calibration(x, breakpoints)
            assert r1 == r2
