import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import ast
import inspect
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import app.core.config  # noqa: F401 — triggers load_dotenv before db.core.session
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.shift_behaviour_summary import ShiftBehaviourSummary
from db.models.rider_behaviour_profile import RiderBehaviourProfile
from db.models.enums import UserRole, ShiftStatus
from app.services import rider_behaviour_profile_service
from app.services import premium_pricing_service as pricing


# ---------------------------------------------------------------------------
# Pure-function tests: compute_premium_quote(), no DB involved. These are
# the bulk of requirement #12's coverage — every combination is exercised
# directly against the deterministic core, independent of the DB
# orchestration layer.
# ---------------------------------------------------------------------------


def _uncapped_target(risk_score, base=None, confidence_scale=Decimal("1")):
    """Mirrors the production smooth-adjustment formula to compute what
    the premium would be with NO rate-of-change interference, so it can be
    used as previous_premium in a test that wants to isolate the smooth
    formula/hard-bounds/confidence-scaling from the rate-of-change cap."""
    base = base if base is not None else pricing.BASE_PREMIUM
    fraction = pricing._smooth_adjustment_fraction(pricing._to_decimal(risk_score))
    raw = base + base * fraction * confidence_scale
    return pricing._clamp_decimal(raw, pricing.MIN_PREMIUM, pricing.MAX_PREMIUM)


def _quote(risk_score=None, confidence=0.9, is_cold_start=False, previous_premium=None,
           contributors=None, base_premium=None, risk_band="MODERATE"):
    kwargs = dict(
        rider_id=uuid.uuid4(),
        is_cold_start=is_cold_start,
        risk_score=risk_score,
        risk_band=risk_band if not is_cold_start else None,
        confidence=confidence,
        scoring_method="deterministic_baseline",
        model_version="behaviour-risk-baseline-v1",
        previous_premium=previous_premium if previous_premium is not None else pricing.BASE_PREMIUM,
        contributors=contributors or [],
    )
    if base_premium is not None:
        kwargs["base_premium"] = base_premium
    return pricing.compute_premium_quote(**kwargs)


class TestRiskScoreSweep:
    """Requirement #12: risk scores 0/25/50/75/100, with previous_premium
    chosen wide enough each time that the rate-of-change cap does not
    interfere — isolating the smooth adjustment formula itself."""

    def test_risk_score_0_gives_a_discount(self):
        q = _quote(risk_score=0.0, previous_premium=Decimal("2.50"))
        assert q.final_premium == Decimal("2.50")
        assert q.adjustment_amount == Decimal("-2.50")
        assert q.pricing_mode == pricing.PRICING_MODE_PERSONALIZED

    def test_risk_score_25(self):
        q = _quote(risk_score=25.0, previous_premium=Decimal("3.75"))
        assert q.final_premium == Decimal("3.75")
        assert q.adjustment_amount == Decimal("-1.25")

    def test_risk_score_50_is_neutral(self):
        q = _quote(risk_score=50.0, previous_premium=pricing.BASE_PREMIUM)
        assert q.final_premium == pricing.BASE_PREMIUM
        assert q.adjustment_amount == Decimal("0.00")

    def test_risk_score_75(self):
        q = _quote(risk_score=75.0, previous_premium=Decimal("6.25"))
        assert q.final_premium == Decimal("6.25")
        assert q.adjustment_amount == Decimal("1.25")

    def test_risk_score_100_gives_a_surcharge(self):
        q = _quote(risk_score=100.0, previous_premium=Decimal("7.50"))
        assert q.final_premium == Decimal("7.50")
        assert q.adjustment_amount == Decimal("2.50")

    def test_adjustment_is_monotonic_in_risk_score(self):
        scores = [0, 10, 25, 40, 50, 60, 75, 90, 100]
        premiums = [
            _quote(risk_score=float(s), previous_premium=_uncapped_target(s)).final_premium
            for s in scores
        ]
        assert premiums == sorted(premiums)

    def test_no_five_band_cliff_edges(self):
        """Requirement #4: adjacent whole-number risk scores must produce
        DIFFERENT prices almost everywhere — proves this isn't secretly
        five discrete bands in disguise."""
        premiums = [
            _quote(risk_score=float(s), previous_premium=_uncapped_target(s)).final_premium
            for s in range(0, 101)
        ]
        distinct = len(set(premiums))
        assert distinct > 20  # far more than 5 discrete values


