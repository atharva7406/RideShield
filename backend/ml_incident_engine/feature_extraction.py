"""
Window -> feature vector.

`compute_features_ts_parity()` is a direct port of
rider-app/src/crash-detection/featureExtraction.ts's `computeFeatures()` —
same formulas, same edge cases, verified against the same numeric examples
used in that file's own test suite
(rider-app/src/crash-detection/__tests__/featureExtraction.test.ts). See
tests/test_feature_extraction.py, which ports those exact test cases.

Everything else here (`compute_extended_features`) is new to this Python
pipeline — features requested for the ML model beyond what the on-device
rule engine needs. They're kept in a clearly separate function so it's
always obvious which numbers have a TS equivalent to stay in sync with, and
which don't.

No feature weights are chosen or combined into a score anywhere in this
file — that is explicitly deferred to model training (Phase 3) and the
Incident Decision Engine (Phase 5), per the project's own instruction not
to hand-pick feature weights.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from . import config as cfg
from .generate_synthetic_data import TelemetryWindow


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------


def _magnitude(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    return np.sqrt(x ** 2 + y ** 2 + z ** 2)


def _population_variance(values: np.ndarray) -> float:
    """Matches the TS helper's `mean((v - mean)^2)` definition, i.e.
    numpy's default (ddof=0) variance."""
    if len(values) < 2:
        return 0.0
    return float(np.var(values))


# ---------------------------------------------------------------------------
# TS-parity feature functions
# ---------------------------------------------------------------------------


def _jerk_series(accel_mag: np.ndarray, accel_t_ms: np.ndarray) -> np.ndarray:
    """Instantaneous |delta(accel magnitude) / delta(t)| at each step.
    `compute_jerk_peak` (TS-parity) and `jerk_mean` (extension) are both
    derived from this same series so they can't silently drift apart."""
    if len(accel_mag) < 2:
        return np.array([])
    dt_sec = np.diff(accel_t_ms) / 1000.0
    d_mag = np.abs(np.diff(accel_mag))
    valid = dt_sec > 0
    if not np.any(valid):
        return np.array([])
    return d_mag[valid] / dt_sec[valid]


def compute_jerk_peak(accel_mag: np.ndarray, accel_t_ms: np.ndarray) -> float:
    """TS-parity: matches computeJerk() in featureExtraction.ts exactly
    (max |delta magnitude / delta t| over the window)."""
    series = _jerk_series(accel_mag, accel_t_ms)
    return float(series.max()) if len(series) else 0.0


def compute_speed_drop(gps_speed_kmh: np.ndarray, gps_t_ms: np.ndarray,
                        anchor_timestamp_ms: Optional[float]) -> Optional[float]:
    """TS-parity port of computeSpeedDrop() in featureExtraction.ts.

    Finds the fastest speed in a window around `anchor_timestamp_ms`
    (defaulting to the last GPS sample if no anchor is given), then the
    slowest speed *after* that peak. Anchoring to the accel-peak timestamp
    (rather than "now") is deliberate in the original TS code — see its
    docstring — and preserved here unchanged.
    """
    if len(gps_speed_kmh) < 2:
        return None

    anchor = anchor_timestamp_ms if anchor_timestamp_ms is not None else float(gps_t_ms[-1])
    window_start = anchor - cfg.SPEED_DROP_WINDOW_MS / 2
    window_end = anchor + cfg.SPEED_DROP_WINDOW_MS

    mask = (gps_t_ms >= window_start) & (gps_t_ms <= window_end)
    window_speeds = gps_speed_kmh[mask]
    if len(window_speeds) < 2:
        return None

    max_speed_index = int(np.argmax(window_speeds))
    max_speed = float(window_speeds[max_speed_index])
    after_peak = window_speeds[max_speed_index:]
    min_speed_after = float(after_peak.min())

    return max_speed - min_speed_after


def compute_post_impact_stillness(accel_mag: np.ndarray, accel_t_ms: np.ndarray) -> bool:
    """TS-parity port of computePostImpactStillness() in
    featureExtraction.ts. Deliberately conservative: returns False (not a
    guess) when there isn't enough post-peak data yet, exactly like the
    original."""
    if len(accel_mag) < 3:
        return False

    peak_index = int(np.argmax(accel_mag))
    after_peak_mag = accel_mag[peak_index + 1:]
    after_peak_t = accel_t_ms[peak_index + 1:]
    if len(after_peak_mag) == 0:
        return False

    span_ms = after_peak_t[-1] - after_peak_t[0]
    if span_ms < cfg.MIN_STILLNESS_DATA_MS:
        return False

    relevant_mask = after_peak_t <= (after_peak_t[0] + cfg.STILLNESS_WINDOW_MS)
    relevant = after_peak_mag[relevant_mask]
    return _population_variance(relevant) < cfg.STILLNESS_ACCEL_VARIANCE_THRESHOLD


