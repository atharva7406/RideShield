"""
Generates synthetic multi-shift rider histories and turns them into real
RiderProfileSnapshot feature vectors via
app.services.rider_behaviour_profile_service's ACTUAL aggregation
functions (build_rider_profile_snapshot) — not a reimplementation. This
guarantees zero feature drift between training-time and production-time
feature computation: whatever Phase 2 does to a real rider's shifts is
exactly what happens here to a synthetic one.

No external dataset, no real rider data — every rider is synthesized from
a latent `true_risk` (0-100) parameter that DRIVES per-shift behavioural
stats (with noise/overlap), per config.py's module docstring on why
`true_risk` — not the Phase 3 baseline's output — is the training label.
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np

# app/ is a sibling package under backend/ — importable the same way
# app/services/ml_scoring_service.py imports ml_incident_engine, as long
# as this runs with backend/ on sys.path (e.g. `python -m
# behaviour_risk_engine.xxx` from backend/). Explicit fallback for
# direct-script / test-collection contexts that don't already have it.
_BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.behaviour_summary_service import MIN_DATA_QUALITY_SCORE_FOR_VALID
from app.services.rider_behaviour_profile_service import RiderProfileSnapshot, build_rider_profile_snapshot

from . import config as cfg


@dataclass
class SyntheticShiftSummary:
    """Matches app.services.rider_behaviour_profile_service._SummaryLike
    exactly — this is what gets fed into the real build_rider_profile_
    snapshot(), not a parallel reimplementation of its input shape."""
    created_at: datetime
    is_valid: bool
    average_speed: float
    max_speed: float
    hard_braking_rate: float
    hard_acceleration_rate: float
    overspeeding_rate: float
    sharp_turn_rate: float
    max_g: float
    data_quality_score: float


@dataclass
class SyntheticRider:
    rider_id: str
    archetype: str  # diagnostics only — NEVER a feature, NEVER used by build_rider_profile_snapshot
    true_risk: float  # the label: most-recent latent risk value
    num_shifts: int
    profile_snapshot: RiderProfileSnapshot


def _rng_uuid(rng: np.random.Generator) -> str:
    return str(uuid.UUID(bytes=rng.bytes(16), version=4))


def _shift_history_count(rng: np.random.Generator, archetype: str) -> int:
    if archetype == "sparse_telemetry":
        low, high = cfg.SHORT_HISTORY_SHIFT_RANGE
    else:
        pool = [cfg.SHORT_HISTORY_SHIFT_RANGE, cfg.MEDIUM_HISTORY_SHIFT_RANGE, cfg.LONG_HISTORY_SHIFT_RANGE]
        low, high = pool[rng.integers(0, len(pool))]
    return int(rng.integers(low, high + 1))


def _base_true_risk_range(archetype: str) -> tuple[float, float]:
    return {
        "consistently_safe": (0.0, 25.0),
        "consistently_aggressive": (70.0, 100.0),
        "improving": (55.0, 95.0),          # starts high, trends down
        "deteriorating": (5.0, 40.0),        # starts low, trends up
        "safe_with_occasional_aggressive": (5.0, 30.0),
        "aggressive_temporarily_safe": (60.0, 95.0),
        "high_overspeeding": (25.0, 70.0),
        "high_hard_braking": (25.0, 70.0),
        "high_hard_acceleration": (25.0, 70.0),
        "frequent_sharp_turns": (25.0, 70.0),
        "mixed": (0.0, 100.0),
        "noisy_low_quality": (0.0, 100.0),
        "sparse_telemetry": (0.0, 100.0),
    }[archetype]


def _dominant_signal(archetype: str) -> Optional[str]:
    return {
        "high_overspeeding": "overspeeding",
        "high_hard_braking": "hard_braking",
        "high_hard_acceleration": "hard_acceleration",
        "frequent_sharp_turns": "sharp_turn",
    }.get(archetype)


def _quality_level(archetype: str) -> str:
    if archetype == "noisy_low_quality":
        return "poor"
    if archetype == "sparse_telemetry":
        return "sparse"
    return "good"


def _true_risk_sequence(rng: np.random.Generator, archetype: str, base_risk: float, num_shifts: int) -> list[float]:
    """Index 0 = OLDEST shift, index -1 = MOST RECENT (matches the order
    shifts actually accumulate in production)."""
    risks = []
    for i in range(num_shifts):
        progress = i / max(1, num_shifts - 1)  # 0 (oldest) -> 1 (most recent)
        r = base_risk
        if archetype == "improving":
            r = base_risk - progress * cfg.TREND_MAGNITUDE
        elif archetype == "deteriorating":
            r = base_risk + progress * cfg.TREND_MAGNITUDE
        r += rng.normal(0, 6.0)  # per-shift wobble even for "stable" archetypes
        risks.append(max(0.0, min(100.0, r)))

    if archetype == "safe_with_occasional_aggressive":
        for i in range(num_shifts):
            if rng.uniform() < cfg.OCCASIONAL_OUTLIER_FRACTION:
                risks[i] = max(0.0, min(100.0, risks[i] + cfg.OCCASIONAL_OUTLIER_MAGNITUDE))
    elif archetype == "aggressive_temporarily_safe":
        block_size = max(1, int(num_shifts * cfg.TEMPORARY_BLOCK_FRACTION))
        for i in range(num_shifts - block_size, num_shifts):  # most-recent contiguous block
            risks[i] = max(0.0, min(100.0, risks[i] - cfg.TEMPORARY_BLOCK_MAGNITUDE))

    return risks


def _shift_stats_from_true_risk(
    rng: np.random.Generator, true_risk: float, dominant_signal: Optional[str], quality_level: str,
) -> SyntheticShiftSummary:
    """Smooth, noisy, overlapping mapping from a single true_risk value to
    one shift's behavioural stats — deliberately NOT a deterministic
    lookup (see config.RATE_NOISE_RELATIVE_STD): two shifts with the same
    true_risk produce different, overlapping rates, and adjacent risk
    levels' distributions overlap too."""
    frac = true_risk / 100.0

    base_hard_braking = frac * 12.0
    base_hard_acceleration = frac * 10.0
    base_overspeeding = frac * 9.0
    base_sharp_turn = frac * 7.0
    base_max_g_extra = frac * 3.0  # added to a 1.0g resting baseline

    if dominant_signal == "overspeeding":
        base_overspeeding *= cfg.DOMINANT_SIGNAL_MULTIPLIER
    elif dominant_signal == "hard_braking":
        base_hard_braking *= cfg.DOMINANT_SIGNAL_MULTIPLIER
    elif dominant_signal == "hard_acceleration":
        base_hard_acceleration *= cfg.DOMINANT_SIGNAL_MULTIPLIER
    elif dominant_signal == "sharp_turn":
        base_sharp_turn *= cfg.DOMINANT_SIGNAL_MULTIPLIER

    def noisy(base: float) -> float:
        return max(0.0, base * (1.0 + rng.normal(0.0, cfg.RATE_NOISE_RELATIVE_STD)))

    hard_braking_rate = noisy(base_hard_braking)
    hard_acceleration_rate = noisy(base_hard_acceleration)
    overspeeding_rate = noisy(base_overspeeding)
    sharp_turn_rate = noisy(base_sharp_turn)
    max_g = max(1.0, 1.0 + base_max_g_extra * (1.0 + rng.normal(0.0, cfg.RATE_NOISE_RELATIVE_STD * 0.5)))

    # Riskier riders drive somewhat faster on average too — correlated,
    # not deterministic (real per-shift noise dominates at the individual
    # level, same principle as the crash engine's hard-negative overlap).
    average_speed = max(5.0, 25.0 + frac * 10.0 + rng.normal(0.0, 5.0))
    max_speed = average_speed + 15.0 + abs(rng.normal(0.0, 5.0))

    if quality_level == "poor":
        data_quality_score = max(0.0, min(1.0, rng.normal(0.32, 0.10)))
        plausible_sample = rng.uniform() > 0.25
    elif quality_level == "sparse":
        data_quality_score = max(0.0, min(1.0, rng.normal(0.30, 0.15)))
        plausible_sample = rng.uniform() > 0.45
    else:
        data_quality_score = max(0.0, min(1.0, rng.normal(0.9, 0.05)))
        plausible_sample = True

    # Mirrors Phase 1's own is_summary_valid() bar (MIN_DATA_QUALITY_SCORE_
    # FOR_VALID) rather than inventing a separate validity threshold here.
    is_valid = plausible_sample and data_quality_score >= MIN_DATA_QUALITY_SCORE_FOR_VALID

    return SyntheticShiftSummary(
        created_at=BASE_TIMESTAMP,  # overwritten by caller with the real sequence position
        is_valid=is_valid,
        average_speed=average_speed,
        max_speed=max_speed,
        hard_braking_rate=hard_braking_rate,
        hard_acceleration_rate=hard_acceleration_rate,
        overspeeding_rate=overspeeding_rate,
        sharp_turn_rate=sharp_turn_rate,
        max_g=max_g,
        data_quality_score=data_quality_score,
    )