class TestColdStart:
    def test_cold_start_uses_base_premium(self):
        q = _quote(is_cold_start=True, risk_score=None, confidence=0.0, previous_premium=pricing.BASE_PREMIUM)
        assert q.pricing_mode == pricing.PRICING_MODE_COLD_START_DEFAULT
        assert q.final_premium == pricing.BASE_PREMIUM
        assert q.risk_score is None
        assert q.contributors == []

    def test_cold_start_ignores_risk_score_if_somehow_present(self):
        # Defensive: is_cold_start=True must win even if a stray risk_score
        # value is also passed (should never happen from a real caller).
        q = _quote(is_cold_start=True, risk_score=95.0, previous_premium=pricing.BASE_PREMIUM)
        assert q.pricing_mode == pricing.PRICING_MODE_COLD_START_DEFAULT
        assert q.final_premium == pricing.BASE_PREMIUM


class TestConfidenceGatedPricingMode:
    def test_high_confidence_is_personalized(self):
        q = _quote(risk_score=90.0, confidence=0.9, previous_premium=_uncapped_target(90.0))
        assert q.pricing_mode == pricing.PRICING_MODE_PERSONALIZED
        high_conf_adjustment = q.adjustment_amount

        low_scale = Decimal("0.1") / pricing.HIGH_CONFIDENCE_THRESHOLD
        q_low = _quote(risk_score=90.0, confidence=0.1,
                        previous_premium=_uncapped_target(90.0, confidence_scale=low_scale))
        assert q_low.pricing_mode == pricing.PRICING_MODE_CONSERVATIVE_DEFAULT
        # Low-confidence adjustment must be strictly smaller in magnitude.
        assert abs(q_low.adjustment_amount) < abs(high_conf_adjustment)

    def test_low_confidence_dampens_but_does_not_zero_the_adjustment(self):
        scale = Decimal("0.05") / pricing.HIGH_CONFIDENCE_THRESHOLD
        q = _quote(risk_score=90.0, confidence=0.05, previous_premium=_uncapped_target(90.0, confidence_scale=scale))
        assert q.pricing_mode == pricing.PRICING_MODE_CONSERVATIVE_DEFAULT
        assert q.adjustment_amount > Decimal("0.00")

    def test_confidence_exactly_at_threshold_is_personalized(self):
        q = _quote(risk_score=90.0, confidence=float(pricing.HIGH_CONFIDENCE_THRESHOLD),
                    previous_premium=_uncapped_target(90.0))
        assert q.pricing_mode == pricing.PRICING_MODE_PERSONALIZED


class TestHardBounds:
    """previous_premium is deliberately set to MIN_PREMIUM/MAX_PREMIUM
    (the most extreme value a REAL previous premium could ever legally be
    — see get_previous_premium/the top-of-function clamp, which means a
    stored previous_premium is always already within bounds) so the
    rate-of-change cap cannot itself be the reason the boundary holds;
    these tests isolate the hard-bound clamp specifically."""

    def test_minimum_premium_enforced(self):
        q = _quote(risk_score=0.0, confidence=1.0, base_premium=Decimal("2.00"),
                    previous_premium=pricing.MIN_PREMIUM)
        assert q.final_premium == pricing.MIN_PREMIUM

    def test_maximum_premium_enforced(self):
        q = _quote(risk_score=100.0, confidence=1.0, base_premium=Decimal("20.00"),
                    previous_premium=pricing.MAX_PREMIUM)
        assert q.final_premium == pricing.MAX_PREMIUM

    def test_final_premium_never_below_min_across_sweep(self):
        for s in range(0, 101, 5):
            q = _quote(risk_score=float(s), base_premium=Decimal("0.50"),
                        previous_premium=pricing.MIN_PREMIUM)
            assert q.final_premium >= pricing.MIN_PREMIUM

    def test_final_premium_never_above_max_across_sweep(self):
        for s in range(0, 101, 5):
            q = _quote(risk_score=float(s), base_premium=Decimal("50.00"),
                        previous_premium=pricing.MAX_PREMIUM)
            assert q.final_premium <= pricing.MAX_PREMIUM


