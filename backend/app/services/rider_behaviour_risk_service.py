"""
Wraps behaviour_risk_engine (Phase 4's offline ML dev pipeline) for use
inside the live backend, with a MANDATORY fallback to the Phase 3
deterministic baseline (behaviour_risk_baseline_service). Mirrors
app/services/ml_scoring_service.py's architecture and fallback-safety
contract exactly — this is the second time this project has built this
pattern, and it should look like it.

FALLBACK-SAFETY CONTRACT (non-negotiable, same as ml_scoring_service.py):
  - assess_rider_risk() never raises for an "XGBoost unavailable" reason.
    If the engine can't be imported, the model file is missing/corrupted,
    or prediction throws for any reason, it transparently falls back to
    behaviour_risk_baseline_service.assess_rider_risk() — the Phase 3
    baseline stays the permanent fallback/comparison model, per the Phase
    4 spec's explicit instruction, not replaced by this service.
  - Cold-start (profile=None) is handled identically regardless of
    whether XGBoost is available — no fabricated score either way.

ISOLATION: this is the only file under app/ that imports
behaviour_risk_engine, same boundary principle as ml_scoring_service.py
importing ml_incident_engine. Neither ML package imports the other.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_behaviour_risk_engine_available = True
try:
    from behaviour_risk_engine import config as brcfg
    from behaviour_risk_engine.predict import load_booster, predict_calibrated_from_features
except Exception as e:  # pragma: no cover - defensive import guard
    _behaviour_risk_engine_available = False
    logger.warning(f"behaviour_risk_engine unavailable, will always use the Phase 3 baseline: {e}")

from app.services import behaviour_risk_baseline_service as baseline_service

_booster = None


def _get_booster():
    global _booster
    if _booster is None:
        _booster = load_booster()
    return _booster


def is_ml_available() -> bool:
    """Checked fresh each call (the loaded booster itself IS cached) so a
    model file added after backend startup gets picked up without a
    restart — same as ml_scoring_service.is_ml_available()."""
    if not _behaviour_risk_engine_available:
        return False
    try:
        _get_booster()
        return True
    except Exception as e:
        logger.warning(f"Behaviour-risk model failed to load, using Phase 3 baseline: {e}")
        return False


@dataclass
class RiderBehaviourRiskResult:
    risk_score: Optional[float]
    risk_band: Optional[str]
    confidence: float
    scoring_method: str          # "xgboost" | "deterministic_baseline" | "cold_start"
    model_version: str
    data_quality: float
    based_on_shift_count: int
    based_on_valid_shift_count: int
    computed_at: datetime
    is_cold_start: bool
    cold_start_reason: Optional[str]
    suggested_pricing_mode: str
    top_features: list  # XGBoost gain-based top contributors, [] for baseline/cold-start
    source: str          # "xgboost" | "baseline_fallback" — which path actually served this result


def _baseline_result_to_service_result(baseline_result, source: str) -> RiderBehaviourRiskResult:
    return RiderBehaviourRiskResult(
        risk_score=baseline_result.risk_score,
        risk_band=baseline_result.risk_band,
        confidence=baseline_result.confidence,
        scoring_method=baseline_result.scoring_method,
        model_version=baseline_result.model_version,
        data_quality=baseline_result.data_quality,
        based_on_shift_count=baseline_result.based_on_shift_count,
        based_on_valid_shift_count=baseline_result.based_on_valid_shift_count,
        computed_at=baseline_result.computed_at,
        is_cold_start=baseline_result.is_cold_start,
        cold_start_reason=baseline_result.cold_start_reason,
        suggested_pricing_mode=baseline_result.suggested_pricing_mode,
        top_features=[],
        source=source,
    )


def _profile_to_features(profile) -> dict:
    """DECIMAL SAFETY: RiderBehaviourProfile's Numeric-typed columns come
    back from SQLAlchemy as decimal.Decimal, not float — every field is
    explicitly float()-cast here, same discipline as
    behaviour_risk_baseline_service.assess_rider_risk() and the exact bug
    class that broke Phase 2's first integration test run."""
    features = {}
    for tier in ("recent", "medium", "long_term"):
        for suffix in ("avg_speed", "max_speed", "hard_braking_rate", "hard_acceleration_rate",
                        "overspeeding_rate", "sharp_turn_rate", "max_g", "data_quality"):
            features[f"{tier}_{suffix}"] = float(getattr(profile, f"{tier}_{suffix}"))
    features["overall_behaviour_score"] = float(profile.overall_behaviour_score)
    features["behaviour_consistency_score"] = float(profile.behaviour_consistency_score)
    features["data_quality_score"] = float(profile.data_quality_score)
    features["based_on_valid_shift_count"] = float(profile.based_on_valid_shift_count)
    features["based_on_shift_count"] = float(profile.based_on_shift_count)
    features["confidence"] = float(profile.confidence)
    features["hard_braking_rate_variance"] = float(profile.hard_braking_rate_variance)
    features["overspeeding_rate_variance"] = float(profile.overspeeding_rate_variance)
    features["speed_variability"] = float(profile.speed_variability)
    return features


