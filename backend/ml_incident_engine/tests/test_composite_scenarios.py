"""
Regression tests for Phase 1's joint/composite ambiguity scenarios, written
BEFORE the generator changes that implement them (see generate_synthetic_data
.py). Each scenario has a `force_*` keyword on generate_event() specifically
so these tests can request a scenario deterministically instead of hoping a
random draw happens to trigger it — the *unforced*, probabilistic behavior
is checked separately in TestCompositesAppearInFullDatasetGeneration.

These exist because the Phase 3 baseline (99% accuracy, PR-AUC=1.0000)
showed the model wasn't learning a single-feature shortcut, but the classes
were still too separable *jointly* — no real crash dataset has this little
simultaneous ambiguity. This suite locks in that composite/overlapping
scenarios actually exist in the data, not just individually-overlapping
feature ranges.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml_incident_engine import config as cfg
from ml_incident_engine.feature_extraction import extract_feature_vector
from ml_incident_engine.generate_synthetic_data import generate_dataset, generate_event


class TestPotholeWithConcurrentTurn:
    """'pothole + sharp turn': hitting a pothole while mid-turn — still a
    pothole event, but with real, sustained gyro elevation on top of its
    own small transient bump."""

    def test_forced_composite_has_higher_gyro_than_plain_pothole(self):
        rng_a, rng_b = np.random.default_rng(500), np.random.default_rng(500)
        plain = generate_event("pothole", rng_a, rider_id="r", shift_id="s", force_concurrent_turn=False)
        composite = generate_event("pothole", rng_b, rider_id="r", shift_id="s", force_concurrent_turn=True)
        assert extract_feature_vector(composite)["gyro_peak"] > extract_feature_vector(plain)["gyro_peak"]

    def test_composite_is_still_labeled_pothole(self):
        rng = np.random.default_rng(501)
        w = generate_event("pothole", rng, rider_id="r", shift_id="s", force_concurrent_turn=True)
        assert w.class_label == "pothole"

    def test_composite_gyro_reaches_into_sharp_turns_range(self):
        rng = np.random.default_rng(1)
        peaks = [
            extract_feature_vector(
                generate_event("pothole", rng, rider_id="r", shift_id="s", force_concurrent_turn=True)
            )["gyro_peak"]
            for _ in range(30)
        ]
        assert max(peaks) > cfg.GENERATION_PARAMS["sharp_turn"]["gyro_peak_deg_s_range"][0] * 0.5


class TestHardBrakingWithConcurrentTurn:
    """'hard braking + turn': braking into a corner — keeps its own speed
    drop, but gyro is no longer a clean near-zero."""

    def test_forced_composite_has_higher_gyro_than_plain_hard_braking(self):
        rng_a, rng_b = np.random.default_rng(600), np.random.default_rng(600)
        plain = generate_event("hard_braking", rng_a, rider_id="r", shift_id="s", force_concurrent_turn=False)
        composite = generate_event("hard_braking", rng_b, rider_id="r", shift_id="s", force_concurrent_turn=True)
        assert extract_feature_vector(composite)["gyro_peak"] > extract_feature_vector(plain)["gyro_peak"]

    def test_composite_keeps_its_speed_drop_signature(self):
        rng = np.random.default_rng(601)
        w = generate_event("hard_braking", rng, rider_id="r", shift_id="s", force_concurrent_turn=True)
        assert w.class_label == "hard_braking"
        f = extract_feature_vector(w)
        assert f["speed_drop"] is not None and f["speed_drop"] > 5.0


class TestPotholeAtHigherSpeed:
    """Calibrated against the reference CSV's pothole_non_crash (speed
    mean ~32, up to ~45 km/h — well above this generator's plain
    15-45 km/h uniform range) — a pothole hit while actually riding fast,
    with proportionally larger impact energy."""

    def test_forced_high_speed_variant_has_higher_speed_than_plain(self):
        rng_a, rng_b = np.random.default_rng(700), np.random.default_rng(700)
        normal = generate_event("pothole", rng_a, rider_id="r", shift_id="s", force_high_speed=False)
        high = generate_event("pothole", rng_b, rider_id="r", shift_id="s", force_high_speed=True)
        f_normal, f_high = extract_feature_vector(normal), extract_feature_vector(high)
        assert (f_high["speed_before"] or 0) > (f_normal["speed_before"] or 0)

    def test_high_speed_variant_has_larger_impact_amplitude_on_average(self):
        rng1, rng2 = np.random.default_rng(2), np.random.default_rng(3)
        normal_peaks = [
            extract_feature_vector(
                generate_event("pothole", rng1, rider_id="r", shift_id="s", force_high_speed=False)
            )["accel_peak_g"]
            for _ in range(30)
        ]
        high_peaks = [
            extract_feature_vector(
                generate_event("pothole", rng2, rider_id="r", shift_id="s", force_high_speed=True)
            )["accel_peak_g"]
            for _ in range(30)
        ]
        assert np.mean(high_peaks) > np.mean(normal_peaks)


class TestSharpTurnEvasiveCrashLikeWithoutCrash:
    """'crash-like acceleration without crash': an evasive swerve — real,
    large accel/gyro reaching into crash-adjacent territory, but with no
    genuine speed drop and (mostly) no post-impact stillness, so the
    multi-signal logic still correctly keeps it out of the crash class.
    Loosely anchored to the reference CSV's near_miss_non_crash (gyroMag
    up to ~68 deg/s at 1Hz — plausibly higher at true sensor resolution)."""

    def test_forced_evasive_reaches_crash_adjacent_gyro(self):
        rng = np.random.default_rng(800)
        w = generate_event("sharp_turn", rng, rider_id="r", shift_id="s", force_evasive=True)
        f = extract_feature_vector(w)
        assert f["gyro_peak"] >= cfg.EVASIVE_GYRO_DEG_S_RANGE[0]

    def test_forced_evasive_has_no_meaningful_speed_drop(self):
        rng = np.random.default_rng(801)
        results = []
        for _ in range(20):
            w = generate_event("sharp_turn", rng, rider_id="r", shift_id="s", force_evasive=True)
            f = extract_feature_vector(w)
            results.append(f["speed_drop"] or 0)
        assert np.mean(results) < 10.0  # nowhere near crash's ~30 kph mean

    def test_evasive_still_labeled_sharp_turn_not_crash(self):
        rng = np.random.default_rng(802)
        w = generate_event("sharp_turn", rng, rider_id="r", shift_id="s", force_evasive=True)
        assert w.class_label == "sharp_turn"


class TestCrashWeakOrPartialPostImpactStillness:
    """Replaces the old instant clear/partial/none noise-level switch with
    a physically-motivated settling PHASE (impact -> decaying residual
    motion -> either true stillness or continued movement), calibrated
    against the reference CSV's crash_post_impact phase (real residual
    gyroMag ~35 deg/s mean, not near-silence)."""

    def test_forced_non_settling_crash_shows_real_residual_motion(self):
        rng = np.random.default_rng(900)
        w = generate_event("crash", rng, rider_id="r", shift_id="s", force_full_stillness=False)
        f = extract_feature_vector(w)
        assert f["post_impact_accel_variance"] is not None
        assert f["post_impact_accel_variance"] > cfg.STILLNESS_ACCEL_VARIANCE_THRESHOLD
        assert f["post_impact_stillness"] is False

    def test_forced_settling_crash_can_still_reach_true_stillness(self):
        rng = np.random.default_rng(901)
        results = [
            extract_feature_vector(
                generate_event("crash", rng, rider_id="r", shift_id="s", force_full_stillness=True)
            )["post_impact_stillness"]
            for _ in range(30)
        ]
        assert sum(results) > 0

    def test_settling_phase_produces_intermediate_not_binary_motion_levels(self):
        # The multi-phase model should show a genuine decaying-but-not-yet-
        # still intermediate level for at least some crash events (the
        # "weak/partial" cases specifically) — not just a hard switch
        # between "silent" and "full normal noise".
        rng = np.random.default_rng(902)
        intermediate_gyro_stds = []
        for _ in range(60):
            w = generate_event("crash", rng, rider_id="r", shift_id="s")
            f = extract_feature_vector(w)
            if f["post_impact_gyro_variance"] is not None:
                intermediate_gyro_stds.append(f["post_impact_gyro_variance"] ** 0.5)
        assert any(5.0 < std < 60.0 for std in intermediate_gyro_stds)


class TestSensorMisalignmentAndNoise:
    """'noisy/misaligned sensor readings': a class-agnostic generation-time
    mode simulating a poorly-mounted or lower-quality phone — a small fixed
    tilt applied to the whole window plus elevated baseline noise. Distinct
    from apply_random_rotation (a large, arbitrary augmentation used for
    orientation-invariance testing) — this is a *moderate*, base-generation
    realism factor, not a post-hoc augmentation."""

    def test_forced_misalignment_changes_raw_axis_values(self):
        rng_a, rng_b = np.random.default_rng(1000), np.random.default_rng(1000)
        plain = generate_event("normal", rng_a, rider_id="r", shift_id="s", force_misalignment=False)
        misaligned = generate_event("normal", rng_b, rider_id="r", shift_id="s", force_misalignment=True)
        assert not np.allclose(plain.accel_x, misaligned.accel_x)

    def test_forced_misalignment_increases_average_feature_noise(self):
        rng1, rng2 = np.random.default_rng(4), np.random.default_rng(5)
        plain_std = [
            extract_feature_vector(
                generate_event("normal", rng1, rider_id="r", shift_id="s", force_misalignment=False)
            )["accel_std"]
            for _ in range(30)
        ]
        misaligned_std = [
            extract_feature_vector(
                generate_event("normal", rng2, rider_id="r", shift_id="s", force_misalignment=True)
            )["accel_std"]
            for _ in range(30)
        ]
        assert np.mean(misaligned_std) > np.mean(plain_std)

    def test_misalignment_can_apply_to_any_class_without_changing_its_label(self):
        rng = np.random.default_rng(1001)
        w = generate_event("crash", rng, rider_id="r", shift_id="s", force_misalignment=True)
        assert w.class_label == "crash"


class TestCompositesAppearUnforcedInFullDatasetGeneration:
    """The forced tests above prove the mechanisms work; this proves they
    actually fire under normal (probabilistic) generate_dataset() use,
    not just when explicitly requested."""

    def test_dataset_contains_some_high_gyro_potholes(self):
        windows = generate_dataset(events_per_class=60, augmentations_per_event=0,
                                    num_riders=10, shifts_per_rider=2, seed=2024)
        pothole_gyro_peaks = [
            extract_feature_vector(w)["gyro_peak"]
            for w in windows if w.class_label == "pothole"
        ]
        # Plain pothole's own gyro_bump tops out at gyro_bump_deg_s_range[1]
        # (40 deg/s, see config.GENERATION_PARAMS) — some events clearing
        # that is evidence the concurrent-turn composite fired unforced.
        plain_max = cfg.GENERATION_PARAMS["pothole"]["gyro_bump_deg_s_range"][1]
        assert any(g > plain_max for g in pothole_gyro_peaks)

    def test_dataset_contains_some_evasive_sharp_turns(self):
        windows = generate_dataset(events_per_class=60, augmentations_per_event=0,
                                    num_riders=10, shifts_per_rider=2, seed=2025)
        sharp_turn_gyro_peaks = [
            extract_feature_vector(w)["gyro_peak"]
            for w in windows if w.class_label == "sharp_turn"
        ]
        assert any(g > cfg.EVASIVE_GYRO_DEG_S_RANGE[0] for g in sharp_turn_gyro_peaks)

    def test_dataset_contains_some_non_settling_crashes(self):
        windows = generate_dataset(events_per_class=60, augmentations_per_event=0,
                                    num_riders=10, shifts_per_rider=2, seed=2026)
        crash_stillness = [
            extract_feature_vector(w)["post_impact_stillness"]
            for w in windows if w.class_label == "crash"
        ]
        assert not all(crash_stillness)  # not every crash settles
        assert any(crash_stillness)  # but most/some still do
