"""
Evaluates the trained baseline model against externally-supplied telemetry
CSVs — NOT part of the Phase 1-4 pipeline proper, and NOT a real-world
validation. Treat results from this script as "does the model generalize
to a different synthetic generation process," nothing stronger.

Three files were supplied, in three different schemas and at three
different (all lower than training) sample rates:

  telemetry_crash_detection.csv   1Hz,  190 shifts, 61,704 rows,
                                   columns: accel_x/y/z, gyro_x/y/z, speed,
                                   lat/lng/altitude/gps_accuracy, timestamp
                                   (ISO8601), label, event_type, shift_id.
                                   Units already match this project's
                                   schema (gyro deg/s, speed km/h).

  crash_training_data.csv         10Hz, single ~20s sequence, 200 rows,
                                   no group id.
  full_ml_training_data.csv       10Hz, 1000 rides, 355,498 rows,
                                   columns: timestamp (epoch ms), accel_x/
                                   y/z, gyro_x/y/z, speed, lat/lng/altitude/
                                   gps_accuracy, label, risk_score, ride_id.
                                   Same schema/generation family as
                                   crash_training_data.csv. UNIT MISMATCH
                                   found by inspection (see module-level
                                   checks in the session this was built in,
                                   not re-derived here): gyro is in
                                   RADIANS/second (normal-riding gyro
                                   magnitude mean 0.16 only makes sense as
                                   rad/s -> ~9 deg/s; crash-labeled mean
                                   3.71 rad/s -> ~212 deg/s, which lands
                                   exactly where this project's crash class
                                   expects it) and speed is in METERS/
                                   SECOND (normal-riding mean 9.75 -> only
                                   makes sense as ~35 km/h, not 9.75 km/h
                                   which would be slower than a bicycle).
                                   Converted below; if that inference is
                                   wrong, every number this script reports
                                   for these two files is wrong too — this
                                   is a real risk, not just a formality,
                                   and is called out again in the printed
                                   report.

CRITICAL CAVEATS (also printed at the end of every run):
  - ALL THREE files sample slower than this project's 50Hz training
    assumption (1Hz / 10Hz vs. 50Hz) — exactly the sampling-rate gap
    documented in config.py. Features computed from sparser windows are
    expected to be noisier/less resolved than what the model was trained
    on, independent of anything else.
  - None of these are confirmed real-world data. crash_training_data.csv
    in particular contains an obviously hand-injected crash spike (exact
    round numbers: accel_x=30.0, -80.0 etc., unlike every other organic-
    looking value in the file) — likely itself synthetic.
  - These files' own labels are binary (crash / not-crash) with no
    equivalent of this project's hard_braking/pothole/sharp_turn/normal
    split. Comparisons below collapse the model's 5-class prediction to
    binary (predicted crash vs. not) to match.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import model_config as mcfg
from .feature_extraction import extract_feature_vector
from .generate_synthetic_data import TelemetryWindow
from .predict import load_booster, predict_from_features

WINDOW_S = 5.0
WINDOW_MS = WINDOW_S * 1000
RAD_TO_DEG = 180.0 / np.pi


def _windows_from_group(df: pd.DataFrame, group_key: str) -> list[TelemetryWindow]:
    """Non-overlapping (tumbling) WINDOW_S-second windows over one group's
    samples, sorted by timestamp. A window's ground-truth label is "crash"
    if ANY sample inside it has label==1, else "not crash". Windows with
    fewer than 3 samples are skipped (too little data for feature
    extraction to mean anything, e.g. compute_post_impact_stillness needs
    >= 3)."""
    df = df.sort_values("timestamp_ms").reset_index(drop=True)
    if df.empty:
        return []
    t0 = df["timestamp_ms"].iloc[0]
    t_end = df["timestamp_ms"].iloc[-1]

    windows = []
    start = t0
    idx = 0
    while start <= t_end:
        sub = df[(df["timestamp_ms"] >= start) & (df["timestamp_ms"] < start + WINDOW_MS)]
        if len(sub) >= 3:
            t = sub["timestamp_ms"].to_numpy(dtype=float)
            w = TelemetryWindow(
                event_id=f"{group_key}-w{idx}",
                rider_id=str(group_key),
                shift_id=str(group_key),
                class_label="unknown",  # ground truth is binary, doesn't map to the 5-class taxonomy
                is_augmented=False,
                source_event_id=f"{group_key}-w{idx}",
                accel_t_ms=t,
                accel_x=sub["accel_x"].to_numpy(dtype=float),
                accel_y=sub["accel_y"].to_numpy(dtype=float),
                accel_z=sub["accel_z"].to_numpy(dtype=float),
                gyro_t_ms=t.copy(),
                gyro_x=sub["gyro_x"].to_numpy(dtype=float),
                gyro_y=sub["gyro_y"].to_numpy(dtype=float),
                gyro_z=sub["gyro_z"].to_numpy(dtype=float),
                gps_t_ms=t.copy(),
                gps_lat=sub.get("latitude", pd.Series(np.zeros(len(sub)))).to_numpy(dtype=float),
                gps_lng=sub.get("longitude", pd.Series(np.zeros(len(sub)))).to_numpy(dtype=float),
                gps_speed_kmh=sub["speed_kmh"].to_numpy(dtype=float),
                gps_altitude=sub.get("altitude", pd.Series(np.zeros(len(sub)))).to_numpy(dtype=float),
                gps_accuracy=sub.get("gps_accuracy", pd.Series(np.full(len(sub), np.nan))).to_numpy(dtype=float),
            )
            windows.append((w, bool(sub["label"].any())))
            idx += 1
        start += WINDOW_MS
    return windows


def _evaluate_windows(windows_with_labels: list[tuple[TelemetryWindow, bool]], booster) -> dict:
    y_true, y_pred, crash_proba = [], [], []
    for window, true_is_crash in windows_with_labels:
        features = extract_feature_vector(window)
        result = predict_from_features(features, booster=booster)
        y_true.append(int(true_is_crash))
        y_pred.append(int(result["predicted_class"] == "crash"))
        crash_proba.append(result["crash_probability"])

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    crash_proba = np.array(crash_proba)

    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    return {
        "n_windows": len(y_true), "n_true_crash": int(y_true.sum()), "n_true_not_crash": int((1 - y_true).sum()),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1, "fpr": fpr,
        "mean_crash_proba_when_true_crash": float(crash_proba[y_true == 1].mean()) if y_true.sum() else None,
        "mean_crash_proba_when_true_normal": float(crash_proba[y_true == 0].mean()) if (1 - y_true).sum() else None,
    }


def _print_report(name: str, result: dict) -> None:
    print("=" * 78)
    print(f"EXTERNAL CSV: {name}")
    print("=" * 78)
    print(f"windows evaluated: {result['n_windows']}  "
          f"(true crash: {result['n_true_crash']}, true not-crash: {result['n_true_not_crash']})")
    print(f"TP={result['tp']}  FP={result['fp']}  FN={result['fn']}  TN={result['tn']}")
    print(f"Precision={result['precision']:.3f}  Recall={result['recall']:.3f}  "
          f"F1={result['f1']:.3f}  FPR={result['fpr']:.3f}")
    if result["mean_crash_proba_when_true_crash"] is not None:
        print(f"Mean predicted crash_probability | true crash:     {result['mean_crash_proba_when_true_crash']:.3f}")
    if result["mean_crash_proba_when_true_normal"] is not None:
        print(f"Mean predicted crash_probability | true not-crash: {result['mean_crash_proba_when_true_normal']:.3f}")
    print()


# ---------------------------------------------------------------------------
# Per-file adapters
# ---------------------------------------------------------------------------


def load_crash_training_family(path: str | Path) -> list[tuple[TelemetryWindow, bool]]:
    """crash_training_data.csv / full_ml_training_data.csv shared schema.
    Converts gyro rad/s -> deg/s and speed m/s -> km/h (see module
    docstring for why)."""
    df = pd.read_csv(path)
    df["timestamp_ms"] = df["timestamp"].astype(float)
    df["gyro_x"] = df["gyro_x"].astype(float) * RAD_TO_DEG
    df["gyro_y"] = df["gyro_y"].astype(float) * RAD_TO_DEG
    df["gyro_z"] = df["gyro_z"].astype(float) * RAD_TO_DEG
    df["speed_kmh"] = df["speed"].astype(float) * 3.6
    df["label"] = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype(int)

    group_col = "ride_id" if "ride_id" in df.columns else None
    all_windows: list[tuple[TelemetryWindow, bool]] = []
    if group_col:
        for group_key, group_df in df.groupby(group_col):
            all_windows.extend(_windows_from_group(group_df, str(group_key)))
    else:
        all_windows.extend(_windows_from_group(df, "single-sequence"))
    return all_windows


def load_telemetry_crash_detection(path: str | Path) -> list[tuple[TelemetryWindow, bool]]:
    """telemetry_crash_detection.csv — already in this project's units
    (gyro deg/s, speed km/h), ISO8601 timestamps, 1Hz."""
    df = pd.read_csv(path)
    df["timestamp_ms"] = (pd.to_datetime(df["timestamp"], utc=True).astype("int64") // 1_000_000).astype(float)
    df["speed_kmh"] = df["speed"].astype(float)
    df["label"] = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype(int)

    all_windows: list[tuple[TelemetryWindow, bool]] = []
    for group_key, group_df in df.groupby("shift_id"):
        all_windows.extend(_windows_from_group(group_df, str(group_key)))
    return all_windows


def main(paths: dict[str, str]) -> dict:
    booster = load_booster()
    results = {}

    if "crash_training_data" in paths:
        windows = load_crash_training_family(paths["crash_training_data"])
        result = _evaluate_windows(windows, booster)
        _print_report("crash_training_data.csv (10Hz, single sequence, unit-converted)", result)
        results["crash_training_data"] = result

    if "full_ml_training_data" in paths:
        windows = load_crash_training_family(paths["full_ml_training_data"])
        result = _evaluate_windows(windows, booster)
        _print_report("full_ml_training_data.csv (10Hz, 1000 rides, unit-converted)", result)
        results["full_ml_training_data"] = result

    if "telemetry_crash_detection" in paths:
        windows = load_telemetry_crash_detection(paths["telemetry_crash_detection"])
        result = _evaluate_windows(windows, booster)
        _print_report("telemetry_crash_detection.csv (1Hz, 190 shifts, native units)", result)
        results["telemetry_crash_detection"] = result

    print("!" * 78)
    print("CAVEATS — read before drawing any conclusion from the numbers above:")
    print("  1. ALL THREE files sample slower than this model's 50Hz training")
    print("     assumption (1Hz / 10Hz here vs. 50Hz). Degraded feature quality")
    print("     (jerk, variance, stillness) is expected independent of anything else.")
    print("  2. None of these are confirmed real-world data. crash_training_data.csv")
    print("     contains an obviously hand-injected crash spike (exact round-number")
    print("     accel values) unlike the rest of that file's organic-looking noise.")
    print("  3. gyro-unit (rad/s->deg/s) and speed-unit (m/s->km/h) conversions for")
    print("     the crash_training_data/full_ml_training_data family were INFERRED")
    print("     from magnitude statistics, not confirmed against a data dictionary —")
    print("     if that inference is wrong, every number reported for those two")
    print("     files is wrong too.")
    print("  4. Ground truth here is binary (crash/not-crash); the model's 5-class")
    print("     prediction is collapsed to binary (predicted=='crash') to compare —")
    print("     a 'not-crash' miss could be a real hard_braking/pothole/sharp_turn")
    print("     false positive OR a genuine binary error, this script can't tell")
    print("     which from these files' labels alone.")
    print("  5. This is a generalization check against a DIFFERENT synthetic")
    print("     generation process, not a real-world validation.")
    print("!" * 78)

    return results


if __name__ == "__main__":
    default_paths = {
        "telemetry_crash_detection": r"C:\Users\Mohit Madke\Downloads\telemetry_crash_detection.csv",
        "crash_training_data": r"C:\Users\Mohit Madke\Downloads\crash_training_data.csv",
        "full_ml_training_data": r"C:\Users\Mohit Madke\Downloads\full_ml_training_data.csv",
    }
    main(default_paths)
