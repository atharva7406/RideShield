"""Inference layer — given a trained booster and a feature dict, return
the model's clamped [0,100] risk score. Mirrors ml_incident_engine/
predict.py's structure and role.

predict_from_features() is unchanged from Phase 4 (raw prediction) —
Phase 5 adds predict_calibrated_from_features() alongside it rather than
modifying it, so Phase 4's own tests/behaviour keep working untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import xgboost as xgb

from . import calibration as calib
from . import config as cfg
from . import model_config as mcfg

_booster_cache: dict[str, xgb.Booster] = {}
_calibration_cache: dict[str, Optional[dict]] = {}


def load_booster(model_path: Optional[Path] = None) -> xgb.Booster:
    model_path = model_path or mcfg.MODEL_PATH
    key = str(model_path)
    if key not in _booster_cache:
        booster = xgb.Booster()
        booster.load_model(str(model_path))
        _booster_cache[key] = booster
    return _booster_cache[key]


def predict_from_features(features: dict, booster: Optional[xgb.Booster] = None) -> dict:
    booster = booster or load_booster()
    x = np.array(
        [[np.nan if features.get(name) is None else features[name] for name in cfg.FEATURE_NAMES]],
        dtype=float,
    )
    dmat = xgb.DMatrix(x, feature_names=cfg.FEATURE_NAMES, missing=np.nan)
    raw_prediction = float(booster.predict(dmat)[0])
    risk_score = max(0.0, min(100.0, raw_prediction))

    importance = booster.get_score(importance_type="gain")
    top_features = sorted(importance.items(), key=lambda kv: kv[1], reverse=True)[:5]

    return {
        "risk_score": risk_score,
        "raw_prediction": raw_prediction,  # before clamping — useful for diagnosing saturation
        "model_version": mcfg.MODEL_VERSION,
        "top_features": [name for name, _ in top_features],
    }


def load_calibration_breakpoints(calibration_path: Optional[Path] = None) -> Optional[dict]:
    """Returns None (not an exception) if no calibration artifact exists
    or it fails to load/parse — its absence is a normal, expected state
    (see model_config.CALIBRATION_PATH's docstring: calibration is only
    persisted if it earned deployment), not a failure to raise about."""
    calibration_path = calibration_path or mcfg.CALIBRATION_PATH
    key = str(calibration_path)
    if key not in _calibration_cache:
        try:
            _calibration_cache[key] = calib.load_calibration(calibration_path)
        except Exception:
            _calibration_cache[key] = None
    return _calibration_cache[key]


def predict_calibrated_from_features(features: dict, booster: Optional[xgb.Booster] = None,
                                      calibration_path: Optional[Path] = None) -> dict:
    """Same contract as predict_from_features(), plus `is_calibrated`.
    Never raises for a calibration-specific reason — if no calibration
    artifact is available or applying it fails for any reason, degrades
    to the raw (still real, still tested, still better than the Phase 3
    baseline per Phase 4's evaluation) XGBoost prediction rather than
    propagating an error. Only a failure of the underlying booster itself
    (handled by predict_from_features/load_booster) should ever reach the
    caller as an exception."""
    raw_result = predict_from_features(features, booster=booster)
    breakpoints = load_calibration_breakpoints(calibration_path)
    if breakpoints is None:
        return {**raw_result, "is_calibrated": False}

    try:
        calibrated_score = calib.apply_calibration(raw_result["risk_score"], breakpoints)
    except Exception:
        return {**raw_result, "is_calibrated": False}

    return {
        **raw_result,
        "risk_score": calibrated_score,
        "model_version": mcfg.CALIBRATED_MODEL_VERSION,
        "is_calibrated": True,
    }