class TestRateOfChangeCap:
    def test_extreme_jump_from_previous_premium_is_capped(self):
        q = _quote(risk_score=100.0, confidence=1.0, previous_premium=Decimal("5.00"))
        # Raw target would be 7.50 (base 5 * 1.5); cap limits the move.
        assert q.rate_of_change_capped is True
        max_step = max(Decimal("5.00") * pricing.MAX_RATE_OF_CHANGE_FRACTION, pricing.MAX_RATE_OF_CHANGE_FLOOR)
        assert q.final_premium == Decimal("5.00") + max_step

    def test_within_cap_is_not_flagged(self):
        q = _quote(risk_score=52.0, confidence=1.0, previous_premium=Decimal("5.00"))
        assert q.rate_of_change_capped is False

    def test_cap_works_symmetrically_for_discounts(self):
        q = _quote(risk_score=0.0, confidence=1.0, previous_premium=Decimal("5.00"))
        assert q.rate_of_change_capped is True
        max_step = max(Decimal("5.00") * pricing.MAX_RATE_OF_CHANGE_FRACTION, pricing.MAX_RATE_OF_CHANGE_FLOOR)
        assert q.final_premium == Decimal("5.00") - max_step

    def test_cap_has_a_rupee_floor_even_at_low_previous_premium(self):
        # previous_premium * 25% would be tiny at MIN_PREMIUM; the Rs.1
        # floor must still apply so the price can meaningfully move.
        q = _quote(risk_score=100.0, confidence=1.0, base_premium=Decimal("20.00"),
                    previous_premium=pricing.MIN_PREMIUM)
        assert q.final_premium == pricing.MIN_PREMIUM + pricing.MAX_RATE_OF_CHANGE_FLOOR


class TestDecimalPrecision:
    def test_result_types_are_decimal(self):
        q = _quote(risk_score=33.0, previous_premium=pricing.BASE_PREMIUM)
        assert isinstance(q.final_premium, Decimal)
        assert isinstance(q.base_premium, Decimal)
        assert isinstance(q.adjustment_amount, Decimal)
        assert isinstance(q.previous_premium, Decimal)

    def test_exact_decimal_arithmetic_no_float_drift(self):
        q = _quote(risk_score=33.0, previous_premium=pricing.BASE_PREMIUM)
        assert q.final_premium == Decimal("4.15")

    def test_quantized_to_two_decimal_places(self):
        q = _quote(risk_score=17.0, previous_premium=pricing.BASE_PREMIUM)
        assert q.final_premium == q.final_premium.quantize(Decimal("0.01"))
        assert q.final_premium.as_tuple().exponent == -2

    def test_final_premium_equals_base_plus_adjustment_exactly(self):
        q = _quote(risk_score=68.0, previous_premium=pricing.BASE_PREMIUM)
        assert q.final_premium == q.base_premium + q.adjustment_amount


class TestNegativeAndInvalidInputs:
    def test_negative_risk_score_is_clamped_to_zero(self):
        q_neg = _quote(risk_score=-40.0, previous_premium=pricing.BASE_PREMIUM)
        q_zero = _quote(risk_score=0.0, previous_premium=pricing.BASE_PREMIUM)
        assert q_neg.final_premium == q_zero.final_premium

    def test_risk_score_above_100_is_clamped(self):
        q_over = _quote(risk_score=250.0, previous_premium=pricing.BASE_PREMIUM)
        q_max = _quote(risk_score=100.0, previous_premium=pricing.BASE_PREMIUM)
        assert q_over.final_premium == q_max.final_premium

    def test_negative_confidence_is_clamped_to_zero(self):
        q = _quote(risk_score=90.0, confidence=-5.0, previous_premium=pricing.BASE_PREMIUM)
        assert q.confidence == 0.0
        assert q.pricing_mode == pricing.PRICING_MODE_CONSERVATIVE_DEFAULT

    def test_confidence_above_1_is_clamped(self):
        q = _quote(risk_score=90.0, confidence=99.0, previous_premium=pricing.BASE_PREMIUM)
        assert q.confidence == 1.0

    def test_negative_previous_premium_is_clamped_into_bounds(self):
        q = _quote(risk_score=50.0, previous_premium=Decimal("-500.00"))
        assert q.previous_premium >= pricing.MIN_PREMIUM


