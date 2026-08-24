import numpy as np
import pytest
import xgboost as xgb

from ml_incident_engine import model_config as mcfg
from ml_incident_engine.dataset import build_and_save, windows_to_dataframe
from ml_incident_engine.feature_extraction import FEATURE_NAMES
from ml_incident_engine.generate_synthetic_data import generate_dataset
from ml_incident_engine.train_model import prepare_matrix, train_baseline


class TestPrepareMatrix:
    def test_shapes_and_label_encoding(self):
        windows = generate_dataset(events_per_class=5, augmentations_per_event=1,
                                    num_riders=2, shifts_per_rider=1, seed=11)
        df = windows_to_dataframe(windows)
        X, y = prepare_matrix(df)

        assert X.shape == (len(df), len(FEATURE_NAMES))
        assert y.shape == (len(df),)
        assert X.dtype == np.float64
        assert set(np.unique(y)) <= set(mcfg.CLASS_TO_INDEX.values())

    def test_boolean_feature_becomes_numeric(self):
        windows = generate_dataset(events_per_class=5, augmentations_per_event=1,
                                    num_riders=2, shifts_per_rider=1, seed=12)
        df = windows_to_dataframe(windows)
        X, _ = prepare_matrix(df)
        stillness_col = FEATURE_NAMES.index("post_impact_stillness")
        assert set(np.unique(X[:, stillness_col])) <= {0.0, 1.0}

    def test_optional_features_become_nan_not_crash(self):
        # speed_drop etc. can legitimately be None for some windows; make
        # sure that doesn't blow up float conversion.
        windows = generate_dataset(events_per_class=5, augmentations_per_event=1,
                                    num_riders=2, shifts_per_rider=1, seed=13)
        df = windows_to_dataframe(windows)
        X, _ = prepare_matrix(df)
        assert np.isfinite(X).any()  # not every value is NaN


class TestTrainBaselineSmoke:
    """A small end-to-end run (tiny dataset, few boosting rounds) — not
    asserting on model quality, just that the whole Phase 3 pipeline
    (sanity checks -> DMatrix -> xgb.train -> save) actually runs without
    error and produces a usable booster."""

    @pytest.fixture(scope="class")
    def tiny_artifacts_dir(self, tmp_path_factory):
        out_dir = tmp_path_factory.mktemp("phase3_smoke")
        build_and_save(
            output_dir=out_dir,
            events_per_class=20,
            augmentations_per_event=2,
            num_riders=6,
            shifts_per_rider=2,
            seed=77,
        )
        return out_dir

    def test_train_baseline_runs_and_saves_a_usable_model(self, tiny_artifacts_dir, monkeypatch):
        # Keep training fast for the smoke test without touching the real
        # baseline hyperparameters used for the actual reported run.
        monkeypatch.setattr(mcfg, "NUM_BOOST_ROUND", 20)
        monkeypatch.setattr(mcfg, "EARLY_STOPPING_ROUNDS", 5)
        monkeypatch.setattr(mcfg, "BASELINE_MODEL_PATH", tiny_artifacts_dir / "smoke_model.json")

        result = train_baseline(artifacts_dir=tiny_artifacts_dir)

        booster = result["booster"]
        assert booster.best_iteration >= 0
        assert (tiny_artifacts_dir / "smoke_model.json").exists()

        proba = booster.predict(xgb.DMatrix(result["X_val"], feature_names=FEATURE_NAMES))
        assert proba.shape == (len(result["y_val"]), len(mcfg.CLASS_ORDER))
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-4)  # valid softmax rows
