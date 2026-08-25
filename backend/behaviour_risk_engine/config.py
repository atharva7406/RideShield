"""
Shared constants for the Behaviour Risk Engine's synthetic rider-history
generation and feature schema. Mirrors ml_incident_engine/config.py's role
— model hyperparameters live in model_config.py instead, once training
starts.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Feature schema.
#
# Every entry here is a real, existing db/models/rider_behaviour_profile.py
# column (verified below in tests/test_dataset.py against the actual
# SQLAlchemy model, not just asserted) — nothing synthetic-only leaks in.
# Excludes identity/bookkeeping columns (id, rider_id, computed_at,
# created_at, updated_at) and excludes overall_behaviour_score's own
# sub-components being duplicated as both raw rates AND the blended score
# would be fine (both are real columns) — included deliberately, same as
# Phase 3's baseline uses overall_behaviour_score as one input among
# several, not the only one.
# ---------------------------------------------------------------------------

_TIER_METRIC_SUFFIXES = [
    "avg_speed", "max_speed", "hard_braking_rate", "hard_acceleration_rate",
    "overspeeding_rate", "sharp_turn_rate", "max_g", "data_quality",
]
_TIERS = ["recent", "medium", "long_term"]

TIER_FEATURE_NAMES = [f"{tier}_{suffix}" for tier in _TIERS for suffix in _TIER_METRIC_SUFFIXES]

OVERALL_FEATURE_NAMES = [
    "overall_behaviour_score",
    "behaviour_consistency_score",
    "data_quality_score",
    "based_on_valid_shift_count",
    "based_on_shift_count",
    "confidence",
    "hard_braking_rate_variance",
    "overspeeding_rate_variance",
    "speed_variability",
]

FEATURE_NAMES = TIER_FEATURE_NAMES + OVERALL_FEATURE_NAMES  # 24 + 9 = 33

TARGET_NAME = "true_risk"

# ---------------------------------------------------------------------------
# Synthetic rider archetypes.
#
# `true_risk` is a LATENT 0-100 ground truth that DRIVES synthetic shift
# generation — it is NEVER a feature, only the training target. This is a
# deliberate response to the Phase 4 spec's own warning: the Phase 3
# baseline is a heuristic, not real-world accident truth, so it cannot be
# used as a training label without just teaching XGBoost to imitate the
# baseline's own blind spots. Using an independently-generated latent
# ground truth means "did XGBoost learn the actual generative pattern
# better than the heuristic did" is an honest question with real evidence,
# not circular.
#
# The training LABEL for a rider is their MOST RECENT true_risk value
# (risk drifts within a rider's own shift sequence for improving/
# deteriorating archetypes) — matches production semantics: the profile
# describes "this rider's behaviour as of now," and that's what a premium
# decision would need to predict.
# ---------------------------------------------------------------------------

ARCHETYPES = [
    "consistently_safe",
    "consistently_aggressive",
    "improving",
    "deteriorating",
    "safe_with_occasional_aggressive",
    "aggressive_temporarily_safe",
    "high_overspeeding",
    "high_hard_braking",
    "high_hard_acceleration",
    "frequent_sharp_turns",
    "mixed",
    "noisy_low_quality",
    "sparse_telemetry",
]

# Equal weight by default — generate_dataset() draws archetypes uniformly
# so no single pattern dominates the training distribution.
SHORT_HISTORY_SHIFT_RANGE = (1, 4)
MEDIUM_HISTORY_SHIFT_RANGE = (5, 15)
LONG_HISTORY_SHIFT_RANGE = (20, 60)

# Relative noise applied to every per-shift rate — the source of
# overlapping distributions between adjacent risk levels (see Phase 4
# spec's explicit "avoid trivial shortcuts" requirement).
RATE_NOISE_RELATIVE_STD = 0.35

# How much a "dominant signal" archetype amplifies that one dimension
# relative to the others, which stay at the true_risk-driven baseline.
DOMINANT_SIGNAL_MULTIPLIER = 2.2

# Trend magnitude (points of true_risk drifted across a rider's full
# shift sequence, oldest -> newest) for improving/deteriorating archetypes.
TREND_MAGNITUDE = 45.0

# "Occasional outlier shift" archetypes: fraction of shifts replaced with
# a large opposite-direction true_risk deviation, and how large.
OCCASIONAL_OUTLIER_FRACTION = 0.18
OCCASIONAL_OUTLIER_MAGNITUDE = 55.0

# "Temporarily safe/aggressive" archetypes: fraction of the MOST RECENT
# shifts (a contiguous block, not scattered) that get the opposite-
# direction deviation — tests whether recent-tier features correctly pick
# up a genuinely-changed current state.
TEMPORARY_BLOCK_FRACTION = 0.3
TEMPORARY_BLOCK_MAGNITUDE = 50.0
