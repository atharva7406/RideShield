"""
Phase 5 — fits isotonic calibration on the EXISTING Phase 4 validation
split (already used for XGBoost's early stopping, never for fitting the
trees' own parameters — fitting a separate, post-hoc calibration layer on
it is standard practice), then evaluates raw vs. calibrated on the
EXISTING Phase 4 TEST split, which this script never touches to fit or
choose anything. Does NOT retrain XGBoost — loads the already-trained
Phase 4 model as-is, per the Phase 5 instruction to build on top of it
without changing Phases 1-4.

DEPLOY DECISION — pre-registered, not chosen by peeking at results: the
calibration artifact is saved (and therefore used by the production
service) ONLY if it improves test-set RMSE over the raw model. This
decision rule was fixed before running the comparison, not selected after
seeing which of several methods "won" on the test set — that would be
exactly the test-set-tuning the Phase 5 spec prohibits. If calibration
doesn't improve RMSE, no artifact is written (and any stale prior one is
removed) and the service keeps using the raw model, per Phase 5 item 12:
"if it does not [improve], keep the simpler raw model."

SYNTHETIC DATA DISCLAIMER: see train_model.py's module docstring. This
evaluates on the same synthetic riders Phase 4 did — results describe
"does calibration correct this synthetic generator's bias pattern," not
real-world model accuracy.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import calibration as calib
from . import config as cfg
from . import model_config as mcfg
from .dataset import load_dataset
from .evaluate_model import _reliability_bins, _regression_metrics, compute_xgboost_predictions
from .predict import load_booster


def _apply_calibration_array(raw_preds: np.ndarray, breakpoints: dict) -> np.ndarray:
    return np.array([calib.apply_calibration(p, breakpoints) for p in raw_preds], dtype=float)


def run(artifacts_dir: Path | None = None) -> dict:
    artifacts_dir = artifacts_dir or mcfg.ARTIFACTS_DIR
    val_df = load_dataset(artifacts_dir / "synthetic_riders_val.parquet")
    test_df = load_dataset(artifacts_dir / "synthetic_riders_test.parquet")
    booster = load_booster()

    print("=" * 78)
    print("PHASE 5 — FITTING ISOTONIC CALIBRATION ON VALIDATION SET")
    print("(the SAME val split Phase 4 used for early stopping — never the test set)")
    print("=" * 78)
    val_raw_preds = compute_xgboost_predictions(val_df, booster)
    val_true = val_df[cfg.TARGET_NAME].to_numpy()
    iso = calib.fit_isotonic_calibration(val_raw_preds, val_true)
    breakpoints = calib.calibration_breakpoints(iso)

    # Correctness check, not a tuning step: confirms the lightweight
    # numpy-only apply_calibration() at inference time reproduces
    # sklearn's IsotonicRegression.predict() exactly, before this artifact
    # is ever considered for deployment.
    sample_x = np.linspace(0.0, 100.0, 41)
    sklearn_pred = iso.predict(sample_x)
    interp_pred = _apply_calibration_array(sample_x, breakpoints)
    max_diff = float(np.max(np.abs(sklearn_pred - interp_pred)))
    print(f"np.interp vs sklearn IsotonicRegression max prediction diff: {max_diff:.8f}")
    if max_diff >= 1e-6:
        raise AssertionError("apply_calibration() does not reproduce IsotonicRegression.predict() — refusing to deploy")
    print("Confirmed: numpy-based calibration application is numerically exact.\n")

    print("=" * 78)
    print("PHASE 5 — RAW vs CALIBRATED ON HELD-OUT TEST SET (never used above)")
    print("=" * 78)
    test_true = test_df[cfg.TARGET_NAME].to_numpy()
    test_raw_preds = compute_xgboost_predictions(test_df, booster)
    test_calibrated_preds = _apply_calibration_array(test_raw_preds, breakpoints)

    raw_metrics = _regression_metrics(test_true, test_raw_preds)
    calibrated_metrics = _regression_metrics(test_true, test_calibrated_preds)

    print(f"{'Metric':<14} {'Raw XGBoost':>14} {'Calibrated':>14}")
    for key, label in [("mae", "MAE"), ("rmse", "RMSE"), ("r2", "R2"), ("correlation", "Correlation")]:
        print(f"{label:<14} {raw_metrics[key]:>14.3f} {calibrated_metrics[key]:>14.3f}")
    print()

    raw_residuals = test_raw_preds - test_true
    cal_residuals = test_calibrated_preds - test_true
    print("Residual (prediction - true) distribution:")
    print(f"  Raw:        mean={raw_residuals.mean():+.3f}  std={raw_residuals.std():.3f}  "
          f"|mean bias|={abs(raw_residuals.mean()):.3f}  max_abs={np.abs(raw_residuals).max():.3f}")
    print(f"  Calibrated: mean={cal_residuals.mean():+.3f}  std={cal_residuals.std():.3f}  "
          f"|mean bias|={abs(cal_residuals.mean()):.3f}  max_abs={np.abs(cal_residuals).max():.3f}")
    print()

    print("Reliability by risk band — RAW:")
    for r in _reliability_bins(test_true, test_raw_preds):
        print(f"  {r['bin']:>8}  n={r['n']:3d}  mean_predicted={r['mean_predicted']:6.2f}  mean_true={r['mean_true']:6.2f}  "
              f"gap={r['mean_predicted'] - r['mean_true']:+.2f}")
    print("Reliability by risk band — CALIBRATED:")
    for r in _reliability_bins(test_true, test_calibrated_preds):
        print(f"  {r['bin']:>8}  n={r['n']:3d}  mean_predicted={r['mean_predicted']:6.2f}  mean_true={r['mean_true']:6.2f}  "
              f"gap={r['mean_predicted'] - r['mean_true']:+.2f}")
    print()

    deploy_calibration = calibrated_metrics["rmse"] < raw_metrics["rmse"]
    print("=" * 78)
    if deploy_calibration:
        print(f"DECISION: calibration IMPROVES test RMSE "
              f"({calibrated_metrics['rmse']:.3f} < {raw_metrics['rmse']:.3f}) — deploying calibration artifact.")
        calib.save_calibration(breakpoints, mcfg.CALIBRATION_PATH)
        print(f"Saved to {mcfg.CALIBRATION_PATH} (version={mcfg.CALIBRATED_MODEL_VERSION})")
    else:
        print(f"DECISION: calibration does NOT improve test RMSE "
              f"({calibrated_metrics['rmse']:.3f} >= {raw_metrics['rmse']:.3f}) — "
              f"keeping the simpler raw model, per Phase 5 spec item 12.")
        if mcfg.CALIBRATION_PATH.exists():
            mcfg.CALIBRATION_PATH.unlink()
            print(f"Removed stale prior calibration artifact at {mcfg.CALIBRATION_PATH}.")
    print("=" * 78)

    print()
    print("!" * 78)
    print("DISCLAIMER: evaluated on SYNTHETIC data (see train_model.py's module")
    print("docstring). This measures whether calibration corrects the synthetic")
    print("generator's own bias pattern — a pipeline validation, not evidence of")
    print("real-world model accuracy.")
    print("!" * 78)

    return {
        "raw_metrics": raw_metrics,
        "calibrated_metrics": calibrated_metrics,
        "deploy_calibration": bool(deploy_calibration),
        "raw_residual_mean": float(raw_residuals.mean()),
        "raw_residual_std": float(raw_residuals.std()),
        "calibrated_residual_mean": float(cal_residuals.mean()),
        "calibrated_residual_std": float(cal_residuals.std()),
        "np_interp_vs_sklearn_max_diff": max_diff,
    }


if __name__ == "__main__":
    run()
