"""
Computes a ShiftBehaviourSummary from a completed shift's retained
telemetry samples. This is Phase 1 of the Behaviour Risk & Premium Engine
— descriptive counts and rates for future ML feature engineering, NOT a
validated insurance risk score. Do not read anything into these numbers
beyond "this many events of this type were counted this way."

THRESHOLD PROVENANCE (read before trusting or tuning these):
  hard_acceleration / hard_braking / overspeeding — mirror
  app/services/telemetry_service.py's existing per-batch RiskScore logic
  (same g-force/speed thresholds: hard_accel g>1.8, hard_braking g<0.5,
  overspeeding speed>60.0 km/h). Duplicated here rather than imported —
  same reasoning as app/services/ml_scoring_service.py duplicating
  telemetry_service.py's CRASH_THRESHOLD_G: that logic is a few inline
  lines inside a larger, working, tested ingest function, not a reusable
  exported one, and refactoring it was judged out of scope for this phase
  (Phase 1 spec: "avoid unnecessary refactors"). If you change one, check
  whether the other should change too — they're linked by comment, not by
  reference.

  sharp_turn — NEW, no equivalent exists anywhere else in this codebase.
  The on-device crash detector (rider-app/src/crash-detection/config.ts)
  has a GYRO_MAGNITUDE_THRESHOLD, but it's tuned for a single 5-second
  crash-CANDIDATE window, not general per-sample per-shift counting, and
  operates on a different (on-device, higher-rate) data stream. The
  threshold below is a first-pass constant, deliberately set well under
  the crash detector's 250 deg/s (this should catch routine sharp
  cornering, not crash-level rotation) but is NOT validated against real
  fleet data. Treat sharp_turn_count as directional, not calibrated, until
  it's checked against real rides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from app.services.distance_service import DistanceCalculationResult


class _SampleLike(Protocol):
    speed: Optional[float]
    accel_x: float
    accel_y: float
    accel_z: float
    gyro_x: float
    gyro_y: float
    gyro_z: float
    timestamp: object


HARD_ACCEL_G_THRESHOLD = 1.8
HARD_BRAKING_G_THRESHOLD = 0.5
OVERSPEED_KMH_THRESHOLD = 60.0
SHARP_TURN_GYRO_THRESHOLD_DEG_S = 100.0

GRAVITY_MS2 = 9.81
SECONDS_PER_HOUR = 3600.0


@dataclass
class BehaviourMetrics:
    sample_count: int
    average_speed: float
    max_speed: float
    hard_braking_count: int
    hard_acceleration_count: int
    overspeeding_count: int
    sharp_turn_count: int
    max_g: float
    accel_std: float
    jerk_mean: float


def compute_behaviour_metrics(samples: Sequence[_SampleLike]) -> BehaviourMetrics:
    """Order-independent except jerk_mean (computed from samples sorted by
    timestamp here, regardless of input order)."""
    if not samples:
        return BehaviourMetrics(0, 0.0, 0.0, 0, 0, 0, 0, 0.0, 0.0, 0.0)

    ordered = sorted(samples, key=lambda s: s.timestamp)

    speeds = [s.speed for s in ordered if s.speed is not None]
    g_forces = []
    hard_accel = hard_braking = overspeeding = sharp_turns = 0

    for s in ordered:
        g = math.sqrt(s.accel_x ** 2 + s.accel_y ** 2 + s.accel_z ** 2) / GRAVITY_MS2
        g_forces.append(g)

        if g > HARD_ACCEL_G_THRESHOLD:
            hard_accel += 1
        elif g < HARD_BRAKING_G_THRESHOLD:
            hard_braking += 1

        if s.speed is not None and s.speed > OVERSPEED_KMH_THRESHOLD:
            overspeeding += 1

        gyro_mag = math.sqrt(s.gyro_x ** 2 + s.gyro_y ** 2 + s.gyro_z ** 2)
        if gyro_mag > SHARP_TURN_GYRO_THRESHOLD_DEG_S:
            sharp_turns += 1

    jerks = []
    for i in range(1, len(ordered)):
        dt = (ordered[i].timestamp - ordered[i - 1].timestamp).total_seconds()
        if dt > 0:
            jerks.append(abs(g_forces[i] - g_forces[i - 1]) / dt)

    mean_g = sum(g_forces) / len(g_forces)
    variance_g = sum((g - mean_g) ** 2 for g in g_forces) / len(g_forces)

    return BehaviourMetrics(
        sample_count=len(ordered),
        average_speed=(sum(speeds) / len(speeds)) if speeds else 0.0,
        max_speed=max(speeds) if speeds else 0.0,
        hard_braking_count=hard_braking,
        hard_acceleration_count=hard_accel,
        overspeeding_count=overspeeding,
        sharp_turn_count=sharp_turns,
        max_g=max(g_forces) if g_forces else 0.0,
        accel_std=math.sqrt(variance_g),
        jerk_mean=(sum(jerks) / len(jerks)) if jerks else 0.0,
    )


def compute_hourly_rate(event_count: int, duration_seconds: float) -> float:
    """Duration-normalized, deliberately NOT distance-normalized this
    phase — see Phase 1 spec: production telemetry is ~1Hz and distance is
    only now (this same phase) being made trustworthy, so
    events/duration is the more defensible exposure denominator for now."""
    if duration_seconds <= 0:
        return 0.0
    return event_count / (duration_seconds / SECONDS_PER_HOUR)


@dataclass
class DataQualityResult:
    score: float  # 0-1
    sampling_density_score: float
    gps_validity_score: float
    gps_accuracy_score: float
    duration_coverage_score: float


# Expected minimum sampling rate used purely as a data-quality yardstick,
# NOT a claim about actual device capability — production telemetry is
# documented (backend/ml_incident_engine/config.py) as ~1Hz today, so a
# shift with close to 1 sample/second scores near-perfect density here.
EXPECTED_SAMPLES_PER_SECOND = 1.0

# Weights sum to 1.0. Deliberately simple and explainable per the Phase 1
# spec — a first-pass allocation, not fit against labeled data: having
# enough samples at all (density) matters most, GPS coordinate/accuracy
# quality next, pure duration-span coverage least (a short, dense shift is
# more useful for behaviour features than a long, sparse one).
WEIGHT_SAMPLING_DENSITY = 0.35
WEIGHT_GPS_VALIDITY = 0.25
WEIGHT_GPS_ACCURACY = 0.20
WEIGHT_DURATION_COVERAGE = 0.20


def compute_data_quality(
    samples: Sequence[_SampleLike],
    duration_seconds: float,
    distance_result: DistanceCalculationResult,
) -> DataQualityResult:
    if duration_seconds <= 0 or not samples:
        return DataQualityResult(0.0, 0.0, 0.0, 0.0, 0.0)

    expected_samples = max(1.0, duration_seconds * EXPECTED_SAMPLES_PER_SECOND)
    sampling_density_score = min(1.0, len(samples) / expected_samples)

    total_gps_considered = (
        distance_result.valid_sample_count
        + distance_result.rejected_invalid_coordinate_count
        + distance_result.rejected_poor_accuracy_count
    )
    gps_validity_score = (
        distance_result.valid_sample_count / total_gps_considered
        if total_gps_considered > 0 else 0.0
    )

    valid_coord_total = distance_result.valid_sample_count + distance_result.rejected_poor_accuracy_count
    gps_accuracy_score = (
        distance_result.valid_sample_count / valid_coord_total
        if valid_coord_total > 0 else 0.0
    )

    ordered = sorted(samples, key=lambda s: s.timestamp)
    telemetry_span_seconds = (ordered[-1].timestamp - ordered[0].timestamp).total_seconds()
    duration_coverage_score = max(0.0, min(1.0, telemetry_span_seconds / duration_seconds))

    score = (
        WEIGHT_SAMPLING_DENSITY * sampling_density_score
        + WEIGHT_GPS_VALIDITY * gps_validity_score
        + WEIGHT_GPS_ACCURACY * gps_accuracy_score
        + WEIGHT_DURATION_COVERAGE * duration_coverage_score
    )
    return DataQualityResult(
        score=max(0.0, min(1.0, score)),
        sampling_density_score=sampling_density_score,
        gps_validity_score=gps_validity_score,
        gps_accuracy_score=gps_accuracy_score,
        duration_coverage_score=duration_coverage_score,
    )


# First-pass validity thresholds, tunable — a summary below these is
# still stored (for auditability) but flagged is_valid=False so downstream
# consumers (the future rider-risk model) can filter it out.
MIN_SAMPLE_COUNT_FOR_VALID = 3
MIN_DATA_QUALITY_SCORE_FOR_VALID = 0.3


def is_summary_valid(sample_count: int, data_quality_score: float) -> bool:
    return sample_count >= MIN_SAMPLE_COUNT_FOR_VALID and data_quality_score >= MIN_DATA_QUALITY_SCORE_FOR_VALID
