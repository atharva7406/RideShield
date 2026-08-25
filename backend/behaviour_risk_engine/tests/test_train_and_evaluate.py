import numpy as np
import pytest
import xgboost as xgb

from behaviour_risk_engine import config as cfg
from behaviour_risk_engine import model_config as mcfg
from behaviour_risk_engine.dataset import build_and_save
from behaviour_risk_engine.evaluate_model import (
    _reliability_bins,
    _regression_metrics,
    _row_to_fake_profile,
    compute_baseline_predictions,
    compute_xgboost_predictions,
    evaluate,
)
from behaviour_risk_engine.predict import load_booster, predict_from_features
from behaviour_risk_engine.train_model import prepare_matrix, train_baseline


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("phase4_smoke")
    build_and_save(output_dir=out_dir, n_riders=250, seed=777)

    original_rounds, original_stop = mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS
    mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS = 60, 10
    try:
        result = train_baseline(artifacts_dir=out_dir)
    finally:
        mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS = original_rounds, original_stop
    return result


class TestPrepareMatrix:
    def test_shapes_and_dtypes(self, trained):
        assert trained["X_train"].shape[1] == len(cfg.FEATURE_NAMES)
        assert trained["X_train"].dtype == np.float64
        assert trained["y_train"].min() >= 0.0
        assert trained["y_train"].max() <= 100.0


class TestTrainingSmoke:
    def test_training_runs_and_saves_a_model(self, trained):
        booster = trained["booster"]
        assert booster.best_iteration >= 0

    def test_deterministic_training_with_fixed_seed(self, tmp_path):
        build_and_save(output_dir=tmp_path, n_riders=120, seed=55)
        original_rounds, original_stop = mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS
        mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS = 30, 8
        try:
            r1 = train_baseline(artifacts_dir=tmp_path)
            r2 = train_baseline(artifacts_dir=tmp_path)
        finally:
            mcfg.NUM_BOOST_ROUND, mcfg.EARLY_STOPPING_ROUNDS = original_rounds, original_stop

        dmat = xgb.DMatrix(r1["X_val"], feature_names=cfg.FEATURE_NAMES)
        pred1 = r1["booster"].predict(dmat)
        pred2 = r2["booster"].predict(dmat)
        np.testing.assert_allclose(pred1, pred2)


class TestPredictFromFeatures:
    def test_prediction_clamped_to_0_100(self, trained):
        booster = trained["booster"]
        extreme_features = {name: 1e6 for name in cfg.FEATURE_NAMES}
        result = predict_from_features(extreme_features, booster=booster)
        assert 0.0 <= result["risk_score"] <= 100.0

    def test_model_version_present(self, trained):
        result = predict_from_features(
            {name: 0.0 for name in cfg.FEATURE_NAMES}, booster=trained["booster"]
        )
        assert result["model_version"] == mcfg.MODEL_VERSION

    def test_missing_features_become_nan_not_crash(self, trained):
        partial = {name: 1.0 for name in cfg.FEATURE_NAMES[:5]}
        result = predict_from_features(partial, booster=trained["booster"])
        assert 0.0 <= result["risk_score"] <= 100.0


class TestBaselineComparisonPipeline:
    def test_row_to_fake_profile_exposes_every_field_the_baseline_reads(self, trained):
        row = trained["test_df"].iloc[0]
        fake_profile = _row_to_fake_profile(row)
        from app.services import behaviour_risk_baseline_service as baseline_svc
        result = baseline_svc.assess_rider_risk(fake_profile)  # must not raise
        assert result.risk_score is not None

    def test_baseline_predictions_in_range(self, trained):
        preds = compute_baseline_predictions(trained["test_df"])
        assert np.all((preds >= 0.0) & (preds <= 100.0))

    def test_xgboost_predictions_in_range(self, trained):
        preds = compute_xgboost_predictions(trained["test_df"], trained["booster"])
        assert np.all((preds >= 0.0) & (preds <= 100.0))

    def test_regression_metrics_sane_on_perfect_prediction(self):
        y = np.array([10.0, 50.0, 90.0, 30.0])
        metrics = _regression_metrics(y, y.copy())
        assert metrics["mae"] == pytest.approx(0.0)
        assert metrics["rmse"] == pytest.approx(0.0)
        assert metrics["r2"] == pytest.approx(1.0)

    def test_regression_metrics_detect_a_bad_predictor(self):
        y_true = np.array([10.0, 20.0, 30.0, 40.0])
        y_pred = np.array([40.0, 30.0, 20.0, 10.0])  # inverted — should score poorly
        metrics = _regression_metrics(y_true, y_pred)
        assert metrics["r2"] < 0.0

    def test_full_evaluate_runs_end_to_end_and_reports_both_models(self, trained, capsys):
        result = evaluate(trained["test_df"], trained["booster"])
        assert "mae" in result["baseline_metrics"]
        assert "mae" in result["xgb_metrics"]
        assert isinstance(result["xgb_better"], (bool, np.bool_))
        captured = capsys.readouterr()
        assert "BASELINE (Phase 3) vs XGBOOST" in captured.out
        assert "DISCLAIMER" in captured.out

    def test_reliability_bins_cover_the_prediction_range(self, trained):
        y_true = trained["test_df"][cfg.TARGET_NAME].to_numpy()
        xgb_pred = compute_xgboost_predictions(trained["test_df"], trained["booster"])
        bins = _reliability_bins(y_true, xgb_pred)
        assert len(bins) > 0
        assert sum(b["n"] for b in bins) == len(xgb_pred)