BASE_TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


def generate_rider(rng: np.random.Generator, archetype: Optional[str] = None) -> Optional[SyntheticRider]:
    """Returns None if the generated rider ends up with zero VALID shifts
    (can legitimately happen for noisy/sparse archetypes) — matches
    production semantics: build_rider_profile_snapshot() itself returns
    None in that case, no profile is created, cold-start applies."""
    archetype = archetype or cfg.ARCHETYPES[rng.integers(0, len(cfg.ARCHETYPES))]
    num_shifts = _shift_history_count(rng, archetype)
    low, high = _base_true_risk_range(archetype)
    base_risk = rng.uniform(low, high)
    dominant_signal = _dominant_signal(archetype)
    quality_level = _quality_level(archetype)

    risk_sequence = _true_risk_sequence(rng, archetype, base_risk, num_shifts)

    shifts = []
    for i, true_risk_i in enumerate(risk_sequence):
        stats = _shift_stats_from_true_risk(rng, true_risk_i, dominant_signal, quality_level)
        # index 0 = oldest -> earliest created_at; index -1 = most recent -> latest created_at.
        stats.created_at = BASE_TIMESTAMP + timedelta(hours=i)
        shifts.append(stats)

    # build_rider_profile_snapshot expects most-recent-first.
    shifts_desc = list(reversed(shifts))
    valid_shifts_desc = [s for s in shifts_desc if s.is_valid]

    snapshot = build_rider_profile_snapshot(
        valid_shifts_desc, based_on_shift_count=len(shifts_desc),
        computed_at=shifts_desc[0].created_at if shifts_desc else BASE_TIMESTAMP,
    )
    if snapshot is None:
        return None  # zero valid shifts — legitimate cold-start case, excluded from training

    return SyntheticRider(
        rider_id=_rng_uuid(rng),
        archetype=archetype,
        true_risk=risk_sequence[-1],  # most-recent latent value — the training label
        num_shifts=num_shifts,
        profile_snapshot=snapshot,
    )


def generate_riders(n_riders: int, seed: int = 42) -> list[SyntheticRider]:
    rng = np.random.default_rng(seed)
    riders = []
    attempts = 0
    max_attempts = n_riders * 3  # generous — a few zero-valid-shift riders are expected and skipped
    while len(riders) < n_riders and attempts < max_attempts:
        attempts += 1
        archetype = cfg.ARCHETYPES[rng.integers(0, len(cfg.ARCHETYPES))]
        rider = generate_rider(rng, archetype=archetype)
        if rider is not None:
            riders.append(rider)
    return riders
