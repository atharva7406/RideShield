"""
Server-side incident-window quality assessment — Phase 4.

Deliberately independent of the client's own `window_metadata.completeness`
(see app/schemas.py's WindowMetadata): the rider app already computes a
completeness verdict on-device (rider-app/src/crash-detection/
incidentWindowCapture.ts), but the backend must never simply trust a
client-supplied quality claim for anything that feeds a safety decision —
same principle as re-scoring the raw window with ML instead of trusting a
client-computed peak_g_force/confidence pair. This module recomputes
quality from the raw samples themselves.

Three tiers, not two:
  - "insufficient": genuinely unusable (this only happens when
    ml_scoring_service.score_window() would already return None — kept
    here as a named tier so callers have one place to check it, not a
    stricter bar than the existing < 3 accel samples rule).
  - "degraded": usable but not full-quality (low sample count, low
    observed rate, missing a modality, non-monotonic timestamps). An
    Incident IS still created for a degraded window — Tier 0 already fired
    L1 on-device before this window even reached the backend, so refusing
    to create the Incident record would silently drop the case from
    escalation entirely. That would be exactly the "offline/degraded ==
    unsafe" regression the project's architecture explicitly forbids.
    Degraded windows instead get a lower decision_confidence downstream
    (see incident_decision_engine.py).
  - "good": normal case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


MIN_SAMPLES_FOR_DEGRADED_FLOOR = 10  # below this, always "degraded" regardless of rate
LOW_SAMPLING_RATE_THRESHOLD_HZ = 20.0  # mirrors rider-app's CRASH_DETECTION_CONFIG value


@dataclass
class WindowQualityResult:
    quality: str  # "good" | "degraded" | "insufficient"
    reasons: list[str] = field(default_factory=list)
    observed_accel_hz: Optional[float] = None
    accel_sample_count: int = 0
    gyro_sample_count: int = 0
    gps_sample_count: int = 0
    has_monotonic_timestamps: bool = True


def _observed_rate_hz(timestamps: list[float]) -> Optional[float]:
    if len(timestamps) < 2:
        return None
    span_ms = timestamps[-1] - timestamps[0]
    if span_ms <= 0:
        return None
    return ((len(timestamps) - 1) / span_ms) * 1000.0


def _is_monotonic(timestamps: list[float]) -> bool:
    return all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))


def assess_window_quality(
    accel_samples: list[dict],
    gyro_samples: list[dict],
    gps_samples: list[dict],
) -> WindowQualityResult:
    """Pure function — no DB/network access, safe to call on every
    submission before any ML scoring happens."""
    if len(accel_samples) < 3:
        return WindowQualityResult(
            quality="insufficient",
            reasons=["too_few_accel_samples"],
            accel_sample_count=len(accel_samples),
            gyro_sample_count=len(gyro_samples),
            gps_sample_count=len(gps_samples),
        )

    accel_t = [s["timestamp"] for s in accel_samples]
    accel_t_sorted = sorted(accel_t)
    monotonic = accel_t == accel_t_sorted
    rate = _observed_rate_hz(accel_t_sorted)

    reasons: list[str] = []
    if len(accel_samples) < MIN_SAMPLES_FOR_DEGRADED_FLOOR:
        reasons.append("low_sample_count")
    if rate is not None and rate < LOW_SAMPLING_RATE_THRESHOLD_HZ:
        reasons.append("low_sampling_rate")
    if rate is None:
        reasons.append("rate_unknown")
    if not gyro_samples:
        reasons.append("missing_gyro")
    if not gps_samples:
        reasons.append("missing_gps")
    if not monotonic:
        reasons.append("non_monotonic_timestamps")

    quality = "degraded" if reasons else "good"

    return WindowQualityResult(
        quality=quality,
        reasons=reasons,
        observed_accel_hz=rate,
        accel_sample_count=len(accel_samples),
        gyro_sample_count=len(gyro_samples),
        gps_sample_count=len(gps_samples),
        has_monotonic_timestamps=monotonic,
    )