def assess_rider_risk(profile) -> RiderBehaviourRiskResult:
    """`profile`: a RiderBehaviourProfile ORM instance, or None for
    cold-start. Never raises. XGBoost available and prediction succeeds ->
    scoring_method="xgboost". Anything else (unavailable, missing/
    corrupted model, invalid features, prediction exception) -> falls back
    to the Phase 3 baseline transparently, scoring_method reflects
    whichever path actually ran.
    """
    if profile is None:
        cold_start = baseline_service.assess_cold_start()
        return _baseline_result_to_service_result(cold_start, source="baseline_fallback")

    if is_ml_available():
        try:
            features = _profile_to_features(profile)
            # predict_calibrated_from_features() ALREADY degrades to the
            # raw (uncalibrated) prediction internally if no calibration
            # artifact was deployed (Phase 5: calibration is only shipped
            # when it improves test RMSE — its absence is a normal,
            # expected state, see model_config.CALIBRATION_PATH's
            # docstring) or if applying calibration fails for any reason.
            # This service's fallback structure therefore stays exactly
            # the 2-tier shape it already was — "this ML call, or the
            # baseline" — Phase 5 only changed WHICH predict function that
            # ML call is, not the shape of the fallback itself.
            ml_result = predict_calibrated_from_features(features, booster=_get_booster())
            # Confidence/band/data-quality reuse the baseline's own
            # already-correct computation (same reasoning as Phase 3
            # reusing Phase 2's confidence: don't recompute what's already
            # solved under a new name) — only risk_score itself comes from
            # XGBoost (calibrated or raw).
            baseline_context = baseline_service.assess_rider_risk(profile)
            risk_score = ml_result["risk_score"]
            return RiderBehaviourRiskResult(
                risk_score=risk_score,
                risk_band=baseline_service.compute_risk_band(risk_score),
                confidence=baseline_context.confidence,
                scoring_method="xgboost_calibrated" if ml_result["is_calibrated"] else "xgboost",
                model_version=ml_result["model_version"],
                data_quality=baseline_context.data_quality,
                based_on_shift_count=baseline_context.based_on_shift_count,
                based_on_valid_shift_count=baseline_context.based_on_valid_shift_count,
                computed_at=datetime.now(timezone.utc),
                is_cold_start=False,
                cold_start_reason=None,
                suggested_pricing_mode="PERSONALIZED",
                top_features=ml_result["top_features"],
                source="xgboost",
            )
        except Exception as e:
            logger.warning(f"XGBoost behaviour-risk scoring failed, falling back to Phase 3 baseline: {e}")

    baseline_result = baseline_service.assess_rider_risk(profile)
    return _baseline_result_to_service_result(baseline_result, source="baseline_fallback")
