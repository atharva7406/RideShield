"""
Phase 4 — XGBoost regression training for the behaviour risk score.

SYNTHETIC DATA DISCLAIMER: trains against procedurally generated rider
histories (generate_synthetic_riders.py), whose target is a LATENT true_
risk value the generator itself defines — not real-world accident data,
not the Phase 3 baseline's output. Metrics from this pipeline measure
"did the model learn the synthetic generator's pattern," a development
proxy, not real-world predictive accuracy. See evaluate_model.py for the
baseline comparison this whole phase exists to produce.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from . import config as cfg
from . import model_config as mcfg
from .dataset import load_dataset
from .sanity_checks import SanityCheckError, run_sanity_checks


def prepare_matrix(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    X = df[cfg.FEATURE_NAMES].astype(float).to_numpy()
    y = df[cfg.TARGET_NAME].astype(float).to_numpy()
    return X, y


def train_baseline(artifacts_dir: Path | None = None) -> dict:
    artifacts_dir = artifacts_dir or mcfg.ARTIFACTS_DIR
    train_df = load_dataset(artifacts_dir / "synthetic_riders_train.parquet")
    val_df = load_dataset(artifacts_dir / "synthetic_riders_val.parquet")
    test_df = load_dataset(artifacts_dir / "synthetic_riders_test.parquet")

    print("=" * 78)
    print("PHASE 4 — PRE-TRAINING SANITY CHECKS")
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

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=cfg.FEATURE_NAMES, missing=np.nan)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=cfg.FEATURE_NAMES, missing=np.nan)

    print("=" * 78)
    print("PHASE 4 — XGBOOST REGRESSION TRAINING")
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
    print(f"Best iteration:      {booster.best_iteration} (of {mcfg.NUM_BOOST_ROUND} max)")
    print(f"Best val RMSE:       {booster.best_score:.3f}")
    print(f"Train RMSE (same it): {evals_result['train']['rmse'][booster.best_iteration]:.3f}")

    model_path = artifacts_dir / mcfg.MODEL_PATH.name
    model_path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(model_path))
    print(f"\nSaved model to {model_path} (version={mcfg.MODEL_VERSION})")

    return {
        "booster": booster,
        "train_df": train_df, "val_df": val_df, "test_df": test_df,
        "X_train": X_train, "y_train": y_train,
        "X_val": X_val, "y_val": y_val,
        "sanity_report": report,
    }


if __name__ == "__main__":
    train_baseline()
