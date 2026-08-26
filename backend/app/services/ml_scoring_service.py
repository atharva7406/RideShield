"""
Wraps ml_incident_engine (the offline ML dev pipeline, backend/ml_incident_
engine/) for use inside the live backend. This is the ONLY file under
app/ that imports ml_incident_engine — keeps the boundary between
"offline ML dev pipeline" and "production backend" explicit and auditable,
same principle as razorpay_service.py wrapping the razorpay SDK.

FALLBACK-SAFETY CONTRACT (non-negotiable — this was the whole point of
building this as a separate, swappable scoring step rather than inlining
XGBoost calls into incidents.py directly):
  - score_window() NEVER raises for a "model unavailable" reason. If the ML
    engine can't be imported, the model file is missing, or scoring throws
    for any reason, it transparently falls back to the same G-force-
    threshold rule telemetry_service.py's ingest path already uses —
    computed from THIS window's own data, never from client-supplied
    numbers. The ML layer must never be a single point of failure for
    crash detection.
  - It only returns None when there truly isn't enough data to compute
    anything at all (fewer than 3 accel samples) — callers should treat
    that as a client error (422), not as "not a crash".
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Mirrors app/services/telemetry_service.py's CRASH_THRESHOLD_G rule —
# duplicated (not imported) because telemetry_service.py's version is a
# few inline lines, not a reusable function; kept in sync by comment, not
# by reference, so a future edit to one won't silently desync the other
# without a code reviewer noticing the doubled comment.
_RULE_CRASH_THRESHOLD_G = 4.0

_ml_incident_engine_available = True
try:
    from ml_incident_engine.feature_extraction import extract_feature_vector
    from ml_incident_engine.generate_synthetic_data import TelemetryWindow
    from ml_incident_engine.predict import load_booster, predict_from_features
except Exception as e:  # pragma: no cover - defensive import guard
    _ml_incident_engine_available = False
    logger.warning(f"ml_incident_engine unavailable, will always use rule-based fallback: {e}")

_booster = None


def _get_booster():
    global _booster
    if _booster is None:
        _booster = load_booster()
    return _booster


def is_ml_available() -> bool:
    """True only if the engine imported AND a trained model file actually
    loads. Checked fresh each call (not cached as a hard failure) so a
    model file added after backend startup gets picked up without a
    restart — but the loaded booster itself IS cached, so this is cheap
    after the first successful load."""
    if not _ml_incident_engine_available:
        return False
    try:
        _get_booster()
        return True
    except Exception as e:
        logger.warning(f"ML model failed to load, will use rule-based fallback: {e}")
        return False


def _build_window(shift_id: str, accel_samples: list[dict], gyro_samples: list[dict],
                   gps_samples: list[dict]) -> "TelemetryWindow":
    accel_t = np.array([s["timestamp"] for s in accel_samples], dtype=float)
    gyro_t = np.array([s["timestamp"] for s in gyro_samples], dtype=float) if gyro_samples else accel_t.copy()

    if gps_samples:
        gps_t = np.array([s["timestamp"] for s in gps_samples], dtype=float)
        gps_lat = np.array([s["latitude"] for s in gps_samples], dtype=float)
        gps_lng = np.array([s["longitude"] for s in gps_samples], dtype=float)
        gps_speed = np.array([s["speed"] for s in gps_samples], dtype=float)
        gps_altitude = np.array([s.get("altitude") if s.get("altitude") is not None else np.nan for s in gps_samples], dtype=float)
        gps_accuracy = np.array([s.get("accuracy") if s.get("accuracy") is not None else np.nan for s in gps_samples], dtype=float)
    else:
        gps_t = gps_lat = gps_lng = gps_speed = gps_altitude = gps_accuracy = np.array([], dtype=float)

    return TelemetryWindow(
        event_id=f"{shift_id}-live",
        rider_id=shift_id,
        shift_id=shift_id,
        class_label="unknown",  # live scoring, not a labeled training window
        is_augmented=False,
        source_event_id=f"{shift_id}-live",
        accel_t_ms=accel_t,
        accel_x=np.array([s["x"] for s in accel_samples], dtype=float),
        accel_y=np.array([s["y"] for s in accel_samples], dtype=float),
        accel_z=np.array([s["z"] for s in accel_samples], dtype=float),
        gyro_t_ms=gyro_t,
        gyro_x=np.array([s["x"] for s in gyro_samples], dtype=float) if gyro_samples else np.array([]),
        gyro_y=np.array([s["y"] for s in gyro_samples], dtype=float) if gyro_samples else np.array([]),
        gyro_z=np.array([s["z"] for s in gyro_samples], dtype=float) if gyro_samples else np.array([]),
        gps_t_ms=gps_t,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        gps_speed_kmh=gps_speed,
        gps_altitude=gps_altitude,
        gps_accuracy=gps_accuracy,
    )


def _rule_based_fallback(peak_g_force: float) -> float:
    """Same formula as telemetry_service.py's ingest-time check — see
    module docstring on why this is duplicated rather than imported."""
    if peak_g_force >= _RULE_CRASH_THRESHOLD_G:
        return min(0.95, 0.5 + (peak_g_force - _RULE_CRASH_THRESHOLD_G) / 10.0)
    return max(0.0, (peak_g_force / _RULE_CRASH_THRESHOLD_G) * 0.5)


def score_window(
    shift_id: str,
    accel_samples: list[dict],
    gyro_samples: list[dict],
    gps_samples: list[dict],
) -> Optional[dict]:
    """Returns {method: "ml"|"rule_based_fallback", peak_g_force,
    confidence_score, predicted_class, post_impact_stillness, speed_drop,
    jerk_peak, peak_to_baseline_ratio}, or None if there's truly not enough
    data (fewer than 3 accel samples) to compute anything — callers must
    treat None as a client error, not as "not a crash".

    The four supporting-evidence fields (Phase 4 — Incident Decision
    Engine) were already being computed internally as ML input features
    and simply discarded before this phase; they're now surfaced so
    incident_decision_engine.py can fuse them with the ML score instead of
    treating confidence_score as the only signal. All four are None when
    `features` couldn't be computed at all (the crude no-engine fallback
    below) — never fabricated.
    """
    if len(accel_samples) < 3:
        return None

    try:
        window = _build_window(shift_id, accel_samples, gyro_samples, gps_samples)
        features = extract_feature_vector(window) if _ml_incident_engine_available else None
    except Exception as e:
        logger.error(f"Feature extraction failed for shift {shift_id}: {e}")
        features = None

    if features is None:
        # Can't even compute the rule-based peak-G fallback without the
        # engine's magnitude helper — degrade to the crudest possible
        # signal so this endpoint still returns *something* rather than
        # 500ing the rider's crash report.
        peak_g_force = _peak_g_force_without_engine(accel_samples)
        return {
            "method": "rule_based_fallback",
            "peak_g_force": peak_g_force,
            "confidence_score": _rule_based_fallback(peak_g_force),
            "predicted_class": None,
            "post_impact_stillness": None,
            "speed_drop": None,
            "jerk_peak": None,
            "peak_to_baseline_ratio": None,
        }

    peak_g_force = float(features["accel_peak_g"])
    evidence_fields = {
        "post_impact_stillness": bool(features["post_impact_stillness"]),
        "speed_drop": features["speed_drop"],
        "jerk_peak": float(features["jerk_peak"]),
        "peak_to_baseline_ratio": float(features["peak_to_baseline_ratio"]),
    }

    if is_ml_available():
        try:
            result = predict_from_features(features, booster=_get_booster())
            return {
                "method": "ml",
                "peak_g_force": peak_g_force,
                "confidence_score": result["crash_probability"],
                "predicted_class": result["predicted_class"],
                **evidence_fields,
            }
        except Exception as e:
            logger.warning(f"ML scoring failed for shift {shift_id}, falling back to rule engine: {e}")

    return {
        "method": "rule_based_fallback",
        "peak_g_force": peak_g_force,
        "confidence_score": _rule_based_fallback(peak_g_force),
        "predicted_class": None,
        **evidence_fields,
    }


def _peak_g_force_without_engine(accel_samples: list[dict]) -> float:
    """Last-resort peak-G computation with no ml_incident_engine import at
    all — used only if that module itself failed to import (e.g. numpy
    missing in some future stripped-down deployment)."""
    gravity = 9.81
    peak = 0.0
    for s in accel_samples:
        mag = (s["x"] ** 2 + s["y"] ** 2 + s["z"] ** 2) ** 0.5
        peak = max(peak, mag / gravity)
    return peak
