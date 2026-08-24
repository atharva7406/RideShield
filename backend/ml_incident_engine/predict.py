"""
Phase 5 (inference layer only) — given a trained booster and a telemetry
window, return the ML layer's raw output. Deliberately returns ONLY
{crash_probability, predicted_class, class_probabilities, feature_values,
model_version} and does NOT decide "is this a verified crash" — that's the
still-unbuilt Incident Decision Engine's job, kept separate on purpose (see
the original Phase 5 discussion: "Do not directly make crash_probability
equal to verified crash").

Not wired into telemetry_service.py / the FastAPI app — this is the
offline inference entry point used by evaluate_external_csv.py and by
tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import xgboost as xgb

from . import model_config as mcfg
from .feature_extraction import FEATURE_NAMES, extract_feature_vector
from .generate_synthetic_data import TelemetryWindow

MODEL_VERSION = "baseline-xgboost-v1"

_booster_cache: dict[str, xgb.Booster] = {}


def load_booster(model_path: Optional[Path] = None) -> xgb.Booster:
    model_path = model_path or mcfg.BASELINE_MODEL_PATH
    key = str(model_path)
    if key not in _booster_cache:
        booster = xgb.Booster()
        booster.load_model(str(model_path))
        _booster_cache[key] = booster
    return _booster_cache[key]


def _feature_dict_to_row(features: dict) -> np.ndarray:
    return np.array(
        [[np.nan if features.get(name) is None else features[name] for name in FEATURE_NAMES]],
        dtype=float,
    )


def predict_from_features(features: dict, booster: Optional[xgb.Booster] = None) -> dict:
    """Same output shape as predict_window, for callers that already have
    a feature dict (e.g. features computed from an external CSV's raw
    samples, not a TelemetryWindow)."""
    booster = booster or load_booster()
    x = _feature_dict_to_row(features)
    dmat = xgb.DMatrix(x, feature_names=FEATURE_NAMES, missing=np.nan)
    proba = booster.predict(dmat)[0]
    predicted_idx = int(np.argmax(proba))
    return {
        "crash_probability": float(proba[mcfg.CRASH_CLASS_INDEX]),
        "predicted_class": mcfg.CLASS_ORDER[predicted_idx],
        "class_probabilities": {c: float(p) for c, p in zip(mcfg.CLASS_ORDER, proba)},
        "feature_values": features,
        "model_version": MODEL_VERSION,
    }


def predict_window(window: TelemetryWindow, booster: Optional[xgb.Booster] = None) -> dict:
    return predict_from_features(extract_feature_vector(window), booster=booster)