class TestDeterminism:
    def test_identical_inputs_produce_identical_prices(self):
        q1 = _quote(risk_score=61.0, confidence=0.7, previous_premium=Decimal("5.50"))
        q2 = _quote(risk_score=61.0, confidence=0.7, previous_premium=Decimal("5.50"))
        assert q1.final_premium == q2.final_premium
        assert q1.adjustment_amount == q2.adjustment_amount
        assert q1.pricing_mode == q2.pricing_mode
        assert q1.rate_of_change_capped == q2.rate_of_change_capped

    def test_repeated_calls_are_stable_across_many_runs(self):
        results = {
            _quote(risk_score=42.0, confidence=0.6, previous_premium=Decimal("6.00")).final_premium
            for _ in range(20)
        }
        assert len(results) == 1


class TestExplanationAndContributors:
    def test_explanation_contains_base_and_final_premium(self):
        q = _quote(risk_score=72.0, previous_premium=pricing.BASE_PREMIUM)
        assert "Base premium: ₹5.00" in q.explanation
        assert f"Final next-shift premium: ₹{q.final_premium:.2f}" in q.explanation

    def test_explanation_lists_named_behavioural_contributors(self):
        from app.services.behaviour_risk_baseline_service import RiskContributor
        contributors = [
            RiskContributor("recent_overspeeding_rate", 9.0, "increases_risk"),
            RiskContributor("recent_hard_braking_rate", 6.0, "increases_risk"),
            RiskContributor("recent_sharp_turn_rate", 0.0, "neutral"),
        ]
        q = _quote(risk_score=80.0, previous_premium=pricing.BASE_PREMIUM, contributors=contributors)
        assert "recent_overspeeding_rate" in q.explanation
        assert "recent_hard_braking_rate" in q.explanation
        # Zero-impact contributors are not listed (they'd be noise, not signal).
        assert "recent_sharp_turn_rate" not in q.explanation

    def test_contributors_sorted_by_magnitude_and_capped_to_five(self):
        from app.services.behaviour_risk_baseline_service import RiskContributor
        contributors = [RiskContributor(f"factor_{i}", float(i), "increases_risk") for i in range(1, 9)]
        q = _quote(risk_score=80.0, previous_premium=pricing.BASE_PREMIUM, contributors=contributors)
        assert len(q.contributors) == 5
        assert q.contributors[0].factor == "factor_8"

    def test_rate_of_change_capped_note_appears_when_capped(self):
        q = _quote(risk_score=100.0, confidence=1.0, previous_premium=Decimal("5.00"))
        assert q.rate_of_change_capped is True
        assert "capped" in q.explanation.lower()


# ---------------------------------------------------------------------------
# Adversarial: prove the client cannot inject/override a premium amount.
# ---------------------------------------------------------------------------


