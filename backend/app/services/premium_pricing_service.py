"""
Phase 6 — PremiumPricingService: converts a rider's behaviour risk
assessment into the rupee premium charged for their NEXT shift.

    Completed shift history -> RiderBehaviourProfile (Phase 1/2)
        -> rider_behaviour_risk_service.assess_rider_risk() (Phase 3/4/5,
           baseline or XGBoost, whichever is live)
        -> risk_score (0-100)
        -> THIS SERVICE -> PremiumQuote (rupees)
        -> (a later phase) Razorpay Order

DESIGN PRINCIPLE (non-negotiable, per the Phase 6 spec): the ML/baseline
model predicts RISK, never MONEY. Nothing in this module imports XGBoost,
sklearn, or ml_incident_engine, and nothing upstream of this module ever
produces a rupee amount — this is the ONLY place a risk score becomes a
price. This mirrors the project's established separation between
ml_scoring_service (never touches money) and everything else.

DECIMAL SAFETY: every monetary computation uses decimal.Decimal, never
float. RiderBehaviourProfile/BehaviourRiskAssessment/RiderBehaviourRiskResult
expose risk_score/confidence as plain floats (they're statistical
quantities, not money) — those are converted to Decimal via
Decimal(str(x)) exactly once, at the boundary where a float first
participates in a monetary calculation, same "cast at the boundary"
discipline as every other Decimal-safety fix in this codebase
(rider_behaviour_risk_service._profile_to_features, etc., just mirrored
for the opposite direction: float statistics -> Decimal money).
Shift.premium_amount is a Numeric(10,2) column and therefore already
comes back from SQLAlchemy as Decimal — read directly, never cast
through float.

NOT PERSISTED: per Phase 6 spec item 15, this returns a PremiumQuote
value object; no audit/persistence table is created here. That is the
later persistence phase's job.

PROTOTYPE PRICING PARAMETERS: every weight/threshold below (base premium,
adjustment curve, confidence threshold, rate-of-change cap, min/max) is a
first-pass, documented, tunable DEMO parameter for the SIH prototype — NOT
an actuarially validated pricing model. Same "V1, document don't hide"
discipline as behaviour_risk_baseline_service.py's own weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app.services import behaviour_risk_baseline_service as baseline_service
from app.services import rider_behaviour_risk_service as risk_service

# ---------------------------------------------------------------------------
# Pricing modes
# ---------------------------------------------------------------------------

PRICING_MODE_PERSONALIZED = "PERSONALIZED"
PRICING_MODE_CONSERVATIVE_DEFAULT = "CONSERVATIVE_DEFAULT"
PRICING_MODE_COLD_START_DEFAULT = "COLD_START_DEFAULT"

# ---------------------------------------------------------------------------
# Configurable pricing parameters (prototype/demo values — see module
# docstring). All monetary constants are Decimal from the start; no float
# ever enters a money computation.
# ---------------------------------------------------------------------------

CENTS = Decimal("0.01")

# Requirement #3: base premium, initially ₹5 to preserve current demo
# behaviour (the hardcoded client-supplied ₹5 the frontend has been
# sending — see app/api/shifts.py's ShiftStart.premium_amount).
BASE_PREMIUM = Decimal("5.00")

# Requirement #5: hard bounds — no formula below can ever produce a price
# outside this range, regardless of risk score, confidence, or bugs in the
# adjustment curve.
MIN_PREMIUM = Decimal("2.00")
MAX_PREMIUM = Decimal("15.00")

# Requirement #4: smooth adjustment curve. risk_score=50 is "neutral" (no
# adjustment); the premium moves linearly away from base as the score
# moves away from 50 in either direction, reaching +/-MAX_ADJUSTMENT_
# FRACTION of the base premium at the score extremes (0 and 100). Linear,
# not banded — every whole-number risk score produces a distinct price,
# there are no five-band cliff edges.
NEUTRAL_RISK_SCORE = Decimal("50")
MAX_ADJUSTMENT_FRACTION = Decimal("0.5")  # +/-50% of base premium at the extremes

# Requirement #7: confidence-gated pricing mode. confidence is Phase 2's
# own 0-1 "how much real history backs this profile" signal (reused, not
# recomputed — same principle behaviour_risk_baseline_service.py already
# follows for the same field). At/above this threshold: full PERSONALIZED
# adjustment. Below it: the adjustment is scaled down continuously
# (confidence / threshold, capped at 1.0) rather than snapping to a second
# hardcoded number — this keeps the mode label binary (a rider is told
# plainly whether pricing is PERSONALIZED or CONSERVATIVE_DEFAULT) while
# keeping the actual rupee effect smooth as confidence crosses the
# threshold, consistent with requirement #4's "no abrupt jumps" intent.
HIGH_CONFIDENCE_THRESHOLD = Decimal("0.5")

# Requirement #6: rate-of-change cap. The premium for the next shift may
# move at most this FRACTION of the previous shift's premium, OR this
# ABSOLUTE floor amount, whichever is larger — the fractional cap alone
# would let a rider stuck near MIN_PREMIUM never recover even after
# consistently safe driving (a fraction of a small number is a small
# number), so a rupee floor keeps the cap meaningful across the whole
# price range.
MAX_RATE_OF_CHANGE_FRACTION = Decimal("0.25")  # 25% of the previous premium
MAX_RATE_OF_CHANGE_FLOOR = Decimal("1.00")      # or at least +/-Rs.1, whichever is bigger


def _to_decimal(value) -> Decimal:
    """Converts a float/int/Decimal statistical value to Decimal via str()
    — never Decimal(float) directly, which would import the float's exact
    (and often ugly) binary representation instead of its printed decimal
    value."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def _clamp_decimal(value: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(hi, value))


