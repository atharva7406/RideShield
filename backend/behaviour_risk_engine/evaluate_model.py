"""
Phase 4 — XGBoost evaluation AND the baseline-vs-XGBoost comparison this
whole phase exists to produce. Runs entirely on the TEST split (never
touched during training/early-stopping — that used train/val only).

Computes the Phase 3 deterministic baseline's score on the exact same test
rows by calling the REAL app.services.behaviour_risk_baseline_service.
assess_rider_risk() against a lightweight stand-in object exposing the
same attributes a real RiderBehaviourProfile would — not a reimplementation
of the baseline's formula, the actual production function.

SYNTHETIC DATA DISCLAIMER: see train_model.py's module docstring.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import xgboost as xgb

_BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services import behaviour_risk_baseline_service as baseline_svc

from . import config as cfg
from .predict import predict_from_features


def _row_to_fake_profile(row: pd.Series) -> SimpleNamespace:
    """Everything assess_rider_risk() reads, pulled from one test-set row
    — not a reimplementation of the baseline, an adapter so the REAL
    baseline function can run against these synthetic rows exactly as it
    would against a real ORM-backed RiderBehaviourProfile."""
    return SimpleNamespace(
        recent_hard_braking_rate=row["recent_hard_braking_rate"],
        recent_hard_acceleration_rate=row["recent_hard_acceleration_rate"],
        recent_overspeeding_rate=row["recent_overspeeding_rate"],
        recent_sharp_turn_rate=row["recent_sharp_turn_rate"],
        recent_max_g=row["recent_max_g"],
        long_term_hard_braking_rate=row["long_term_hard_braking_rate"],
        long_term_overspeeding_rate=row["long_term_overspeeding_rate"],
        behaviour_consistency_score=row["behaviour_consistency_score"],
        overall_behaviour_score=row["overall_behaviour_score"],
        data_quality_score=row["data_quality_score"],
        confidence=row["confidence"],
        based_on_valid_shift_count=row["based_on_valid_shift_count"],
        based_on_shift_count=row["based_on_shift_count"],
    )


def compute_baseline_predictions(test_df: pd.DataFrame) -> np.ndarray:
    predictions = []
    for _, row in test_df.iterrows():
        fake_profile = _row_to_fake_profile(row)
        result = baseline_svc.assess_rider_risk(fake_profile)
        predictions.append(result.risk_score)
    return np.array(predictions, dtype=float)


def compute_xgboost_predictions(test_df: pd.DataFrame, booster: xgb.Booster) -> np.ndarray:
    predictions = []
    for _, row in test_df.iterrows():
        features = {name: float(row[name]) for name in cfg.FEATURE_NAMES}
        result = predict_from_features(features, booster=booster)
        predictions.append(result["risk_score"])
    return np.array(predictions, dtype=float)


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    ss_res = float(np.sum(errors ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
    correlation = float(np.corrcoef(y_true, y_pred)[0, 1]) if np.std(y_pred) > 0 else float("nan")
    return {
        "mae": mae, "rmse": rmse, "r2": r2, "correlation": correlation,
        "pred_min": float(y_pred.min()), "pred_max": float(y_pred.max()), "pred_mean": float(y_pred.mean()),
    }


def _reliability_bins(y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 5) -> list[dict]:
    """Coarse calibration check: within each predicted-score bin, does the
    mean TRUE value roughly track the mean PREDICTED value? Large gaps
    indicate the model is systematically over/under-confident in that
    range, not just noisy."""
    bins = np.linspace(0, 100, n_bins + 1)
    bin_idx = np.clip(np.digitize(y_pred, bins) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        mask = bin_idx == b
        n = int(mask.sum())
        if n == 0:
            continue
        rows.append({
            "bin": f"{bins[b]:.0f}-{bins[b + 1]:.0f}", "n": n,
            "mean_predicted": float(y_pred[mask].mean()), "mean_true": float(y_true[mask].mean()),
        })
    return rows


def _print_metrics_table(baseline_metrics: dict, xgb_metrics: dict) -> None:
    print(f"{'Metric':<14} {'Baseline':>12} {'XGBoost':>12}")
    for key, label in [("mae", "MAE"), ("rmse", "RMSE"), ("r2", "R²"), ("correlation", "Correlation")]:
        print(f"{label:<14} {baseline_metrics[key]:>12.3f} {xgb_metrics[key]:>12.3f}")
    print(f"{'Pred range':<14} {baseline_metrics['pred_min']:>5.1f}-{baseline_metrics['pred_max']:<6.1f} "
          f"{xgb_metrics['pred_min']:>5.1f}-{xgb_metrics['pred_max']:<6.1f}")


def evaluate(test_df: pd.DataFrame, booster: xgb.Booster) -> dict:
    y_true = test_df[cfg.TARGET_NAME].astype(float).to_numpy()

    print("=" * 78)
    print("BASELINE (Phase 3) vs XGBOOST — SAME HELD-OUT TEST RIDERS")
    print("=" * 78)
    baseline_pred = compute_baseline_predictions(test_df)
    xgb_pred = compute_xgboost_predictions(test_df, booster)

    baseline_metrics = _regression_metrics(y_true, baseline_pred)
    xgb_metrics = _regression_metrics(y_true, xgb_pred)
    _print_metrics_table(baseline_metrics, xgb_metrics)
    print()

    xgb_better = xgb_metrics["rmse"] < baseline_metrics["rmse"]
    print(f"XGBoost {'IMPROVED on' if xgb_better else 'did NOT improve on'} the baseline "
          f"(RMSE {xgb_metrics['rmse']:.3f} vs {baseline_metrics['rmse']:.3f}).")
    print()

    print("=" * 78)
    print("XGBOOST RELIABILITY (predicted-score bins vs. mean true value)")
    print("=" * 78)
    reliability = _reliability_bins(y_true, xgb_pred)
    for r in reliability:
        print(f"  {r['bin']:>8}  n={r['n']:4d}  mean_predicted={r['mean_predicted']:6.2f}  mean_true={r['mean_true']:6.2f}")
    print()

    print("=" * 78)
    print("NATIVE XGBOOST FEATURE IMPORTANCE (gain-based, top 10)")
    print("=" * 78)
    importance = booster.get_score(importance_type="gain")
    for name, gain in sorted(importance.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        print(f"  {name:35s} {gain:10.2f}")
    print()

    if xgb_metrics["r2"] > 0.97:
        print("!" * 78)
        print(f"R²={xgb_metrics['r2']:.4f} is suspiciously high for a synthetic-noise regression task.")
        print("Per Phase 4 spec item 12: investigating rather than reporting this as success.")
        print("!" * 78)
        _investigate_suspicious_performance(test_df, y_true, xgb_pred, importance)

    print("!" * 78)
    print("DISCLAIMER: all metrics above are on SYNTHETIC data whose target is a")
    print("latent generator parameter, not real accident/claims outcomes. This")
    print("measures 'did the model learn the synthetic generator's pattern' — a")
    print("pipeline validation, not evidence of real-world predictive accuracy.")
    print("!" * 78)

    return {
        "baseline_metrics": baseline_metrics, "xgb_metrics": xgb_metrics,
        "xgb_better": xgb_better, "reliability_bins": reliability,
        "feature_importance": importance,
        "baseline_predictions": baseline_pred, "xgb_predictions": xgb_pred, "y_true": y_true,
    }


def _investigate_suspicious_performance(test_df: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray,
                                         importance: dict) -> None:
    """Checks for the two shortcut-learning patterns most likely to
    produce an inflated R² on THIS generator: (a) one feature dominating
    gain far beyond the rest (a near-lookup-table relationship), (b)
    near-zero residual variance concentrated in a narrow true_risk band
    (suggesting the model memorized rather than generalized)."""
    total_gain = sum(importance.values()) or 1.0
    top_name, top_gain = max(importance.items(), key=lambda kv: kv[1])
    top_share = top_gain / total_gain
    print(f"  Top feature '{top_name}' accounts for {top_share:.1%} of total gain "
          f"({'POSSIBLE single-feature shortcut' if top_share > 0.6 else 'not obviously dominant'}).")

    residuals = np.abs(y_pred - y_true)
    print(f"  Residual mean={residuals.mean():.2f}, max={residuals.max():.2f}, "
          f"90th pct={np.percentile(residuals, 90):.2f}")
    print(f"  Test set archetype diversity: {test_df['archetype'].nunique()} archetypes present.")


if __name__ == "__main__":
    from .train_model import train_baseline

    result = train_baseline()
    evaluate(result["test_df"], result["booster"])