class TestAntiTampering:
    def test_compute_premium_quote_has_no_client_overridable_price_parameter(self):
        params = set(inspect.signature(pricing.compute_premium_quote).parameters.keys())
        forbidden = {"premium_amount", "final_premium", "override_premium", "client_premium", "price"}
        assert params.isdisjoint(forbidden)

    def test_calculate_premium_quote_only_accepts_db_and_rider_id(self):
        params = list(inspect.signature(pricing.calculate_premium_quote).parameters.keys())
        assert params == ["db", "rider_id"]

    def test_passing_an_unexpected_price_kwarg_raises_typeerror(self):
        with pytest.raises(TypeError):
            pricing.compute_premium_quote(
                rider_id=uuid.uuid4(), is_cold_start=False, risk_score=50.0, risk_band="MODERATE",
                confidence=0.9, scoring_method="deterministic_baseline", model_version="v1",
                previous_premium=Decimal("5.00"), final_premium=Decimal("999.00"),
            )

    def test_service_module_does_not_import_shift_request_schemas(self):
        """Architectural proof, not just a runtime check: the pricing
        service has no code path that could even read a client-supplied
        premium — it never imports the schema that carries one."""
        with open(pricing.__file__, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_names.add(node.module)
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported_names.update(alias.name for alias in node.names)
        assert "ShiftStart" not in imported_names
        assert "app.schemas" not in imported_names

    def test_final_premium_is_identical_regardless_of_a_simulated_client_claim(self):
        """Simulates two callers of the DB-orchestration entry point for
        the SAME rider/DB-state, one of which imagines it 'wants' a
        different premium — since calculate_premium_quote(db, rider_id)
        has no parameter through which that desire could even be
        expressed, both calls must produce the identical, server-computed
        price."""
        db = SessionLocal()
        rand_id = uuid.uuid4()
        rand_str = str(rand_id.int)[:8]
        user = User(
            id=rand_id, email=f"test_pricing_tamper_{rand_str}@example.com",
            phone_number=f"+1995{rand_str}", hashed_password="x", full_name="Tamper Test Rider",
            role=UserRole.RIDER, wallet_balance=500.0, is_active=True,
        )
        db.add(user)
        db.commit()
        try:
            # "Attacker" call — there is simply no argument to smuggle a
            # premium through; calling with only (db, rider_id) IS the
            # attack surface, and it's empty by construction.
            q1 = pricing.calculate_premium_quote(db, user.id)
            q2 = pricing.calculate_premium_quote(db, user.id)
            assert q1.final_premium == q2.final_premium
        finally:
            db.query(User).filter(User.id == user.id).delete()
            db.commit()
            db.close()


# ---------------------------------------------------------------------------
# DB-orchestration integration tests: calculate_premium_quote(db, rider_id)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_rider():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id, email=f"test_pricing_service_{rand_str}@example.com",
        phone_number=f"+1996{rand_str}", hashed_password="hashed_test_pass",
        full_name="Test Pricing Rider", role=UserRole.RIDER, wallet_balance=500.0, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    try:
        db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user.id).delete()
        db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.rider_id == user.id).delete()
        db.query(Shift).filter(Shift.rider_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _make_shift(rider_id, premium_amount=5.0, start_offset_hours=1):
    db = SessionLocal()
    shift = Shift(
        rider_id=rider_id, status=ShiftStatus.COMPLETED,
        start_time=datetime.now(timezone.utc) - timedelta(hours=start_offset_hours),
        end_time=datetime.now(timezone.utc) - timedelta(hours=start_offset_hours - 1),
        premium_amount=premium_amount,
        policy_number=f"POL-PRICING-{uuid.uuid4().hex[:8].upper()}", distance_km=5.0,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    shift_id = shift.id
    db.close()
    return shift_id


def _insert_summary(rider_id, shift_id, created_at, hard_braking_rate=2.0, overspeeding_rate=0.5):
    db = SessionLocal()
    db.add(ShiftBehaviourSummary(
        shift_id=shift_id, rider_id=rider_id,
        duration_seconds=600, distance_km=5.0, sample_count=50,
        average_speed=30.0, max_speed=45.0,
        hard_braking_count=2, hard_acceleration_count=1, overspeeding_count=0, sharp_turn_count=1,
        hard_braking_rate=hard_braking_rate, hard_acceleration_rate=1.0,
        overspeeding_rate=overspeeding_rate, sharp_turn_rate=1.0,
        max_g=1.4, accel_std=0.2, jerk_mean=0.1,
        sampling_density=5.0, data_quality_score=0.9, is_valid=True,
        created_at=created_at,
    ))
    db.commit()
    db.close()


def _real_profile(rider_id, n_shifts=6, hard_braking_rate=2.0, overspeeding_rate=0.5):
    for i in range(n_shifts):
        shift_id = _make_shift(rider_id, start_offset_hours=n_shifts - i + 1)
        _insert_summary(rider_id, shift_id, datetime.now(timezone.utc) - timedelta(hours=i),
                         hard_braking_rate=hard_braking_rate, overspeeding_rate=overspeeding_rate)
    db = SessionLocal()
    profile = rider_behaviour_profile_service.rebuild_rider_profile(db, rider_id)
    db.commit()
    db.close()
    return profile


class TestCalculatePremiumQuoteIntegration:
    def test_cold_start_rider_gets_base_premium(self, test_rider):
        db = SessionLocal()
        try:
            q = pricing.calculate_premium_quote(db, test_rider.id)
            assert q.is_cold_start is True
            assert q.pricing_mode == pricing.PRICING_MODE_COLD_START_DEFAULT
            assert q.final_premium == pricing.BASE_PREMIUM
        finally:
            db.close()

    def test_real_profile_produces_a_bounded_decimal_quote(self, test_rider):
        _real_profile(test_rider.id)
        db = SessionLocal()
        try:
            q = pricing.calculate_premium_quote(db, test_rider.id)
            assert q.is_cold_start is False
            assert isinstance(q.final_premium, Decimal)
            assert pricing.MIN_PREMIUM <= q.final_premium <= pricing.MAX_PREMIUM
            assert q.contributors  # baseline contributors present for explanation
        finally:
            db.close()

    def test_previous_premium_read_from_most_recent_shift(self, test_rider):
        _make_shift(test_rider.id, premium_amount=9.00, start_offset_hours=1)
        _make_shift(test_rider.id, premium_amount=3.00, start_offset_hours=48)  # older
        db = SessionLocal()
        try:
            prev = pricing.get_previous_premium(db, test_rider.id)
            assert prev == Decimal("9.00")
        finally:
            db.close()

    def test_no_prior_shift_defaults_previous_premium_to_base(self, test_rider):
        db = SessionLocal()
        try:
            prev = pricing.get_previous_premium(db, test_rider.id)
            assert prev == pricing.BASE_PREMIUM
        finally:
            db.close()

    def test_riskier_profile_produces_higher_or_equal_premium_than_safer_profile(self):
        db = SessionLocal()
        safe_rand, risky_rand = uuid.uuid4(), uuid.uuid4()
        safe_user = User(
            id=safe_rand, email=f"safe_{str(safe_rand.int)[:8]}@example.com",
            phone_number=f"+1997{str(safe_rand.int)[:8]}", hashed_password="x",
            full_name="Safe Rider", role=UserRole.RIDER, wallet_balance=500.0, is_active=True,
        )
        risky_user = User(
            id=risky_rand, email=f"risky_{str(risky_rand.int)[:8]}@example.com",
            phone_number=f"+1998{str(risky_rand.int)[:8]}", hashed_password="x",
            full_name="Risky Rider", role=UserRole.RIDER, wallet_balance=500.0, is_active=True,
        )
        db.add_all([safe_user, risky_user])
        db.commit()
        try:
            _real_profile(safe_user.id, hard_braking_rate=0.0, overspeeding_rate=0.0)
            _real_profile(risky_user.id, hard_braking_rate=15.0, overspeeding_rate=10.0)
            # previous_premium == BASE_PREMIUM for both riders: close enough
            # to the expected raw targets that the rate-of-change cap does
            # not swallow the risk-based difference (unlike MAX_PREMIUM,
            # which would pull both far-apart raw targets up to the same
            # capped floor and mask the very difference this test checks).
            for rid in (safe_user.id, risky_user.id):
                _make_shift(rid, premium_amount=float(pricing.BASE_PREMIUM), start_offset_hours=1)

            q_safe = pricing.calculate_premium_quote(db, safe_user.id)
            q_risky = pricing.calculate_premium_quote(db, risky_user.id)
            assert q_risky.final_premium >= q_safe.final_premium
        finally:
            for rid in (safe_user.id, risky_user.id):
                db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == rid).delete()
                db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.rider_id == rid).delete()
                db.query(Shift).filter(Shift.rider_id == rid).delete()
                db.query(User).filter(User.id == rid).delete()
            db.commit()
            db.close()


class TestIsolationFromCrashMlEngine:
    def test_service_does_not_import_ml_incident_engine(self):
        with open(pricing.__file__, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert not any("ml_incident_engine" in m for m in imported_modules)
        assert not any(m in ("xgboost", "behaviour_risk_engine") or (m and "behaviour_risk_engine" in m)
                        for m in imported_modules)
