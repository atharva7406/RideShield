import numpy as np
import pytest

from behaviour_risk_engine import calibrate_and_evaluate
from behaviour_risk_engine import calibration as calib
from behaviour_risk_engine import config as cfg
from behaviour_risk_engine import model_config as mcfg
from behaviour_risk_engine.dataset import build_and_save
from behaviour_risk_engine.predict import (
    load_calibration_breakpoints,
    predict_calibrated_from_features,
    predict_from_features,
)
from behaviour_risk_engine.train_model import train_baseline


@pytest.fixture(scope="module")
def trained_with_data(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("phase5_smoke")
    build_and_save(output_dir=out_dir, n_riders=300, seed=888)

    # train_baseline() always saves to mcfg.MODEL_PATH regardless of
    # artifacts_dir (that's existing Phase 4 behaviour, unchanged here) —
    # point it at out_dir for the duration of this fixture so the trained
    # model and the dataset splits live in the same temp directory that
    # calibrate_and_evaluate.run(artifacts_dir=out_dir) will read from.
    original_rounds, original_stop = mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS
    original_model_path = mcfg.MODEL_PATH
    mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS = 80, 15
    mcfg.MODEL_PATH = out_dir / "behaviour_risk_xgboost_model.json"
    try:
        result = train_baseline(artifacts_dir=out_dir)
    finally:
        mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS = original_rounds, original_stop
        mcfg.MODEL_PATH = original_model_path
    return out_dir, result


class TestCalibrateAndEvaluateRun:
    def test_run_completes_and_returns_expected_keys(self, trained_with_data, monkeypatch):
        out_dir, _ = trained_with_data
        monkeypatch.setattr(mcfg, "MODEL_PATH", out_dir / "behaviour_risk_xgboost_model.json")
        monkeypatch.setattr(mcfg, "CALIBRATION_PATH", out_dir / "calibration.json")

        result = calibrate_and_evaluate.run(artifacts_dir=out_dir)

        assert "raw_metrics" in result
        assert "calibrated_metrics" in result
        assert "deploy_calibration" in result
        assert result["np_interp_vs_sklearn_max_diff"] < 1e-6

    def test_deploy_decision_is_written_to_disk_only_when_true(self, trained_with_data, monkeypatch, tmp_path):
        out_dir, _ = trained_with_data
        cal_path = tmp_path / "cal_decision.json"
        monkeypatch.setattr(mcfg, "MODEL_PATH", out_dir / "behaviour_risk_xgboost_model.json")
        monkeypatch.setattr(mcfg, "CALIBRATION_PATH", cal_path)

        result = calibrate_and_evaluate.run(artifacts_dir=out_dir)

        assert cal_path.exists() == result["deploy_calibration"]

    def test_stale_artifact_removed_when_calibration_rejected(self, trained_with_data, monkeypatch, tmp_path):
        out_dir, _ = trained_with_data
        cal_path = tmp_path / "stale_cal.json"
        # Plant a stale prior artifact.
        calib.save_calibration({"x_thresholds": [0.0, 100.0], "y_thresholds": [0.0, 100.0]}, cal_path)
        monkeypatch.setattr(mcfg, "MODEL_PATH", out_dir / "behaviour_risk_xgboost_model.json")
        monkeypatch.setattr(mcfg, "CALIBRATION_PATH", cal_path)

        result = calibrate_and_evaluate.run(artifacts_dir=out_dir)
        if not result["deploy_calibration"]:
            assert not cal_path.exists()


class TestPredictCalibratedFromFeatures:
    def test_no_calibration_artifact_degrades_to_raw(self, trained_with_data, tmp_path):
        out_dir, result = trained_with_data
        booster = result["booster"]
        features = {name: 5.0 for name in cfg.FEATURE_NAMES}

        raw_result = predict_from_features(features, booster=booster)
        calibrated_result = predict_calibrated_from_features(
            features, booster=booster, calibration_path=tmp_path / "does_not_exist.json"
        )

        assert calibrated_result["is_calibrated"] is False
        assert calibrated_result["risk_score"] == pytest.approx(raw_result["risk_score"])
        assert calibrated_result["model_version"] == mcfg.MODEL_VERSION  # NOT the "-calibrated" version

    def test_valid_calibration_artifact_is_applied(self, trained_with_data, tmp_path):
        out_dir, result = trained_with_data
        booster = result["booster"]
        cal_path = tmp_path / "valid_cal.json"
        # A deliberately non-identity calibration so we can prove it's actually applied.
        calib.save_calibration({"x_thresholds": [0.0, 50.0, 100.0], "y_thresholds": [10.0, 50.0, 90.0]}, cal_path)

        features = {name: 0.0 for name in cfg.FEATURE_NAMES}
        raw_result = predict_from_features(features, booster=booster)
        calibrated_result = predict_calibrated_from_features(features, booster=booster, calibration_path=cal_path)

        assert calibrated_result["is_calibrated"] is True
        assert calibrated_result["model_version"] == mcfg.CALIBRATED_MODEL_VERSION
        # With this breakpoint set, a raw score near 0 should calibrate toward 10, not equal raw.
        if raw_result["risk_score"] < 5.0:
            assert calibrated_result["risk_score"] != pytest.approx(raw_result["risk_score"])

    def test_corrupted_calibration_file_degrades_to_raw_not_exception(self, trained_with_data, tmp_path):
        out_dir, result = trained_with_data
        booster = result["booster"]
        cal_path = tmp_path / "corrupted.json"
        cal_path.write_text("not valid json {{{")

        features = {name: 5.0 for name in cfg.FEATURE_NAMES}
        calibrated_result = predict_calibrated_from_features(features, booster=booster, calibration_path=cal_path)
        assert calibrated_result["is_calibrated"] is False  # degraded gracefully, did not raise

    def test_output_clamped_to_0_100(self, trained_with_data, tmp_path):
        out_dir, result = trained_with_data
        booster = result["booster"]
        cal_path = tmp_path / "extreme_cal.json"
        calib.save_calibration({"x_thresholds": [0.0, 100.0], "y_thresholds": [0.0, 100.0]}, cal_path)

        extreme_features = {name: 1e6 for name in cfg.FEATURE_NAMES}
        calibrated_result = predict_calibrated_from_features(extreme_features, booster=booster, calibration_path=cal_path)
        assert 0.0 <= calibrated_result["risk_score"] <= 100.0

    def test_deterministic(self, trained_with_data, tmp_path):
        out_dir, result = trained_with_data
        booster = result["booster"]
        cal_path = tmp_path / "det_cal.json"
        calib.save_calibration({"x_thresholds": [0.0, 50.0, 100.0], "y_thresholds": [5.0, 55.0, 95.0]}, cal_path)

        features = {name: 3.0 for name in cfg.FEATURE_NAMES}
        r1 = predict_calibrated_from_features(features, booster=booster, calibration_path=cal_path)
        r2 = predict_calibrated_from_features(features, booster=booster, calibration_path=cal_path)
        assert r1["risk_score"] == r2["risk_score"]
