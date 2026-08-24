"""
Phase 3 model-specific configuration — hyperparameters, class ordering, and
artifact paths. Kept separate from config.py (Phase 1: data generation /
feature extraction constants, already locked in by Phase 1's tests) so a
training hyperparameter change never risks touching the data pipeline.
"""

from __future__ import annotations

from pathlib import Path

from . import config as cfg

RANDOM_SEED = 42

CLASS_ORDER = list(cfg.EVENT_CLASSES)  # ["normal", "hard_braking", "pothole", "sharp_turn", "crash"]
CLASS_TO_INDEX = {c: i for i, c in enumerate(CLASS_ORDER)}
CRASH_CLASS_INDEX = CLASS_TO_INDEX[cfg.CRASH_CLASS]

# ---------------------------------------------------------------------------
# Baseline hyperparameters.
#
# Deliberately conservative/default-ish, not tuned — this is a BASELINE.
# The point of this first Phase 3 pass is to see how a single, ordinary
# multiclass model does on the (now-fixed) synthetic data before deciding
# whether the dual multiclass + calibrated-binary architecture discussed
# earlier is actually worth its added complexity. Do not read anything into
# the specific hyperparameter values below beyond "reasonable defaults."
# ---------------------------------------------------------------------------

BASELINE_XGB_PARAMS = {
    "objective": "multi:softprob",
    "num_class": len(CLASS_ORDER),
    "max_depth": 4,
    "eta": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "eval_metric": "mlogloss",
    "seed": RANDOM_SEED,
}
NUM_BOOST_ROUND = 300
EARLY_STOPPING_ROUNDS = 20

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
BASELINE_MODEL_PATH = ARTIFACTS_DIR / "baseline_xgboost_model.json"