@dataclass
class PricingContributor:
    """A behavioural factor from the transparent Phase 3 baseline's own
    decomposition of the risk score (see module docstring in
    behaviour_risk_baseline_service.py). Expressed in RISK-SCORE POINTS,
    not rupees — this pricing service deliberately does NOT attempt to
    split the rupee adjustment amount factor-by-factor (that would imply a
    precision this prototype doesn't have); it reports which behaviours
    drove the risk score that in turn drove the price.

    HONESTY NOTE: when the live risk_score actually came from the XGBoost
    model (Phase 4/5) rather than the baseline, these contributors are
    NOT that model's literal feature attribution (which would require
    SHAP values, not implemented anywhere in this project) — they are the
    baseline's own transparent recomputation from the same underlying
    behaviour signals, used here purely as a faithful, human-readable
    explanation proxy. See calculate_premium_quote()'s docstring.
    """

    factor: str
    impact_points: float
    direction: str


@dataclass
class PremiumQuote:
    rider_id: object
    base_premium: Decimal
    risk_score: Optional[float]      # None only for cold-start
    risk_band: Optional[str]
    confidence: float
    scoring_method: str              # "xgboost" | "xgboost_calibrated" | "deterministic_baseline" | "cold_start"
    model_version: str
    pricing_mode: str                # PERSONALIZED | CONSERVATIVE_DEFAULT | COLD_START_DEFAULT
    previous_premium: Decimal
    raw_adjustment_amount: Decimal   # before the rate-of-change cap
    adjustment_amount: Decimal       # signed, AFTER the rate-of-change cap; final_premium == base_premium + adjustment_amount exactly
    final_premium: Decimal
    rate_of_change_capped: bool
    is_cold_start: bool
    contributors: list[PricingContributor]
    explanation: str
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Pure numeric core — no DB access. All inputs already plain
# float/Decimal/bool/str; this is the deterministic business-logic layer
# requirement #1/#11 describe. Given identical inputs, always returns an
# identical PremiumQuote (modulo computed_at, which is metadata, not a
# pricing input or output).
# ---------------------------------------------------------------------------


def _smooth_adjustment_fraction(risk_score: Decimal) -> Decimal:
    """Linear in risk_score, zero at NEUTRAL_RISK_SCORE, +/-MAX_ADJUSTMENT_
    FRACTION at the 0/100 extremes. risk_score is clamped to [0,100]
    first — defensive, since every real caller already guarantees this
    range, but requirement #12 explicitly asks for negative/out-of-range
    input coverage."""
    clamped = _clamp_decimal(risk_score, Decimal("0"), Decimal("100"))
    return (clamped - NEUTRAL_RISK_SCORE) / NEUTRAL_RISK_SCORE * MAX_ADJUSTMENT_FRACTION


