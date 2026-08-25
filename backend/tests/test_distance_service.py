import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.services import distance_service


@dataclass
class FakeGpsSample:
    timestamp: datetime
    latitude: Optional[float]
    longitude: Optional[float]
    gps_accuracy: Optional[float] = 5.0


BASE_T = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _t(seconds: float) -> datetime:
    return BASE_T + timedelta(seconds=seconds)


class TestHaversineKm:
    def test_known_one_degree_latitude_distance(self):
        # ~111.19 km per degree of latitude on the sphere this project uses.
        d = distance_service.haversine_km(0.0, 0.0, 1.0, 0.0)
        assert d == pytest.approx(111.19, abs=0.1)

    def test_zero_distance_for_identical_points(self):
        assert distance_service.haversine_km(19.076, 72.877, 19.076, 72.877) == pytest.approx(0.0, abs=1e-9)

    def test_distance_is_symmetric(self):
        d1 = distance_service.haversine_km(19.076, 72.877, 19.10, 72.90)
        d2 = distance_service.haversine_km(19.10, 72.90, 19.076, 72.877)
        assert d1 == pytest.approx(d2)


class TestComputeDistanceKm:
    def test_two_valid_points(self):
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777),
            FakeGpsSample(_t(10), 19.0770, 72.8787),
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.distance_km > 0
        assert result.valid_sample_count == 2
        assert result.rejected_jump_count == 0

    def test_stationary_rider_near_zero_distance(self):
        samples = [FakeGpsSample(_t(i), 19.0760, 72.8777) for i in range(0, 30, 5)]
        result = distance_service.compute_distance_km(samples)
        assert result.distance_km == pytest.approx(0.0, abs=1e-6)

    def test_multiple_points_sum_matches_individual_segments(self):
        points = [(19.0760, 72.8777), (19.0770, 72.8787), (19.0780, 72.8800), (19.0790, 72.8810)]
        samples = [FakeGpsSample(_t(i * 10), lat, lng) for i, (lat, lng) in enumerate(points)]
        result = distance_service.compute_distance_km(samples)

        expected = sum(
            distance_service.haversine_km(*points[i], *points[i + 1])
            for i in range(len(points) - 1)
        )
        assert result.distance_km == pytest.approx(expected, rel=1e-6)

    def test_samples_out_of_order_are_sorted_first(self):
        # Same points as above but shuffled input order.
        s1 = FakeGpsSample(_t(0), 19.0760, 72.8777)
        s2 = FakeGpsSample(_t(10), 19.0770, 72.8787)
        forward = distance_service.compute_distance_km([s1, s2])
        shuffled = distance_service.compute_distance_km([s2, s1])
        assert forward.distance_km == pytest.approx(shuffled.distance_km)

    def test_missing_gps_none_coordinates_excluded(self):
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777),
            FakeGpsSample(_t(10), None, None),
            FakeGpsSample(_t(20), 19.0780, 72.8800),
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.rejected_invalid_coordinate_count == 1
        assert result.valid_sample_count == 2

    def test_null_island_sentinel_excluded(self):
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777),
            FakeGpsSample(_t(10), 0.0, 0.0),
            FakeGpsSample(_t(20), 19.0780, 72.8800),
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.rejected_invalid_coordinate_count == 1

    def test_out_of_range_coordinates_excluded(self):
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777),
            FakeGpsSample(_t(10), 95.0, 200.0),  # invalid lat/lng range
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.rejected_invalid_coordinate_count == 1

    def test_poor_gps_accuracy_excluded(self):
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777, gps_accuracy=5.0),
            FakeGpsSample(_t(10), 19.0770, 72.8787, gps_accuracy=500.0),  # way beyond threshold
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.rejected_poor_accuracy_count == 1
        assert result.valid_sample_count == 1

    def test_impossible_gps_jump_rejected(self):
        # ~100km apart within 10 seconds -> ~36,000 km/h, nowhere near plausible.
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777),
            FakeGpsSample(_t(10), 20.0000, 73.8000),
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.rejected_jump_count == 1
        assert result.distance_km == pytest.approx(0.0, abs=1e-9)

    def test_jump_rejection_does_not_advance_reference_point(self):
        # A single bad fix in the middle shouldn't poison later legitimate segments.
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777),
            FakeGpsSample(_t(10), 25.0000, 80.0000),  # bad fix, rejected
            FakeGpsSample(_t(20), 19.0770, 72.8787),  # legitimate, close to sample 1
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.rejected_jump_count >= 1
        assert result.distance_km > 0  # segment 1 -> 3 still counted

    def test_large_time_gap_resets_reference_without_counting_segment(self):
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777),
            FakeGpsSample(_t(distance_service.MAX_GAP_SECONDS_FOR_JUMP_CHECK + 60), 19.5000, 73.5000),
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.untracked_gap_count == 1
        assert result.rejected_jump_count == 0  # gap check was SKIPPED, not failed
        assert result.distance_km == pytest.approx(0.0, abs=1e-9)  # segment itself not counted

    def test_duplicate_or_reversed_timestamp_does_not_advance_or_crash(self):
        samples = [
            FakeGpsSample(_t(0), 19.0760, 72.8777),
            FakeGpsSample(_t(0), 19.0761, 72.8778),  # same timestamp, dt=0
        ]
        result = distance_service.compute_distance_km(samples)
        assert result.rejected_out_of_order_count == 1

    def test_empty_samples_returns_zero(self):
        result = distance_service.compute_distance_km([])
        assert result.distance_km == 0.0
        assert result.valid_sample_count == 0

    def test_single_valid_sample_returns_zero(self):
        result = distance_service.compute_distance_km([FakeGpsSample(_t(0), 19.0760, 72.8777)])
        assert result.distance_km == 0.0
        assert result.valid_sample_count == 1

    def test_distance_never_negative(self):
        samples = [FakeGpsSample(_t(i), 19.0760 + i * 1e-5, 72.8777) for i in range(20)]
        result = distance_service.compute_distance_km(samples)
        assert result.distance_km >= 0.0
