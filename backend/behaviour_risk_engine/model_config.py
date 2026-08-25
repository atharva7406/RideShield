"""
Phase 4 model-specific configuration — regression hyperparameters and
artifact paths. Mirrors ml_incident_engine/model_config.py's role/reasons
for existing as a separate file from config.py.
"""

from __future__ import annotations

from pathlib import Path

RANDOM_SEED = 42

# Regression, not classification — the Phase 4 spec is explicit that a
# 5-class formulation would reintroduce the abrupt-boundary problem a
# premium engine needs to avoid. Conservative depth/rate/sampling +
# explicit L1/L2 regularization, matching the spec's "prevent obvious
# overfitting" instruction and NOT aggressively tuned against the test
# set — this is a first honest baseline comparison, not a tuned result.
BASELINE_XGB_PARAMS = {
    "objective": "reg:squarederror",
    "max_depth": 4,
    "eta": 0.08,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "reg_alpha": 0.5,
    "reg_lambda": 1.5,
    "eval_metric": "rmse",
    "seed": RANDOM_SEED,
}
NUM_BOOST_ROUND = 400
EARLY_STOPPING_ROUNDS = 25

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "behaviour_risk_xgboost_model.json"
MODEL_VERSION = "behaviour-risk-xgboost-v1"

# Phase 5 — regression calibration (see calibration.py). CALIBRATION_PATH
# only exists on disk if calibrate_and_evaluate.py's run() decided
# calibration actually improves test-set RMSE over the raw model — its
# absence is a normal, expected state (not an error), meaning "raw
# predictions were kept because calibration didn't earn its place."
CALIBRATION_PATH = ARTIFACTS_DIR / "behaviour_risk_calibration.json"
CALIBRATED_MODEL_VERSION = "behaviour-risk-xgboost-v1-calibrated"