def compute_premium_quote(
    *,
    rider_id,
    is_cold_start: bool,
    risk_score: Optional[float],
    risk_band: Optional[str],
    confidence: float,
    scoring_method: str,
    model_version: str,
    previous_premium: Decimal,
    contributors: Optional[list] = None,
    base_premium: Decimal = BASE_PREMIUM,
) -> PremiumQuote:
    contributors = contributors or []
    previous_premium = _clamp_decimal(_to_decimal(previous_premium), MIN_PREMIUM, MAX_PREMIUM)
    confidence_dec = _clamp_decimal(_to_decimal(confidence), Decimal("0"), Decimal("1"))

    if is_cold_start or risk_score is None:
        # Requirement #7: cold-start riders get an explicit, unadjusted
        # default — no risk-based personalization is possible or claimed
        # when zero history exists.
        pricing_mode = PRICING_MODE_COLD_START_DEFAULT
        raw_premium = base_premium
        confidence_scale = Decimal("0")
        top_contributors: list[PricingContributor] = []
    else:
        risk_score_dec = _clamp_decimal(_to_decimal(risk_score), Decimal("0"), Decimal("100"))
        fraction = _smooth_adjustment_fraction(risk_score_dec)

        if confidence_dec >= HIGH_CONFIDENCE_THRESHOLD:
            pricing_mode = PRICING_MODE_PERSONALIZED
            confidence_scale = Decimal("1")
        else:
            # Requirement #7: low confidence -> conservative pricing.
            # Dampens (never zeroes, never inverts) the adjustment
            # proportionally to how far confidence falls short of the
            # threshold, rather than discarding the risk signal entirely.
            pricing_mode = PRICING_MODE_CONSERVATIVE_DEFAULT
            confidence_scale = min(Decimal("1"), confidence_dec / HIGH_CONFIDENCE_THRESHOLD)

        raw_premium = base_premium + (base_premium * fraction * confidence_scale)
        raw_premium = _clamp_decimal(raw_premium, MIN_PREMIUM, MAX_PREMIUM)

        top_contributors = sorted(
            (PricingContributor(c.factor, float(c.impact), c.direction) for c in contributors),
            key=lambda c: abs(c.impact_points),
            reverse=True,
        )[:5]

    raw_adjustment = raw_premium - base_premium

    # Requirement #6: rate-of-change cap relative to the PREVIOUS shift's
    # premium (not the base premium) — this bounds how much a single
    # completed shift can move the price, independent of how far the risk
    # score itself moved.
    max_step = max(previous_premium * MAX_RATE_OF_CHANGE_FRACTION, MAX_RATE_OF_CHANGE_FLOOR)
    floor = previous_premium - max_step
    ceiling = previous_premium + max_step
    capped_premium = _clamp_decimal(raw_premium, floor, ceiling)
    rate_of_change_capped = capped_premium != raw_premium

    # Requirement #5: hard min/max bounds apply last too — belt-and-braces
    # against a pathological previous_premium (e.g. corrupted data) ever
    # pushing the capped result outside the absolute safe range.
    final_premium = _quantize(_clamp_decimal(capped_premium, MIN_PREMIUM, MAX_PREMIUM))
    final_adjustment = final_premium - base_premium

    explanation = _build_explanation(
        base_premium=base_premium,
        risk_score=risk_score,
        risk_band=risk_band,
        pricing_mode=pricing_mode,
        confidence=confidence_dec,
        adjustment=final_adjustment,
        final_premium=final_premium,
        rate_of_change_capped=rate_of_change_capped,
        is_cold_start=is_cold_start,
        contributors=top_contributors,
    )

    return PremiumQuote(
        rider_id=rider_id,
        base_premium=_quantize(base_premium),
        risk_score=risk_score,
        risk_band=risk_band,
        confidence=float(confidence_dec),
        scoring_method=scoring_method,
        model_version=model_version,
        pricing_mode=pricing_mode,
        previous_premium=_quantize(previous_premium),
        raw_adjustment_amount=_quantize(raw_adjustment),
        adjustment_amount=_quantize(final_adjustment),
        final_premium=final_premium,
        rate_of_change_capped=rate_of_change_capped,
        is_cold_start=is_cold_start,
        contributors=top_contributors,
        explanation=explanation,
    )


