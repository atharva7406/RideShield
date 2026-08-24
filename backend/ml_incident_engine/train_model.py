"""
Phase 3 — baseline model training.

Trains a single multiclass XGBoost classifier (softmax probabilities over
all 5 classes) as a BASELINE — deliberately NOT the dual multiclass +
calibrated-binary architecture discussed earlier. The point of this first
pass is to see how an ordinary model performs on this data before deciding
whether that extra complexity is actually earned.

Only reads train/val splits. The test split is loaded for the sanity
checks (leakage/class-presence/balance) but never used for fitting or for
any metric in this script — it stays held out for a single, final
evaluation once the model design is settled; using it now would burn that.

SYNTHETIC DATA DISCLAIMER: this script measures fit to synthetic,
procedurally generated data (see generate_synthetic_data.py). That's a
development proxy for whether the pipeline/features work, not a measure of
real-world crash-detection accuracy — do not report these numbers as such.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from . import model_config as mcfg
from .dataset import load_dataset
from .feature_extraction import FEATURE_NAMES
from .sanity_checks import SanityCheckError, run_sanity_checks


def prepare_matrix(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Feature matrix + integer-encoded labels. Optional features that are
    None become NaN (XGBoost's native missing-value handling deals with
    this directly — no imputation needed)."""
    X = df[FEATURE_NAMES].astype(float).to_numpy()
    y = df["class_label"].map(mcfg.CLASS_TO_INDEX).to_numpy()
    return X, y


def train_baseline(artifacts_dir: Path | None = None) -> dict:
    artifacts_dir = artifacts_dir or mcfg.ARTIFACTS_DIR
    train_df = load_dataset(artifacts_dir / "synthetic_dataset_train.parquet")
    val_df = load_dataset(artifacts_dir / "synthetic_dataset_val.parquet")
    test_df = load_dataset(artifacts_dir / "synthetic_dataset_test.parquet")

    print("=" * 78)
    print("PHASE 3 — PRE-TRAINING SANITY CHECKS")
    print("=" * 78)
    try:
        report = run_sanity_checks(train_df, val_df, test_df)
    except (SanityCheckError, AssertionError) as e:
        print(f"SANITY CHECK FAILED: {e}")
        raise
    print(json.dumps(report, indent=2, default=str))
    print("All sanity checks passed.\n")

    X_train, y_train = prepare_matrix(train_df)
    X_val, y_val = prepare_matrix(val_df)

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_NAMES, missing=np.nan)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_NAMES, missing=np.nan)

    print("=" * 78)
    print("PHASE 3 — BASELINE MODEL TRAINING (single multiclass XGBoost)")
    print("=" * 78)
    evals_result: dict = {}
    booster = xgb.train(
        mcfg.BASELINE_XGB_PARAMS,
        dtrain,
        num_boost_round=mcfg.NUM_BOOST_ROUND,
        evals=[(dtrain, "train"), (dval, "val")],
        early_stopping_rounds=mcfg.EARLY_STOPPING_ROUNDS,
        evals_result=evals_result,
        verbose_eval=False,
    )
    print(f"Best iteration:              {booster.best_iteration} (of {mcfg.NUM_BOOST_ROUND} max, "
          f"early_stopping_rounds={mcfg.EARLY_STOPPING_ROUNDS})")
    print(f"Best val mlogloss:           {booster.best_score:.4f}")
    print(f"Train mlogloss (same iter):  {evals_result['train']['mlogloss'][booster.best_iteration]:.4f}")
    train_val_gap = evals_result['train']['mlogloss'][booster.best_iteration] - booster.best_score
    print(f"Train-val mlogloss gap:      {train_val_gap:.4f}  "
          f"({'larger gap can indicate overfitting' if train_val_gap < -0.05 else 'no obvious overfitting signal'})")

    mcfg.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(mcfg.BASELINE_MODEL_PATH))
    print(f"\nSaved baseline model to {mcfg.BASELINE_MODEL_PATH}")

    return {
        "booster": booster,
        "train_df": train_df, "val_df": val_df, "test_df": test_df,
        "X_train": X_train, "y_train": y_train,
        "X_val": X_val, "y_val": y_val,
        "sanity_report": report,
    }


if __name__ == "__main__":
    train_baseline()
