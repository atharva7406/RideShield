import io

import numpy as np
import pytest
from PIL import Image

from helmet_detection_engine import config as cfg
from helmet_detection_engine import predict


def _random_image_bytes(size=(400, 300)) -> bytes:
    arr = (np.random.rand(size[1], size[0], 3) * 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestPreprocessing:
    def test_produces_expected_tensor_shape(self):
        tensor = predict.preprocess_image_bytes(_random_image_bytes())
        assert tensor.shape == (1, 3, cfg.INPUT_SIZE, cfg.INPUT_SIZE)
        assert tensor.dtype == np.float32

    def test_values_normalized_to_0_1(self):
        tensor = predict.preprocess_image_bytes(_random_image_bytes())
        assert tensor.min() >= 0.0
        assert tensor.max() <= 1.0

    def test_handles_non_square_and_odd_sizes(self):
        for size in [(50, 800), (1000, 1000), (37, 91)]:
            tensor = predict.preprocess_image_bytes(_random_image_bytes(size))
            assert tensor.shape == (1, 3, cfg.INPUT_SIZE, cfg.INPUT_SIZE)

    def test_malformed_bytes_raise_value_error(self):
        with pytest.raises(ValueError):
            predict.preprocess_image_bytes(b"this is not an image")

    def test_empty_bytes_raise_value_error(self):
        with pytest.raises(ValueError):
            predict.preprocess_image_bytes(b"")


class TestModelLoading:
    def test_load_session_returns_a_session(self):
        session = predict.load_session()
        assert session is not None
        assert len(session.get_inputs()) == 1
        assert session.get_inputs()[0].shape == [1, 3, cfg.INPUT_SIZE, cfg.INPUT_SIZE]

    def test_missing_model_file_raises(self, tmp_path):
        with pytest.raises(Exception):
            predict.load_session(tmp_path / "does_not_exist.onnx")

    def test_session_is_cached(self):
        s1 = predict.load_session()
        s2 = predict.load_session()
        assert s1 is s2


class TestPredictFromImageBytes:
    def test_returns_expected_contract(self):
        result = predict.predict_from_image_bytes(_random_image_bytes())
        assert set(result.keys()) == {
            "predicted_class", "confidence", "helmet_worn",
            "class_probabilities", "model_version",
        }
        assert result["predicted_class"] in cfg.CLASS_NAMES
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["helmet_worn"], bool)
        assert set(result["class_probabilities"].keys()) == set(cfg.CLASS_NAMES)
        assert result["model_version"] == cfg.MODEL_VERSION

    def test_class_probabilities_sum_to_approximately_one(self):
        result = predict.predict_from_image_bytes(_random_image_bytes())
        total = sum(result["class_probabilities"].values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_helmet_worn_requires_both_helmet_class_and_threshold(self):
        # helmet_worn can only be True if predicted_class is a helmet
        # class AND confidence clears CONFIDENCE_THRESHOLD — verify the
        # contract holds across several random inputs (this model's
        # actual accuracy is not being asserted here, only the decision
        # rule wiring — see config.py's provenance note).
        for _ in range(10):
            result = predict.predict_from_image_bytes(_random_image_bytes())
            if result["helmet_worn"]:
                assert result["predicted_class"] in cfg.HELMET_CLASSES
                assert result["confidence"] >= cfg.CONFIDENCE_THRESHOLD

    def test_deterministic_for_the_same_image(self):
        img_bytes = _random_image_bytes()
        r1 = predict.predict_from_image_bytes(img_bytes)
        r2 = predict.predict_from_image_bytes(img_bytes)
        assert r1 == r2

    def test_malformed_image_raises_value_error(self):
        with pytest.raises(ValueError):
            predict.predict_from_image_bytes(b"garbage-not-an-image")