def compute_features_ts_parity(
    accel_mag: np.ndarray, accel_gforce: np.ndarray, accel_t_ms: np.ndarray,
    gyro_mag: np.ndarray,
    gps_speed_kmh: np.ndarray, gps_t_ms: np.ndarray,
) -> dict:
    """Direct port of computeFeatures() in featureExtraction.ts. Field
    names match the TS FeatureSet interface, snake_cased."""
    accel_peak = float(accel_mag.max()) if len(accel_mag) else 0.0
    accel_peak_g = float(accel_gforce.max()) if len(accel_gforce) else 0.0
    accel_magnitude_latest = float(accel_mag[-1]) if len(accel_mag) else 0.0

    accel_peak_timestamp: Optional[float] = None
    peak_to_baseline_ratio = 0.0
    if len(accel_gforce):
        peak_g_idx = int(np.argmax(accel_gforce))
        baseline_samples = np.delete(accel_gforce, peak_g_idx)
        baseline_g = float(baseline_samples.mean()) if len(baseline_samples) else (accel_peak_g or 1.0)
        peak_to_baseline_ratio = accel_peak_g / max(baseline_g, 0.05)
        accel_peak_timestamp = float(accel_t_ms[peak_g_idx])

    gyro_magnitude_latest = float(gyro_mag[-1]) if len(gyro_mag) else 0.0
    gyro_peak = float(gyro_mag.max()) if len(gyro_mag) else 0.0
    gyro_variance = _population_variance(gyro_mag)

    return {
        "accel_magnitude": accel_magnitude_latest,
        "accel_peak": accel_peak,
        "accel_peak_g": accel_peak_g,
        "jerk_peak": compute_jerk_peak(accel_mag, accel_t_ms),
        "gyro_magnitude": gyro_magnitude_latest,
        "gyro_peak": gyro_peak,
        "gyro_variance": gyro_variance,
        "peak_to_baseline_ratio": peak_to_baseline_ratio,
        "speed_drop": compute_speed_drop(gps_speed_kmh, gps_t_ms, accel_peak_timestamp),
        "post_impact_stillness": compute_post_impact_stillness(accel_mag, accel_t_ms),
        "_accel_peak_timestamp_ms": accel_peak_timestamp,  # internal, used by extended features below
    }


# ---------------------------------------------------------------------------
# Extension features (no TS equivalent)
# ---------------------------------------------------------------------------


def _post_impact_window(mag: np.ndarray, t_ms: np.ndarray, anchor_ms: Optional[float]) -> Optional[np.ndarray]:
    """Samples within STILLNESS_WINDOW_MS after `anchor_ms`, or None if
    there isn't at least MIN_STILLNESS_DATA_MS worth of span."""
    if anchor_ms is None or len(mag) == 0:
        return None
    mask = (t_ms > anchor_ms) & (t_ms <= anchor_ms + cfg.STILLNESS_WINDOW_MS)
    if not np.any(mask):
        return None
    windowed_t = t_ms[mask]
    if (windowed_t[-1] - windowed_t[0]) < cfg.MIN_STILLNESS_DATA_MS and len(windowed_t) < 2:
        return None
    return mag[mask]


def compute_duration_abnormal_motion_ms(accel_gforce: np.ndarray, accel_t_ms: np.ndarray,
                                         ratio_threshold: float = cfg.ABNORMAL_MOTION_BASELINE_RATIO) -> float:
    """Total timespan (first to last abnormal sample) where acceleration
    stays above `ratio_threshold` times the window's own baseline
    (mean excluding the single peak sample, same baseline definition as
    peak_to_baseline_ratio). 0.0 if nothing crosses the threshold."""
    if len(accel_gforce) < 2:
        return 0.0
    peak_idx = int(np.argmax(accel_gforce))
    baseline_samples = np.delete(accel_gforce, peak_idx)
    baseline_g = float(baseline_samples.mean()) if len(baseline_samples) else 1.0
    threshold = max(baseline_g, 0.05) * ratio_threshold

    above = np.where(accel_gforce > threshold)[0]
    if len(above) == 0:
        return 0.0
    return float(accel_t_ms[above[-1]] - accel_t_ms[above[0]])


