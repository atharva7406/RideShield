import numpy as np
import pytest

from ml_incident_engine import model_config as mcfg
from ml_incident_engine.dataset import build_and_save
from ml_incident_engine.feature_extraction import FEATURE_NAMES, extract_feature_vector
from ml_incident_engine.generate_synthetic_data import generate_event
from ml_incident_engine.predict import load_booster, predict_from_features, predict_window
from ml_incident_engine.train_model import train_baseline


@pytest.fixture(scope="module")
def trained_booster(tmp_path_factory, monkeypatch_module=None):
    out_dir = tmp_path_factory.mktemp("predict_smoke")
    build_and_save(output_dir=out_dir, events_per_class=15, augmentations_per_event=2,
                    num_riders=5, shifts_per_rider=2, seed=555)
    import ml_incident_engine.model_config as mcfg_module
    original_rounds = mcfg_module.NUM_BOOST_ROUND
    original_stop = mcfg_module.EARLY_STOPPING_ROUNDS
    mcfg_module.NUM_BOOST_ROUND = 15
    mcfg_module.EARLY_STOPPING_ROUNDS = 5
    try:
        result = train_baseline(artifacts_dir=out_dir)
    finally:
        mcfg_module.NUM_BOOST_ROUND = original_rounds
        mcfg_module.EARLY_STOPPING_ROUNDS = original_stop
    return result["booster"]


class TestPredictWindow:
    def test_output_shape_and_keys(self, trained_booster):
        rng = np.random.default_rng(1)
        window = generate_event("crash", rng, rider_id="r", shift_id="s")
        result = predict_window(window, booster=trained_booster)

        assert set(result.keys()) == {
            "crash_probability", "predicted_class", "class_probabilities",
            "feature_values", "model_version",
        }
        assert result["predicted_class"] in mcfg.CLASS_ORDER
        assert 0.0 <= result["crash_probability"] <= 1.0
        assert set(result["class_probabilities"].keys()) == set(mcfg.CLASS_ORDER)
        assert abs(sum(result["class_probabilities"].values()) - 1.0) < 1e-4

    def test_predict_from_features_matches_predict_window(self, trained_booster):
        rng = np.random.default_rng(2)
        window = generate_event("normal", rng, rider_id="r", shift_id="s")
        features = extract_feature_vector(window)

        via_window = predict_window(window, booster=trained_booster)
        via_features = predict_from_features(features, booster=trained_booster)

        assert via_window["predicted_class"] == via_features["predicted_class"]
        assert via_window["crash_probability"] == pytest.approx(via_features["crash_probability"])

    def test_does_not_decide_verified_crash(self, trained_booster):
        # Contract check: the output is a raw prediction, not a decision —
        # no "is_verified" / "incident_status" key should ever appear here,
        # that's the (separate, unbuilt) Incident Decision Engine's job.
        rng = np.random.default_rng(3)
        window = generate_event("crash", rng, rider_id="r", shift_id="s")
        result = predict_window(window, booster=trained_booster)
        assert "is_verified" not in result
        assert "incident_status" not in result

    def test_missing_optional_feature_does_not_crash_inference(self, trained_booster):
        rng = np.random.default_rng(4)
        window = generate_event("pothole", rng, rider_id="r", shift_id="s")
        features = extract_feature_vector(window)
        features["speed_drop"] = None  # force a missing Optional feature
        result = predict_from_features(features, booster=trained_booster)
        assert result["predicted_class"] in mcfg.CLASS_ORDER


class TestLoadBoosterCaching:
    def test_same_path_returns_cached_instance(self, trained_booster, tmp_path):
        model_path = tmp_path / "cached_model.json"
        trained_booster.save_model(str(model_path))
        b1 = load_booster(model_path)
        b2 = load_booster(model_path)
        assert b1 is b2
