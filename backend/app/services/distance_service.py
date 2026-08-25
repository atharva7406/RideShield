"""
Server-authoritative GPS distance calculation for completed shifts.

Replaces trusting client-supplied Shift.distance_km. Previously
`end_shift` (app/api/shifts.py) simply overwrote the server's own
incrementally-accumulated distance with whatever the rider app sent — and
the app currently sends a literal hardcoded 15.4 regardless of the actual
ride (rider-app/src/services/shiftService.ts). Distance is now computed
here, server-side, from the shift's own retained TelemetrySample rows at
shift-end.

LIMITATIONS (documented per the Phase 1 spec's requirement, not hidden):
  - Haversine assumes a spherical Earth; error is on the order of meters
    over city-scale distances — negligible for this use case.
  - Production telemetry currently arrives at ~1Hz, one sample per
    request (see backend/ml_incident_engine/config.py's documented
    sampling-rate gap, proven this project's crash model 0% recall at
    that resolution). A rider's true path is a curved polyline sampled
    coarsely, not smoothly tracked — this computes the sum of straight
    chords between samples, which systematically UNDER-estimates true
    distance on any route with turns between sample points. That's a
    known structural bound of sampling at this rate, not a bug here.
  - Historical shifts completed BEFORE this change shipped are NOT
    retroactively recalculated — their stored distance_km reflects
    whatever was trusted at the time (client-supplied or the old
    average-speed-based incremental estimate). Only shifts completed
    after this change get the server-authoritative value.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


class _SampleLike(Protocol):
    latitude: Optional[float]
    longitude: Optional[float]
    gps_accuracy: Optional[float]
    timestamp: object  # datetime — only ordering/subtraction is required


# A generously high upper bound for a gig-rider two-wheeler, chosen to
# reject GPS teleportation artifacts (a jump implying faster than this
# between two closely-timed samples is almost certainly a bad fix, not
# real motion) without false-rejecting genuine fast riding. Not
# empirically validated against real fleet data — a tunable constant, not
# a physical law.
MAX_PLAUSIBLE_SPEED_KMH = 120.0

# Samples reporting worse than this GPS accuracy (meters) are excluded
# from the distance calculation entirely — a poor fix can imply a large
# spurious jump even between two genuinely stationary readings.
MAX_GPS_ACCURACY_METERS = 50.0

# Beyond this time gap between consecutive valid samples, the
# implied-speed jump check is skipped entirely — a real tracking gap
# (app backgrounded, signal lost) can legitimately look like an
# impossible average speed without being a GPS error, and refusing to
# advance the reference point after every such gap would silently freeze
# distance accumulation for the rest of the shift. The segment's distance
# still isn't counted (we can't verify the path taken during an untracked
# gap), but the reference point resets so later segments aren't compared
# against an increasingly stale anchor.
MAX_GAP_SECONDS_FOR_JUMP_CHECK = 120.0

EARTH_RADIUS_KM = 6371.0088


@dataclass
class DistanceCalculationResult:
    distance_km: float
    valid_sample_count: int
    rejected_invalid_coordinate_count: int = 0
    rejected_poor_accuracy_count: int = 0
    rejected_jump_count: int = 0
    rejected_out_of_order_count: int = 0
    untracked_gap_count: int = 0


def _is_valid_coordinate(lat: Optional[float], lng: Optional[float]) -> bool:
    if lat is None or lng is None:
        return False
    if lat == 0.0 and lng == 0.0:  # common "no GPS fix" sentinel value
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def compute_distance_km(samples: Sequence[_SampleLike]) -> DistanceCalculationResult:
    """
    Sums Haversine distance across consecutive VALID sample pairs only.
    `samples` may be passed in any order — sorted here by timestamp.

    A sample is excluded entirely (not just the segment touching it) if
    its coordinates are missing/out of range, or its GPS accuracy is
    worse than MAX_GPS_ACCURACY_METERS. A segment between two otherwise-
    valid samples is rejected — distance not counted, reference point NOT
    advanced, so the next sample is compared against the same last-known-
    good point — if it implies a speed faster than MAX_PLAUSIBLE_SPEED_KMH
    within a short time gap (see MAX_GAP_SECONDS_FOR_JUMP_CHECK). Across a
    longer gap, the segment's distance still isn't counted, but the
    reference point DOES advance, to avoid freezing accumulation after a
    real tracking gap.

    Never returns a negative distance (Haversine terms are individually
    non-negative by construction; the final clamp is defensive).
    """
    result = DistanceCalculationResult(distance_km=0.0, valid_sample_count=0)
    ordered = sorted(samples, key=lambda s: s.timestamp)

    last_valid = None
    for s in ordered:
        if not _is_valid_coordinate(s.latitude, s.longitude):
            result.rejected_invalid_coordinate_count += 1
            continue
        if s.gps_accuracy is not None and s.gps_accuracy > MAX_GPS_ACCURACY_METERS:
            result.rejected_poor_accuracy_count += 1
            continue

        result.valid_sample_count += 1

        if last_valid is None:
            last_valid = s
            continue

        dt_seconds = (s.timestamp - last_valid.timestamp).total_seconds()
        if dt_seconds <= 0:
            result.rejected_out_of_order_count += 1
            continue  # don't advance the reference on a non-positive/duplicate timestamp

        segment_km = haversine_km(last_valid.latitude, last_valid.longitude, s.latitude, s.longitude)
        dt_hours = dt_seconds / 3600.0
        implied_speed_kmh = segment_km / dt_hours if dt_hours > 0 else float("inf")

        if dt_seconds > MAX_GAP_SECONDS_FOR_JUMP_CHECK:
            result.untracked_gap_count += 1
            last_valid = s  # reset reference past the gap; don't count the segment
            continue

        if implied_speed_kmh > MAX_PLAUSIBLE_SPEED_KMH:
            result.rejected_jump_count += 1
            continue  # don't advance — likely s itself is a bad fix

        result.distance_km += segment_km
        last_valid = s

    result.distance_km = max(0.0, result.distance_km)
    return result
