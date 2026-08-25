"""
Phase 5 — regression calibration for the Phase 4 XGBoost behaviour-risk
model.

"Calibration" here means correcting systematic bias in the raw XGBoost
regression output using ISOTONIC regression — not Platt scaling, which
calibrates classifier probabilities and doesn't apply to a continuous
0-100 regression target. Isotonic regression directly targets the exact
failure mode Phase 4's own reliability-bin analysis could reveal
(systematic over/under-prediction concentrated in specific score ranges),
without assuming a particular parametric correction shape.

The fitted calibration is persisted as its raw (x_thresholds, y_thresholds)
step-function breakpoints — NOT a pickled sklearn object — so applying it
at inference time only needs numpy (np.interp), matching this project's
existing "training-time deps stay training-time, inference stays minimal"
principle (ml_scoring_service.py, rider_behaviour_risk_service.py, Phase 4's
own predict.py). np.interp's default clipped-boundary behaviour exactly
reproduces IsotonicRegression(out_of_bounds="clip").predict() — verified
numerically in calibrate_and_evaluate.py's own run() before ever deploying
an artifact, and in tests/test_calibration.py, not just assumed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np


def fit_isotonic_calibration(raw_predictions: np.ndarray, true_values: np.ndarray):
    """Training-only — imports scikit-learn locally so this stays out of
    the inference-time dependency footprint (apply_calibration below needs
    only numpy)."""
    from sklearn.isotonic import IsotonicRegression

    iso = IsotonicRegression(y_min=0.0, y_max=100.0, out_of_bounds="clip", increasing=True)
    iso.fit(raw_predictions, true_values)
    return iso


def calibration_breakpoints(iso) -> dict:
    return {
        "x_thresholds": iso.X_thresholds_.tolist(),
        "y_thresholds": iso.y_thresholds_.tolist(),
    }


def save_calibration(breakpoints: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(breakpoints, f)


def load_calibration(path: Path) -> dict:
    """Raises on missing/corrupted/malformed file — callers (predict.py)
    are responsible for catching and degrading gracefully, same pattern as
    predict.load_booster()."""
    path = Path(path)
    with open(path, "r") as f:
        data = json.load(f)
    if "x_thresholds" not in data or "y_thresholds" not in data:
        raise ValueError(f"Calibration file {path} missing required keys")
    if len(data["x_thresholds"]) != len(data["y_thresholds"]) or len(data["x_thresholds"]) < 2:
        raise ValueError(f"Calibration file {path} has malformed breakpoint arrays")
    return data


def apply_calibration(raw_score: float, breakpoints: dict) -> float:
    x = breakpoints["x_thresholds"]
    y = breakpoints["y_thresholds"]
    calibrated = float(np.interp(raw_score, x, y))
    return max(0.0, min(100.0, calibrated))
