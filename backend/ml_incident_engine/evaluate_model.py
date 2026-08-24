"""
Phase 3/4 — baseline model evaluation, on the VAL split only.

Deliberately does not touch the test split (see train_model.py's
docstring) — that stays held out for a single, final look once the model
architecture question (single multiclass vs. the dual multiclass +
calibrated-binary design discussed earlier) is actually decided.

Reports, in order: multiclass confusion matrix, per-class precision/
recall/F1, crash-class one-vs-rest metrics, false-positive rate FROM each
hard-negative class (hard_braking, pothole, sharp_turn — the classes
Phase 1 was specifically built to make ambiguous) INTO crash, a decision-
threshold sweep on the crash probability, PR-AUC, native XGBoost feature
importance, and a reliability check on the RAW (uncalibrated) softmax
output — this baseline applies no Platt/sigmoid calibration yet, that was
explicitly deferred pending this first look.

SYNTHETIC DATA DISCLAIMER: see train_model.py's module docstring.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import auc, classification_report, confusion_matrix, precision_recall_curve

from . import model_config as mcfg
from .feature_extraction import FEATURE_NAMES


def predict_proba(booster: xgb.Booster, X: np.ndarray) -> np.ndarray:
    dmat = xgb.DMatrix(X, feature_names=FEATURE_NAMES, missing=np.nan)
    return booster.predict(dmat)  # (n, num_class) softmax probabilities


def _binary_metrics(y_true_binary: np.ndarray, y_pred_binary: np.ndarray) -> dict:
    tp = int(((y_pred_binary == 1) & (y_true_binary == 1)).sum())
    fp = int(((y_pred_binary == 1) & (y_true_binary == 0)).sum())
    fn = int(((y_pred_binary == 0) & (y_true_binary == 1)).sum())
    tn = int(((y_pred_binary == 0) & (y_true_binary == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1, "fpr": fpr}


def evaluate_baseline(booster: xgb.Booster, X_val: np.ndarray, y_val: np.ndarray) -> dict:
    proba = predict_proba(booster, X_val)
    y_pred = proba.argmax(axis=1)
    crash_idx = mcfg.CRASH_CLASS_INDEX
    crash_proba = proba[:, crash_idx]
    y_val_is_crash = (y_val == crash_idx).astype(int)
    y_pred_is_crash = (y_pred == crash_idx).astype(int)

    print("=" * 78)
    print("MULTICLASS CONFUSION MATRIX (rows = true class, cols = predicted class)")
    print("=" * 78)
    cm = confusion_matrix(y_val, y_pred, labels=list(range(len(mcfg.CLASS_ORDER))))
    cm_df = pd.DataFrame(cm, index=mcfg.CLASS_ORDER, columns=mcfg.CLASS_ORDER)
    print(cm_df.to_string())
    print()

    print("=" * 78)
    print("PER-CLASS PRECISION / RECALL / F1 (argmax predictions)")
    print("=" * 78)
    report_str = classification_report(y_val, y_pred, target_names=mcfg.CLASS_ORDER, digits=3, zero_division=0)
    print(report_str)

    print("=" * 78)
    print("CRASH CLASS — ONE-VS-REST (argmax prediction, i.e. threshold ~1/num_classes)")
    print("=" * 78)
    crash_metrics = _binary_metrics(y_val_is_crash, y_pred_is_crash)
    print(f"TP={crash_metrics['tp']}  FP={crash_metrics['fp']}  FN={crash_metrics['fn']}  TN={crash_metrics['tn']}")
    print(f"Precision={crash_metrics['precision']:.3f}  Recall={crash_metrics['recall']:.3f}  "
          f"F1={crash_metrics['f1']:.3f}  FPR={crash_metrics['fpr']:.3f}")
    print()

    print("=" * 78)
    print("FALSE-POSITIVE RATE INTO 'crash' FROM EACH HARD-NEGATIVE CLASS")
    print("(this is the number that actually matters for claims false-positives —")
    print(" these are the classes Phase 1 was built to make genuinely ambiguous)")
    print("=" * 78)
    hard_negative_fp_rates = {}
    for cls in ["normal", "hard_braking", "pothole", "sharp_turn"]:
        idx = mcfg.CLASS_TO_INDEX[cls]
        mask = y_val == idx
        n = int(mask.sum())
        n_as_crash = int((y_pred[mask] == crash_idx).sum())
        rate = n_as_crash / n if n else 0.0
        hard_negative_fp_rates[cls] = {"n": n, "predicted_as_crash": n_as_crash, "rate": round(rate, 4)}
        print(f"  {cls:15s}  n={n:4d}   predicted-as-crash={n_as_crash:4d}   rate={rate:.3f}")
    print()

    print("=" * 78)
    print("CRASH-PROBABILITY DECISION-THRESHOLD SWEEP")
    print("=" * 78)
    print(f"{'threshold':>10} {'precision':>10} {'recall':>10} {'f1':>8} {'fpr':>8} {'n_flagged':>10}")
    threshold_sweep = []
    for t in np.arange(0.1, 1.0, 0.1):
        pred_t = (crash_proba >= t).astype(int)
        m = _binary_metrics(y_val_is_crash, pred_t)
        row = {"threshold": round(float(t), 2), "precision": round(m["precision"], 3),
               "recall": round(m["recall"], 3), "f1": round(m["f1"], 3), "fpr": round(m["fpr"], 3),
               "n_flagged": m["tp"] + m["fp"]}
        threshold_sweep.append(row)
        print(f"{t:>10.1f} {m['precision']:>10.3f} {m['recall']:>10.3f} {m['f1']:>8.3f} "
              f"{m['fpr']:>8.3f} {row['n_flagged']:>10d}")
    print()

    precisions, recalls, _ = precision_recall_curve(y_val_is_crash, crash_proba)
    pr_auc = float(auc(recalls, precisions))
    print(f"Crash PR-AUC: {pr_auc:.4f}  (baseline/no-skill for this class prevalence would be "
          f"~{y_val_is_crash.mean():.3f})")
    print()

    print("=" * 78)
    print("NATIVE XGBOOST FEATURE IMPORTANCE (gain-based, top 10)")
    print("=" * 78)
    importance = booster.get_score(importance_type="gain")
    importance_sorted = sorted(importance.items(), key=lambda kv: kv[1], reverse=True)
    for name, gain in importance_sorted[:10]:
        print(f"  {name:30s} {gain:10.2f}")
    missing_features = set(FEATURE_NAMES) - set(importance.keys())
    if missing_features:
        print(f"  (never split on: {sorted(missing_features)})")
    print()

    print("=" * 78)
    print("RAW (UNCALIBRATED) CRASH-PROBABILITY RELIABILITY CHECK")
    print("=" * 78)
    print("No Platt/sigmoid calibration applied yet in this baseline (deferred")
    print("pending this first look). Bins below show whether the raw softmax")
    print("crash-probability already roughly tracks empirical crash frequency,")
    print("or whether calibration is clearly needed before this number is used")
    print("as a claims-decision gate.")
    bins = np.arange(0, 1.1, 0.1)
    bin_idx = np.digitize(crash_proba, bins) - 1
    reliability = []
    print(f"{'bin':>12} {'n':>6} {'mean_predicted':>15} {'empirical_rate':>15}")
    for b in range(len(bins) - 1):
        mask = bin_idx == b
        n = int(mask.sum())
        if n == 0:
            continue
        mean_pred = float(crash_proba[mask].mean())
        empirical_rate = float(y_val_is_crash[mask].mean())
        reliability.append({"bin": f"{bins[b]:.1f}-{bins[b + 1]:.1f}", "n": n,
                             "mean_predicted": round(mean_pred, 3), "empirical_rate": round(empirical_rate, 3)})
        print(f"{bins[b]:>5.1f}-{bins[b + 1]:<5.1f} {n:>6d} {mean_pred:>15.3f} {empirical_rate:>15.3f}")
    print()

    print("!" * 78)
    print("DISCLAIMER: all metrics above are on SYNTHETIC, procedurally generated")
    print("data (backend/ml_incident_engine/generate_synthetic_data.py). They are")
    print("a development proxy for whether the pipeline/features work — NOT a")
    print("measurement of real-world crash-detection accuracy. Do not report")
    print("these numbers as real-world performance.")
    print("!" * 78)

    return {
        "confusion_matrix": cm_df,
        "classification_report_text": report_str,
        "crash_binary_metrics": crash_metrics,
        "hard_negative_fp_rates": hard_negative_fp_rates,
        "threshold_sweep": threshold_sweep,
        "pr_auc": pr_auc,
        "feature_importance": dict(importance_sorted),
        "reliability_bins": reliability,
    }


if __name__ == "__main__":
    from .train_model import train_baseline

    result = train_baseline()
    evaluate_baseline(result["booster"], result["X_val"], result["y_val"])
