"""
Builds and persists a rider's RiderBehaviourProfile from their valid,
completed ShiftBehaviourSummary rows. Phase 2 of the Behaviour Risk &
Premium Engine:

    Telemetry -> ShiftBehaviourSummary -> RiderBehaviourProfile

Deliberately isolated from backend/ml_incident_engine/ and
app/services/ml_scoring_service.py — no import from either appears here,
by design (see Phase 2 spec's "Keep crash ML isolated"). The only shared
layer with the crash engine is the underlying telemetry/shift data, not
code.

NOT IN SCOPE THIS PHASE (see module docstring in
db/models/rider_behaviour_profile.py): no XGBoost, no premium/pricing
logic, no cold-start PRICING policy. `overall_behaviour_score` is a
transparent baseline indicator only, not a risk probability — see
compute_overall_behaviour_score()'s docstring for exactly what goes into
it and why.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol, Sequence

from sqlalchemy.orm import Session


class _SummaryLike(Protocol):
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


# ---------------------------------------------------------------------------
# Temporal window sizes.
#
# Deliberately shift-COUNT windows (not calendar-time windows) — a rider's
# "recent" behaviour should mean their last few rides regardless of how
# many days ago that was (a rider who only drives on weekends shouldn't
# have a stale/empty "recent" window just because 5 days passed). Sizes
# match the values the original Behaviour Engine planning doc itself
# suggested (recent = last 3-5 shifts, medium = last 10), not invented
# fresh here.
# ---------------------------------------------------------------------------

RECENT_WINDOW_SHIFT_COUNT = 5
MEDIUM_WINDOW_SHIFT_COUNT = 10
# "Long-term" is nominally unbounded (the rider's whole valid history), but
# capped here purely as a practical query-size bound, not a philosophical
# one — a rider with thousands of historical shifts shouldn't make every
# shift-end request pull an ever-growing unbounded result set.
LONG_TERM_WINDOW_SHIFT_COUNT_CAP = 200

# Overall-score blend weights across the three tiers — see
# compute_overall_behaviour_score(). Sum to 1.0. Recent behaviour
# influences the score most; long-term history still has real (20%)
# weight so one unusual recent shift can't swing the score on its own.
RECENT_SCORE_WEIGHT = 0.5
MEDIUM_SCORE_WEIGHT = 0.3
LONG_TERM_SCORE_WEIGHT = 0.2

# Confidence saturates once a rider has this many valid shifts — chosen to
# match MEDIUM_WINDOW_SHIFT_COUNT: once there's enough history to fill the
# medium-term window, shift COUNT stops being the limiting factor and data
# QUALITY becomes the only thing still capping confidence. See
# compute_confidence().
CONFIDENCE_SATURATION_SHIFT_COUNT = MEDIUM_WINDOW_SHIFT_COUNT


@dataclass
class TierAggregate:
    shift_count: int
    avg_speed: float = 0.0
    max_speed: float = 0.0
    hard_braking_rate: float = 0.0
    hard_acceleration_rate: float = 0.0
    overspeeding_rate: float = 0.0
    sharp_turn_rate: float = 0.0
    max_g: float = 0.0
    data_quality: float = 0.0


def compute_tier_aggregate(summaries: Sequence[_SummaryLike]) -> TierAggregate:
    """Plain (unweighted) mean of each metric across `summaries`. Callers
    pass in exactly the shifts that belong to a given tier (recent/medium/
    long-term) — the recency-weighting comes from WHICH shifts are in each
    tier (see build_rider_profile_snapshot), not from a within-tier
    weighting scheme, keeping each tier itself simple and auditable."""
    if not summaries:
        return TierAggregate(shift_count=0)

    n = len(summaries)
    return TierAggregate(
        shift_count=n,
        avg_speed=sum(s.average_speed for s in summaries) / n,
        max_speed=max(s.max_speed for s in summaries),
        hard_braking_rate=sum(s.hard_braking_rate for s in summaries) / n,
        hard_acceleration_rate=sum(s.hard_acceleration_rate for s in summaries) / n,
        overspeeding_rate=sum(s.overspeeding_rate for s in summaries) / n,
        sharp_turn_rate=sum(s.sharp_turn_rate for s in summaries) / n,
        # float() casts: ShiftBehaviourSummary.max_g / data_quality_score are
        # SQLAlchemy Numeric columns, which come back as decimal.Decimal —
        # mixing that with the plain floats elsewhere in this module's
        # arithmetic (e.g. MAX_G_BASELINE) raises TypeError. Caught by
        # tests/test_rider_behaviour_profile_integration.py, which uses
        # real ORM-backed rows, not the plain-float fixtures the pure unit
        # tests use — exactly why both test styles exist.
        max_g=max(float(s.max_g) for s in summaries),
        data_quality=sum(float(s.data_quality_score) for s in summaries) / n,
    )


@dataclass
class ConsistencyResult:
    hard_braking_rate_variance: float = 0.0
    overspeeding_rate_variance: float = 0.0
    speed_variability: float = 0.0
    consistency_score: float = 0.0  # 0-100, higher = more consistent


def _coefficient_of_variation(values: Sequence[float]) -> float:
    """std / mean — a standard, scale-free measure of relative spread (not
    an invented formula). 0 if fewer than 2 values (can't measure spread)
    or if the mean is 0 (all-zero values are, by definition, perfectly
    consistent, not "undefined")."""
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if mean == 0:
        return 0.0
    return statistics.pstdev(values) / mean


def compute_consistency(summaries: Sequence[_SummaryLike]) -> ConsistencyResult:
    """Measures shift-to-shift STABILITY of behaviour, not the behaviour's
    absolute level — a rider who is *consistently* moderate scores higher
    here than one who alternates between very safe and very aggressive
    shifts, even if their average is similar.

    consistency_score = 100 * (1 - mean CV), clamped to [0, 100], averaged
    across hard-braking rate, overspeeding rate, and average speed. CV
    (coefficient of variation) is 0 for a perfectly steady rider (score
    100) and grows without bound for an erratic one (score approaches 0 as
    CV approaches 1, i.e. shift-to-shift swings as large as the rider's own
    average)."""
    if len(summaries) < 2:
        return ConsistencyResult()

    hard_braking_rates = [s.hard_braking_rate for s in summaries]
    overspeeding_rates = [s.overspeeding_rate for s in summaries]
    speeds = [s.average_speed for s in summaries]

    hb_variance = statistics.pvariance(hard_braking_rates)
    os_variance = statistics.pvariance(overspeeding_rates)
    speed_variability = statistics.pvariance(speeds)

    cvs = [
        _coefficient_of_variation(hard_braking_rates),
        _coefficient_of_variation(overspeeding_rates),
        _coefficient_of_variation(speeds),
    ]
    mean_cv = sum(cvs) / len(cvs)
    consistency_score = max(0.0, min(100.0, 100.0 * (1.0 - mean_cv)))

    return ConsistencyResult(
        hard_braking_rate_variance=hb_variance,
        overspeeding_rate_variance=os_variance,
        speed_variability=speed_variability,
        consistency_score=consistency_score,
    )


# ---------------------------------------------------------------------------
# Overall behaviour score.
#
# BASELINE 100, points deducted per behaviour indicator, each deduction
# individually capped so one extreme/corrupted rate can't dominate or push
# the score negative before the final clamp — same defensive-capping
# principle as behaviour_summary_service.py's data quality formula. A
# consistency bonus is added back (stable riders score slightly higher
# than an equally-aggressive-on-average but erratic one).
#
# These per-unit penalty weights are a first-pass, deterministic, tunable
# allocation — NOT fit against labeled accident data, and NOT a claim
# about actual accident probability. Same "V1, document don't hide"
# discipline as every other threshold in this codebase (see
# rider-app/src/crash-detection/config.ts, behaviour_summary_service.py).
# ---------------------------------------------------------------------------

BASELINE_SCORE = 100.0

HARD_BRAKING_PENALTY_PER_EVENT_PER_HOUR = 3.0
HARD_ACCELERATION_PENALTY_PER_EVENT_PER_HOUR = 3.0
OVERSPEEDING_PENALTY_PER_EVENT_PER_HOUR = 4.0
SHARP_TURN_PENALTY_PER_EVENT_PER_HOUR = 2.0
# Penalty per g of max_g above a resting ~1g baseline.
MAX_G_PENALTY_PER_G_ABOVE_BASELINE = 5.0
MAX_G_BASELINE = 1.0

# Cap on how many points ANY SINGLE component may deduct — defends against
# one corrupted/outlier shift's rate dominating the whole score.
MAX_PENALTY_PER_COMPONENT = 30.0

# Added back (not deducted), scaled by consistency_score/100 — a
# consistently-behaving rider is rewarded relative to an equally-averaged
# but erratic one.
CONSISTENCY_BONUS_MAX = 10.0


def compute_overall_behaviour_score(
    recent: TierAggregate, medium: TierAggregate, long_term: TierAggregate,
    consistency: ConsistencyResult,
) -> float:
    """Blends the three tiers' rates (weighted RECENT/MEDIUM/LONG_TERM_
    SCORE_WEIGHT, renormalized over whichever tiers actually have data —
    see _blend_tiers), then applies a single deterministic penalty formula
    to the blended rates. Bounded to [0, 100]. This is a behavioural-risk
    INDICATOR, not a validated accident-probability estimate — see module
    docstring."""
    blended = _blend_tiers(recent, medium, long_term)
    if blended is None:
        return BASELINE_SCORE  # no data at all -> neutral, not penalized

    def capped_penalty(rate: float, per_unit: float) -> float:
        return min(MAX_PENALTY_PER_COMPONENT, max(0.0, rate) * per_unit)

    score = BASELINE_SCORE
    score -= capped_penalty(blended.hard_braking_rate, HARD_BRAKING_PENALTY_PER_EVENT_PER_HOUR)
    score -= capped_penalty(blended.hard_acceleration_rate, HARD_ACCELERATION_PENALTY_PER_EVENT_PER_HOUR)
    score -= capped_penalty(blended.overspeeding_rate, OVERSPEEDING_PENALTY_PER_EVENT_PER_HOUR)
    score -= capped_penalty(blended.sharp_turn_rate, SHARP_TURN_PENALTY_PER_EVENT_PER_HOUR)
    score -= capped_penalty(max(0.0, blended.max_g - MAX_G_BASELINE), MAX_G_PENALTY_PER_G_ABOVE_BASELINE)
    score += (consistency.consistency_score / 100.0) * CONSISTENCY_BONUS_MAX

    return max(0.0, min(100.0, score))


def _blend_tiers(recent: TierAggregate, medium: TierAggregate, long_term: TierAggregate) -> Optional[TierAggregate]:
    """Weighted combination of the three tiers, renormalized over only the
    tiers that actually have data — a rider with just 2 shifts (so medium
    and long_term are identical to/degenerate with recent, or simply
    empty) must not have their score dragged toward a fabricated "0"
    long-term value. Returns None only if every tier is empty."""
    weighted = [(recent, RECENT_SCORE_WEIGHT), (medium, MEDIUM_SCORE_WEIGHT), (long_term, LONG_TERM_SCORE_WEIGHT)]
    active = [(t, w) for t, w in weighted if t.shift_count > 0]
    if not active:
        return None

    total_weight = sum(w for _, w in active)
    result = TierAggregate(shift_count=sum(t.shift_count for t, _ in active))
    for field_name in ("avg_speed", "max_speed", "hard_braking_rate", "hard_acceleration_rate",
                        "overspeeding_rate", "sharp_turn_rate", "max_g", "data_quality"):
        blended_value = sum(getattr(t, field_name) * w for t, w in active) / total_weight
        setattr(result, field_name, blended_value)
    return result


def compute_confidence(valid_shift_count: int, avg_data_quality: float) -> float:
    """0-1. Shift-count component saturates at CONFIDENCE_SATURATION_
    SHIFT_COUNT (beyond that, more shifts don't further increase
    confidence — data QUALITY is the only remaining limiter). Zero valid
    shifts -> zero confidence, regardless of anything else."""
    if valid_shift_count <= 0:
        return 0.0
    count_component = min(1.0, valid_shift_count / CONFIDENCE_SATURATION_SHIFT_COUNT)
    return max(0.0, min(1.0, count_component * avg_data_quality))


@dataclass
class RiderProfileSnapshot:
    computed_at: datetime
    based_on_shift_count: int
    based_on_valid_shift_count: int
    recent: TierAggregate
    medium: TierAggregate
    long_term: TierAggregate
    consistency: ConsistencyResult
    overall_behaviour_score: float
    data_quality_score: float
    confidence: float


def build_rider_profile_snapshot(
    valid_summaries_sorted_desc: Sequence[_SummaryLike],
    based_on_shift_count: int,
    computed_at: Optional[datetime] = None,
) -> Optional[RiderProfileSnapshot]:
    """Pure function, no DB access — `valid_summaries_sorted_desc` must
    already be filtered to is_valid=True and sorted most-recent-first.
    Returns None if there are zero valid summaries (cold start: no profile
    should be persisted yet — see rebuild_rider_profile)."""
    if not valid_summaries_sorted_desc:
        return None

    computed_at = computed_at or datetime.now(timezone.utc)

    recent_slice = valid_summaries_sorted_desc[:RECENT_WINDOW_SHIFT_COUNT]
    medium_slice = valid_summaries_sorted_desc[:MEDIUM_WINDOW_SHIFT_COUNT]
    long_term_slice = valid_summaries_sorted_desc[:LONG_TERM_WINDOW_SHIFT_COUNT_CAP]

    recent = compute_tier_aggregate(recent_slice)
    medium = compute_tier_aggregate(medium_slice)
    long_term = compute_tier_aggregate(long_term_slice)

    # Consistency is measured over the medium-term window — recent(5) is
    # too few to meaningfully estimate variance, long-term(up to 200) risks
    # diluting genuinely-recent instability with very old history.
    consistency = compute_consistency(medium_slice)

    overall_score = compute_overall_behaviour_score(recent, medium, long_term, consistency)

    valid_count = len(valid_summaries_sorted_desc)
    avg_quality = sum(float(s.data_quality_score) for s in valid_summaries_sorted_desc) / valid_count
    confidence = compute_confidence(valid_count, avg_quality)

    return RiderProfileSnapshot(
        computed_at=computed_at,
        based_on_shift_count=based_on_shift_count,
        based_on_valid_shift_count=valid_count,
        recent=recent, medium=medium, long_term=long_term,
        consistency=consistency,
        overall_behaviour_score=overall_score,
        data_quality_score=avg_quality,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# DB orchestration
# ---------------------------------------------------------------------------


def rebuild_rider_profile(db: Session, rider_id, as_of: Optional[datetime] = None):
    """Rebuilds (not appends to) rider_id's RiderBehaviourProfile from
    their ShiftBehaviourSummary history, and upserts the single profile
    row for that rider (idempotent — calling this twice in a row for the
    same underlying data produces the same one row, not two).

    `as_of`: anti-leakage cutoff (Phase 2 spec requirement #11) — only
    summaries with created_at <= as_of are considered. Defaults to "now",
    which is correct for the normal post-shift-end trigger (nothing in the
    future exists in the DB anyway at that point) but lets a future caller
    (e.g. a premium-quote request needing "the profile as it would have
    looked at shift-start time") reconstruct a historical view explicitly,
    without querying summaries that hadn't happened yet.

    Returns the persisted RiderBehaviourProfile, or None if the rider has
    zero valid shift summaries as of the cutoff — deliberately does NOT
    create an all-zero placeholder row; absence of a profile row IS the
    cold-start signal for callers (see db/models/rider_behaviour_profile.py).
    Does not commit — the caller controls the transaction boundary (see
    app/api/shifts.py's end_shift, which commits shift + summary + profile
    together where practical).
    """
    from db.models.rider_behaviour_profile import RiderBehaviourProfile
    from db.models.shift_behaviour_summary import ShiftBehaviourSummary

    as_of = as_of or datetime.now(timezone.utc)

    all_summaries = (
        db.query(ShiftBehaviourSummary)
        .filter(ShiftBehaviourSummary.rider_id == rider_id)
        .filter(ShiftBehaviourSummary.created_at <= as_of)
        .order_by(ShiftBehaviourSummary.created_at.desc())
        .all()
    )
    based_on_shift_count = len(all_summaries)
    valid_summaries = [s for s in all_summaries if s.is_valid]

    snapshot = build_rider_profile_snapshot(valid_summaries, based_on_shift_count, computed_at=as_of)
    if snapshot is None:
        return None

    profile = db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == rider_id).first()
    if profile is None:
        profile = RiderBehaviourProfile(rider_id=rider_id)
        db.add(profile)

    profile.computed_at = snapshot.computed_at
    profile.based_on_shift_count = snapshot.based_on_shift_count
    profile.based_on_valid_shift_count = snapshot.based_on_valid_shift_count

    profile.recent_avg_speed = snapshot.recent.avg_speed
    profile.recent_max_speed = snapshot.recent.max_speed
    profile.recent_hard_braking_rate = snapshot.recent.hard_braking_rate
    profile.recent_hard_acceleration_rate = snapshot.recent.hard_acceleration_rate
    profile.recent_overspeeding_rate = snapshot.recent.overspeeding_rate
    profile.recent_sharp_turn_rate = snapshot.recent.sharp_turn_rate
    profile.recent_max_g = snapshot.recent.max_g
    profile.recent_data_quality = snapshot.recent.data_quality

    profile.medium_avg_speed = snapshot.medium.avg_speed
    profile.medium_max_speed = snapshot.medium.max_speed
    profile.medium_hard_braking_rate = snapshot.medium.hard_braking_rate
    profile.medium_hard_acceleration_rate = snapshot.medium.hard_acceleration_rate
    profile.medium_overspeeding_rate = snapshot.medium.overspeeding_rate
    profile.medium_sharp_turn_rate = snapshot.medium.sharp_turn_rate
    profile.medium_max_g = snapshot.medium.max_g
    profile.medium_data_quality = snapshot.medium.data_quality

    profile.long_term_avg_speed = snapshot.long_term.avg_speed
    profile.long_term_max_speed = snapshot.long_term.max_speed
    profile.long_term_hard_braking_rate = snapshot.long_term.hard_braking_rate
    profile.long_term_hard_acceleration_rate = snapshot.long_term.hard_acceleration_rate
    profile.long_term_overspeeding_rate = snapshot.long_term.overspeeding_rate
    profile.long_term_sharp_turn_rate = snapshot.long_term.sharp_turn_rate
    profile.long_term_max_g = snapshot.long_term.max_g
    profile.long_term_data_quality = snapshot.long_term.data_quality

    profile.hard_braking_rate_variance = snapshot.consistency.hard_braking_rate_variance
    profile.overspeeding_rate_variance = snapshot.consistency.overspeeding_rate_variance
    profile.speed_variability = snapshot.consistency.speed_variability
    profile.behaviour_consistency_score = snapshot.consistency.consistency_score

    profile.overall_behaviour_score = snapshot.overall_behaviour_score
    profile.data_quality_score = snapshot.data_quality_score
    profile.confidence = snapshot.confidence

    db.flush()
    return profile
