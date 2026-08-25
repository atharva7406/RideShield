"""
Transparent, deterministic, non-ML baseline risk score computed from a
rider's RiderBehaviourProfile (Phase 2). Phase 3 of the Behaviour Risk &
Premium Engine:

    RiderBehaviourProfile -> BehaviourRiskAssessment (this service)

Purpose: a strong, fully-explainable baseline to later compare a real
XGBoost model against — "does ML actually outperform a transparent
rule-based system?" is only answerable if this baseline exists and is
honest about its own uncertainty. NOT a validated accident-probability
estimate — see MODEL_VERSION and the module-level disclaimer repeated in
compute_risk_score()'s docstring.

NOT PERSISTED. This is a pure function of an already-persisted profile —
cheap to recompute, nothing yet consumes a stored result (no pricing
engine exists), and the original Behaviour Engine plan's Phase 12
explicitly owns the audit-trail persistence layer (RiderRiskAssessment)
once pricing decisions actually need recording. Adding a table now would
be schema built for an undefined consumer.

ISOLATION: this module must never import backend/ml_incident_engine or
app/services/ml_scoring_service — the crash-detection model and the
behaviour-risk baseline are separate systems that happen to both read
telemetry-derived data, not a shared pipeline. Enforced by
tests/test_behaviour_risk_baseline_service.py (checks actual import
statements, not a naive substring match — see Phase 2's own isolation
test for why that matters).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

MODEL_VERSION = "behaviour-risk-baseline-v1"
SCORING_METHOD_BASELINE = "deterministic_baseline"
SCORING_METHOD_COLD_START = "cold_start"


@dataclass
class RiskContributor:
    factor: str
    impact: float  # signed points; contributors sum to the pre-clamp raw score
    direction: str  # "increases_risk" | "reduces_risk"


@dataclass
class BehaviourRiskAssessment:
    risk_score: Optional[float]  # 0-100, None only for cold-start
    risk_band: Optional[str]     # None only for cold-start
    confidence: float            # 0-1
    scoring_method: str
    model_version: str
    contributors: list[RiskContributor]
    data_quality: float          # 0-1
    based_on_shift_count: int
    based_on_valid_shift_count: int
    computed_at: datetime
    is_cold_start: bool = False
    cold_start_reason: Optional[str] = None
    # Signal for a future pricing engine (Phase 9/11) — not acted on here,
    # this phase does not implement pricing.
    suggested_pricing_mode: str = "PERSONALIZED"  # or "COLD_START_DEFAULT"


# ---------------------------------------------------------------------------
# Risk bands.
#
# Deliberately a SEPARATE, 5-band vocabulary from db/models/enums.py's
# existing RiskLevel (LOW/MEDIUM/HIGH/CRITICAL) — that enum is the live,
# continuous IN-SHIFT risk signal (db/models/risk.py, computed during an
# ACTIVE shift by telemetry_service.py). This is a different concept
# (historical, premium-relevant rider risk) computed at a different time
# for a different purpose; reusing the same 4-value enum vocabulary for
# both would make a shift's live risk_level=HIGH and a rider's behaviour
# risk_band=HIGH look like the same kind of statement when they aren't.
# Not a SQLAlchemy enum since nothing here is persisted — plain strings.
#
# Thresholds match the Phase 3 spec's own suggested cutoffs verbatim,
# after inspecting existing conventions (see above) — nothing here
# dictated a different specific cutoff scheme, only a different band
# COUNT for a different concept, so adopting the spec's suggestion as the
# first-pass, documented, tunable thresholds is reasonable. Half-open
# intervals: a boundary value belongs to the HIGHER band (20.0 -> LOW,
# not VERY_LOW), except the top band, closed on both ends at 100.
# ---------------------------------------------------------------------------

RISK_BAND_VERY_LOW = "VERY_LOW"
RISK_BAND_LOW = "LOW"
RISK_BAND_MODERATE = "MODERATE"
RISK_BAND_HIGH = "HIGH"
RISK_BAND_VERY_HIGH = "VERY_HIGH"

_RISK_BAND_UPPER_BOUNDS = [
    (20.0, RISK_BAND_VERY_LOW),
    (40.0, RISK_BAND_LOW),
    (60.0, RISK_BAND_MODERATE),
    (80.0, RISK_BAND_HIGH),
]


def compute_risk_band(risk_score: float) -> str:
    for upper_bound, band in _RISK_BAND_UPPER_BOUNDS:
        if risk_score < upper_bound:
            return band
    return RISK_BAND_VERY_HIGH


# ---------------------------------------------------------------------------
# Scoring formula.
#
# Baseline 0 (zero measured risk indicators -> zero score), points ADDED
# per risky recent-period signal (each individually capped so one extreme
# rate can't dominate — same defensive-capping principle
# behaviour_summary_service.py and rider_behaviour_profile_service.py
# already use), plus a smaller weighted contribution from Phase 2's own
# blended overall_behaviour_score (so long/medium-term tiered history
# still matters, without literally double-counting the same rates twice
# under two names), MINUS a capped discount for a genuinely-proven-safe
# long-term history.
#
# These weights are a first-pass, deterministic, documented allocation —
# NOT fit against labeled accident/claims data, and NOT a claim about
# real-world accident probability. Same "V1, document don't hide"
# discipline as every other threshold in this codebase.
# ---------------------------------------------------------------------------

RECENT_HARD_BRAKING_WEIGHT = 1.0       # points per event/hour
RECENT_HARD_ACCELERATION_WEIGHT = 1.0
RECENT_OVERSPEEDING_WEIGHT = 1.5
RECENT_SHARP_TURN_WEIGHT = 1.0
RECENT_MAX_G_WEIGHT = 3.0              # points per g above MAX_G_BASELINE
MAX_G_BASELINE = 1.0

# Cap on how many points ANY SINGLE recent-rate term may contribute.
# Deliberately set ABOVE what this project's own "aggressive rider"
# reference values (see rider_behaviour_profile_service tests: ~15 hard
# brakes/hr, ~10 overspeeding events/hr, ~4.5g max) produce per term —
# an earlier version capped at 25 with 2.5x these weights, which meant 3
# of 5 terms already hit their cap at just that reference level, pushing
# the raw score past 100 before the long-term-history discount below even
# applied, silently erasing its effect exactly in the range where
# differentiating "bad recent, safe long-term" from "bad both" matters
# most. Caught by test_bad_recent_but_safe_long_term_scores_lower_than_
# bad_both, which failed (100.0 == 100.0) until these weights were
# rebalanced — not loosened to make the test pass, the formula's actual
# saturation point was the bug.
MAX_TERM_CONTRIBUTION = 18.0

# Volatile (low-consistency) behaviour is itself a risk signal, distinct
# from the rate magnitudes — a rider who swings between very safe and very
# aggressive is less predictable than one who is steadily moderate.
INCONSISTENCY_WEIGHT_MAX = 15.0  # full amount when behaviour_consistency_score == 0

# Phase 2's overall_behaviour_score already blends recent/medium/long-term
# tiers + consistency with its own weights — kept intentionally SMALL here
# specifically to avoid double-counting the same underlying rates the
# terms above already penalize directly; this term exists so
# overall_behaviour_score genuinely influences the number (the Phase 3
# spec explicitly lists it as a required input), without duplicating it
# line-for-line in the contributor breakdown.
HISTORICAL_PROFILE_WEIGHT = 0.25

# "Proven safe long-term history" discount — only meaningfully earned once
# real long-term history exists (scaled by based_on_valid_shift_count,
# saturating at LONG_TERM_TRUST_SHIFT_COUNT; RiderBehaviourProfile doesn't
# store a long-term-tier-specific shift count, so the overall valid-shift
# count is used as a documented approximation).
SAFE_LONG_TERM_MAX_DISCOUNT = 8.0
LONG_TERM_TRUST_SHIFT_COUNT = 10
# "Reference bad rate" used to scale how much of the discount is earned —
# a long-term hard-braking + overspeeding combination at/above this level
# earns none of the discount; at 0, the full discount (subject to trust).
LONG_TERM_REFERENCE_BAD_SCORE = (
    RECENT_HARD_BRAKING_WEIGHT * 5.0 + RECENT_OVERSPEEDING_WEIGHT * 5.0
)  # "5 events/hour of each is clearly bad"


def _capped_penalty(rate: float, weight: float) -> float:
    return min(MAX_TERM_CONTRIBUTION, max(0.0, rate) * weight)


def _safe_long_term_discount(long_term_hard_braking_rate: float, long_term_overspeeding_rate: float,
                              based_on_valid_shift_count: int) -> float:
    badness = min(
        LONG_TERM_REFERENCE_BAD_SCORE,
        max(0.0, long_term_hard_braking_rate) * RECENT_HARD_BRAKING_WEIGHT
        + max(0.0, long_term_overspeeding_rate) * RECENT_OVERSPEEDING_WEIGHT,
    )
    goodness_fraction = 1.0 - (badness / LONG_TERM_REFERENCE_BAD_SCORE)
    trust_factor = min(1.0, max(0.0, based_on_valid_shift_count) / LONG_TERM_TRUST_SHIFT_COUNT)
    return SAFE_LONG_TERM_MAX_DISCOUNT * goodness_fraction * trust_factor


def compute_risk_score_and_contributors(
    recent_hard_braking_rate: float, recent_hard_acceleration_rate: float,
    recent_overspeeding_rate: float, recent_sharp_turn_rate: float, recent_max_g: float,
    long_term_hard_braking_rate: float, long_term_overspeeding_rate: float,
    behaviour_consistency_score: float, overall_behaviour_score: float,
    based_on_valid_shift_count: int,
) -> tuple[float, list[RiskContributor]]:
    """Pure numeric core — all inputs must already be plain float/int (see
    assess_rider_risk() for the Decimal-safety casting boundary). Returns
    (clamped risk_score, contributors) where contributors' impacts sum to
    the PRE-CLAMP raw score — the explanation is exact arithmetic, not an
    approximation, deliberately (see module docstring: this baseline's
    whole point is being fully transparent)."""
    hb_term = _capped_penalty(recent_hard_braking_rate, RECENT_HARD_BRAKING_WEIGHT)
    ha_term = _capped_penalty(recent_hard_acceleration_rate, RECENT_HARD_ACCELERATION_WEIGHT)
    os_term = _capped_penalty(recent_overspeeding_rate, RECENT_OVERSPEEDING_WEIGHT)
    st_term = _capped_penalty(recent_sharp_turn_rate, RECENT_SHARP_TURN_WEIGHT)
    g_term = _capped_penalty(max(0.0, recent_max_g - MAX_G_BASELINE), RECENT_MAX_G_WEIGHT)
    inconsistency_term = (100.0 - max(0.0, min(100.0, behaviour_consistency_score))) / 100.0 * INCONSISTENCY_WEIGHT_MAX
    historical_term = HISTORICAL_PROFILE_WEIGHT * (100.0 - max(0.0, min(100.0, overall_behaviour_score)))
    safe_discount = _safe_long_term_discount(
        long_term_hard_braking_rate, long_term_overspeeding_rate, based_on_valid_shift_count
    )

    contributors = [
        RiskContributor("recent_hard_braking_rate", hb_term, "increases_risk" if hb_term > 0 else "neutral"),
        RiskContributor("recent_hard_acceleration_rate", ha_term, "increases_risk" if ha_term > 0 else "neutral"),
        RiskContributor("recent_overspeeding_rate", os_term, "increases_risk" if os_term > 0 else "neutral"),
        RiskContributor("recent_sharp_turn_rate", st_term, "increases_risk" if st_term > 0 else "neutral"),
        RiskContributor("recent_max_g", g_term, "increases_risk" if g_term > 0 else "neutral"),
        RiskContributor("behaviour_consistency", inconsistency_term, "increases_risk" if inconsistency_term > 0 else "neutral"),
        RiskContributor("historical_profile_score", historical_term, "increases_risk" if historical_term > 0 else "neutral"),
        RiskContributor("safe_long_term_behaviour", -safe_discount, "reduces_risk" if safe_discount > 0 else "neutral"),
    ]

    raw_score = sum(c.impact for c in contributors)
    risk_score = max(0.0, min(100.0, raw_score))
    return risk_score, contributors


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def assess_cold_start(reason: str = "No RiderBehaviourProfile exists for this rider yet.") -> BehaviourRiskAssessment:
    """No fabricated score — risk_score/risk_band are explicitly None, not
    a fake '50' or '0'. Callers (a future pricing engine) should read
    is_cold_start / suggested_pricing_mode to select a default/base
    premium path instead of a personalized one (Phase 11's concern, not
    implemented here — this just exposes the signal)."""
    return BehaviourRiskAssessment(
        risk_score=None,
        risk_band=None,
        confidence=0.0,
        scoring_method=SCORING_METHOD_COLD_START,
        model_version=MODEL_VERSION,
        contributors=[],
        data_quality=0.0,
        based_on_shift_count=0,
        based_on_valid_shift_count=0,
        computed_at=datetime.now(timezone.utc),
        is_cold_start=True,
        cold_start_reason=reason,
        suggested_pricing_mode="COLD_START_DEFAULT",
    )


def assess_rider_risk(profile) -> BehaviourRiskAssessment:
    """`profile`: a RiderBehaviourProfile ORM instance, or None for
    cold-start. Never raises for "no data" — returns assess_cold_start()
    instead. Never fails on a low-data-quality profile either — the risk
    estimate is still computed and returned (per Phase 3 spec item 6:
    "preserve the risk estimate"), only `confidence` reflects the
    reduced trust, via a direct pass-through of profile.confidence (Phase
    2 already computes exactly "how much historical evidence backs this
    profile" — recomputing that here under a new name would duplicate,
    not improve on, that logic).

    DECIMAL SAFETY: RiderBehaviourProfile's Numeric-typed columns
    (recent_max_g, recent_data_quality, medium_/long_term_ equivalents,
    behaviour_consistency_score, overall_behaviour_score, data_quality_
    score, confidence) come back from SQLAlchemy as decimal.Decimal, not
    float — every one is explicitly float()-cast below. This exact class
    of bug broke Phase 2's first integration test run; casting proactively
    here rather than discovering it the same way again.
    """
    if profile is None:
        return assess_cold_start()

    recent_hard_braking_rate = float(profile.recent_hard_braking_rate)
    recent_hard_acceleration_rate = float(profile.recent_hard_acceleration_rate)
    recent_overspeeding_rate = float(profile.recent_overspeeding_rate)
    recent_sharp_turn_rate = float(profile.recent_sharp_turn_rate)
    recent_max_g = float(profile.recent_max_g)
    long_term_hard_braking_rate = float(profile.long_term_hard_braking_rate)
    long_term_overspeeding_rate = float(profile.long_term_overspeeding_rate)
    behaviour_consistency_score = float(profile.behaviour_consistency_score)
    overall_behaviour_score = float(profile.overall_behaviour_score)
    data_quality_score = float(profile.data_quality_score)
    confidence = float(profile.confidence)
    based_on_valid_shift_count = int(profile.based_on_valid_shift_count)
    based_on_shift_count = int(profile.based_on_shift_count)

    risk_score, contributors = compute_risk_score_and_contributors(
        recent_hard_braking_rate, recent_hard_acceleration_rate,
        recent_overspeeding_rate, recent_sharp_turn_rate, recent_max_g,
        long_term_hard_braking_rate, long_term_overspeeding_rate,
        behaviour_consistency_score, overall_behaviour_score,
        based_on_valid_shift_count,
    )
    risk_band = compute_risk_band(risk_score)

    return BehaviourRiskAssessment(
        risk_score=risk_score,
        risk_band=risk_band,
        confidence=confidence,
        scoring_method=SCORING_METHOD_BASELINE,
        model_version=MODEL_VERSION,
        contributors=contributors,
        data_quality=data_quality_score,
        based_on_shift_count=based_on_shift_count,
        based_on_valid_shift_count=based_on_valid_shift_count,
        computed_at=datetime.now(timezone.utc),
        is_cold_start=False,
        cold_start_reason=None,
        suggested_pricing_mode="PERSONALIZED",
    )