def compute_accel_gyro_correlation(accel_mag: np.ndarray, gyro_mag: np.ndarray) -> Optional[float]:
    """Pearson correlation between the accel-magnitude and gyro-magnitude
    series. Requires equal-length, aligned series (true for our synthetic
    windows, both sampled at ACCEL_GYRO_SAMPLE_RATE_HZ off the same clock)
    and non-zero variance in both; returns None otherwise rather than NaN."""
    if len(accel_mag) != len(gyro_mag) or len(accel_mag) < 2:
        return None
    if np.std(accel_mag) == 0 or np.std(gyro_mag) == 0:
        return None
    corr = float(np.corrcoef(accel_mag, gyro_mag)[0, 1])
    return corr if np.isfinite(corr) else None


def compute_extended_features(
    accel_mag: np.ndarray, accel_gforce: np.ndarray, accel_t_ms: np.ndarray,
    gyro_mag: np.ndarray,
    gps_speed_kmh: np.ndarray, gps_t_ms: np.ndarray,
    gps_accuracy: np.ndarray,
    accel_peak_timestamp_ms: Optional[float],
) -> dict:
    accel_mean = float(accel_mag.mean()) if len(accel_mag) else 0.0
    accel_std = float(accel_mag.std()) if len(accel_mag) else 0.0

    jerk_series = _jerk_series(accel_mag, accel_t_ms)
    jerk_mean = float(jerk_series.mean()) if len(jerk_series) else 0.0

    speed_before: Optional[float] = None
    speed_after: Optional[float] = None
    if accel_peak_timestamp_ms is not None and len(gps_speed_kmh):
        before_mask = gps_t_ms <= accel_peak_timestamp_ms
        after_mask = gps_t_ms > accel_peak_timestamp_ms
        if np.any(before_mask):
            speed_before = float(gps_speed_kmh[before_mask].max())
        if np.any(after_mask):
            speed_after = float(gps_speed_kmh[after_mask].min())

    post_accel = _post_impact_window(accel_mag, accel_t_ms, accel_peak_timestamp_ms)
    post_impact_accel_variance = _population_variance(post_accel) if post_accel is not None else None

    post_gyro = _post_impact_window(gyro_mag, accel_t_ms, accel_peak_timestamp_ms)
    post_impact_gyro_variance = _population_variance(post_gyro) if post_gyro is not None else None

    return {
        "accel_mean": accel_mean,
        "accel_std": accel_std,
        "jerk_mean": jerk_mean,
        "speed_before": speed_before,
        "speed_after": speed_after,
        "post_impact_accel_variance": post_impact_accel_variance,
        "post_impact_gyro_variance": post_impact_gyro_variance,
        "duration_abnormal_motion_ms": compute_duration_abnormal_motion_ms(accel_gforce, accel_t_ms),
        "gps_accuracy_mean": float(gps_accuracy.mean()) if len(gps_accuracy) else None,
        "accel_gyro_correlation": compute_accel_gyro_correlation(accel_mag, gyro_mag),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_feature_vector(window: TelemetryWindow) -> dict:
    """The full named feature vector for one window: TS-parity features
    plus extensions. This is the only function dataset.py calls."""
    accel_mag = _magnitude(window.accel_x, window.accel_y, window.accel_z)
    accel_gforce = accel_mag / cfg.GRAVITY_MS2
    gyro_mag = _magnitude(window.gyro_x, window.gyro_y, window.gyro_z)

    ts_parity = compute_features_ts_parity(
        accel_mag, accel_gforce, window.accel_t_ms,
        gyro_mag,
        window.gps_speed_kmh, window.gps_t_ms,
    )
    accel_peak_timestamp_ms = ts_parity.pop("_accel_peak_timestamp_ms")

    extended = compute_extended_features(
        accel_mag, accel_gforce, window.accel_t_ms,
        gyro_mag,
        window.gps_speed_kmh, window.gps_t_ms,
        window.gps_accuracy,
        accel_peak_timestamp_ms,
    )

    return {**ts_parity, **extended}


FEATURE_NAMES = [
    "accel_magnitude", "accel_peak", "accel_peak_g", "jerk_peak",
    "gyro_magnitude", "gyro_peak", "gyro_variance", "peak_to_baseline_ratio",
    "speed_drop", "post_impact_stillness",
    "accel_mean", "accel_std", "jerk_mean", "speed_before", "speed_after",
    "post_impact_accel_variance", "post_impact_gyro_variance",
    "duration_abnormal_motion_ms", "gps_accuracy_mean", "accel_gyro_correlation",
]