def _build_explanation(
    *, base_premium: Decimal, risk_score: Optional[float], risk_band: Optional[str],
    pricing_mode: str, confidence: Decimal, adjustment: Decimal, final_premium: Decimal,
    rate_of_change_capped: bool, is_cold_start: bool, contributors: list[PricingContributor],
) -> str:
    lines = [f"Base premium: ₹{base_premium:.2f}"]

    if is_cold_start:
        lines.append("Rider has no completed-shift history yet — cold-start default pricing applied.")
        lines.append(f"Pricing mode: {pricing_mode}")
    else:
        lines.append(f"Risk score: {risk_score:.0f}/100 ({risk_band})")
        lines.append(f"Pricing mode: {pricing_mode} (confidence: {confidence:.2f})")
        sign = "+" if adjustment >= 0 else "-"
        label = "Risk-based surcharge" if adjustment >= 0 else "Risk-based discount"
        lines.append(f"{label}: {sign}₹{abs(adjustment):.2f}")
        if contributors:
            lines.append("Major behavioural contributors to the risk score:")
            for c in contributors:
                if c.impact_points == 0:
                    continue
                c_sign = "+" if c.impact_points >= 0 else "-"
                lines.append(f"  - {c.factor}: {c_sign}{abs(c.impact_points):.1f} pts ({c.direction})")

    if rate_of_change_capped:
        lines.append("Note: change from the previous shift's premium was capped to avoid an extreme jump.")

    lines.append(f"Final next-shift premium: ₹{final_premium:.2f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DB orchestration entry point (requirement #9): the ONLY inputs are
# rider_id and server-side state — nothing from a request body ever
# reaches compute_premium_quote(). There is no parameter anywhere in this
# module's public API for a client-supplied premium amount; requirement
# #8 ("do not allow the client to submit or override the premium") is
# therefore enforced by the function signature itself, not by a runtime
# check that could be bypassed or forgotten at a call site.
# ---------------------------------------------------------------------------


def get_previous_premium(db, rider_id) -> Decimal:
    """The most recently STARTED shift's premium_amount for this rider, or
    BASE_PREMIUM if they have none yet (their very first shift has nothing
    to rate-of-change-cap against). Numeric(10,2) column — already Decimal
    from SQLAlchemy, read directly, never routed through float."""
    from db.models.shift import Shift

    last_shift = (
        db.query(Shift)
        .filter(Shift.rider_id == rider_id)
        .order_by(Shift.start_time.desc())
        .first()
    )
    if last_shift is None:
        return BASE_PREMIUM
    return _to_decimal(last_shift.premium_amount)


def calculate_premium_quote(db, rider_id) -> PremiumQuote:
    """Requirement #9's DB-orchestration entry point:
        rider_id -> RiderBehaviourProfile -> risk assessment
                 -> previous premium -> PremiumQuote

    Deliberately calls BOTH rider_behaviour_risk_service.assess_rider_risk()
    (for the actual risk_score/band/confidence/mode/model_version — the
    live scoring path, baseline or XGBoost, with its own fallback-safety
    already handled there) AND behaviour_risk_baseline_service.assess_
    rider_risk() directly (purely to obtain the transparent per-factor
    `contributors` breakdown for the human-readable explanation — see
    PricingContributor's docstring for why this is honest even on the
    XGBoost path). Calling the baseline twice this way is cheap (it's a
    pure function over an already-loaded profile, no extra DB or model
    I/O) and keeps this service from having to invent its own second
    explanation mechanism.
    """
    from db.models.rider_behaviour_profile import RiderBehaviourProfile

    profile = (
        db.query(RiderBehaviourProfile)
        .filter(RiderBehaviourProfile.rider_id == rider_id)
        .first()
    )

    risk_result = risk_service.assess_rider_risk(profile)
    baseline_assessment = baseline_service.assess_rider_risk(profile)
    previous_premium = get_previous_premium(db, rider_id)

    return compute_premium_quote(
        rider_id=rider_id,
        is_cold_start=risk_result.is_cold_start,
        risk_score=risk_result.risk_score,
        risk_band=risk_result.risk_band,
        confidence=risk_result.confidence,
        scoring_method=risk_result.scoring_method,
        model_version=risk_result.model_version,
        previous_premium=previous_premium,
        contributors=baseline_assessment.contributors,
    )


# ---------------------------------------------------------------------------
# Phase 7: audit-trail persistence (db/models/premium_quote.py).
# ---------------------------------------------------------------------------


def persist_premium_quote(db, quote: PremiumQuote, shift_id) -> "PremiumQuoteRecord":
    """Writes the ACTUAL PremiumQuote that priced a shift into
    premium_quotes, one row per shift (unique constraint on shift_id) —
    answers "why was this rider charged Rs.X for this shift?" without
    recomputing anything later, since a rider's profile/risk keeps
    changing after this snapshot is taken.

    Caller's responsibility: `shift_id` must already exist in the DB
    (flush the Shift row first) — the FK is RESTRICT, same convention as
    every other shift_id FK in this codebase. Does not commit; the caller
    controls the transaction boundary (same pattern as
    rider_behaviour_profile_service.rebuild_rider_profile).
    """
    from db.models.premium_quote import PremiumQuoteRecord

    record = PremiumQuoteRecord(
        shift_id=shift_id,
        rider_id=quote.rider_id,
        is_cold_start=quote.is_cold_start,
        risk_score=quote.risk_score,
        risk_band=quote.risk_band,
        confidence=quote.confidence,
        scoring_method=quote.scoring_method,
        model_version=quote.model_version,
        pricing_mode=quote.pricing_mode,
        base_premium=quote.base_premium,
        previous_premium=quote.previous_premium,
        adjustment_amount=quote.adjustment_amount,
        final_premium=quote.final_premium,
        rate_of_change_capped=quote.rate_of_change_capped,
        explanation=quote.explanation,
        computed_at=quote.computed_at,
    )
    db.add(record)
    return record
