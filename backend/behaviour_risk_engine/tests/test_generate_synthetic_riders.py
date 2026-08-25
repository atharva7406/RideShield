import numpy as np
import pytest

from behaviour_risk_engine import config as cfg
from behaviour_risk_engine.generate_synthetic_riders import generate_rider, generate_riders


class TestGenerateRiderBasics:
    @pytest.mark.parametrize("archetype", cfg.ARCHETYPES)
    def test_every_archetype_can_produce_a_rider(self, archetype):
        rng = np.random.default_rng(1)
        found = False
        for _ in range(10):  # noisy/sparse archetypes occasionally yield zero valid shifts
            rider = generate_rider(rng, archetype=archetype)
            if rider is not None:
                found = True
                assert 0.0 <= rider.true_risk <= 100.0
                assert rider.archetype == archetype
                break
        assert found, f"{archetype} never produced a valid rider in 10 attempts"

    def test_true_risk_is_not_a_feature_of_the_snapshot(self):
        # The latent label must never leak into the aggregated features.
        rng = np.random.default_rng(2)
        rider = generate_rider(rng, archetype="consistently_aggressive")
        snapshot_attrs = vars(rider.profile_snapshot)
        assert "true_risk" not in snapshot_attrs
        assert "archetype" not in snapshot_attrs

    def test_reproducible_with_same_seed(self):
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        r1 = generate_rider(rng1, archetype="mixed")
        r2 = generate_rider(rng2, archetype="mixed")
        assert r1.true_risk == pytest.approx(r2.true_risk)
        assert r1.profile_snapshot.overall_behaviour_score == pytest.approx(r2.profile_snapshot.overall_behaviour_score)

    def test_no_nan_in_snapshot_fields(self):
        rng = np.random.default_rng(3)
        rider = generate_rider(rng, archetype="noisy_low_quality")
        if rider is None:
            pytest.skip("noisy_low_quality happened to yield zero valid shifts this seed")
        for tier_name in ("recent", "medium", "long_term"):
            tier = getattr(rider.profile_snapshot, tier_name)
            for field_value in vars(tier).values():
                if isinstance(field_value, float):
                    assert np.isfinite(field_value)


class TestArchetypeBehaviour:
    def test_consistently_safe_has_low_true_risk(self):
        rng = np.random.default_rng(10)
        risks = []
        for _ in range(20):
            r = generate_rider(rng, archetype="consistently_safe")
            if r:
                risks.append(r.true_risk)
        assert np.mean(risks) < 35.0

    def test_consistently_aggressive_has_high_true_risk(self):
        rng = np.random.default_rng(11)
        risks = []
        for _ in range(20):
            r = generate_rider(rng, archetype="consistently_aggressive")
            if r:
                risks.append(r.true_risk)
        assert np.mean(risks) > 65.0

    def test_dominant_signal_archetypes_elevate_the_right_feature(self):
        rng = np.random.default_rng(12)
        overspeeding_riders = [generate_rider(rng, archetype="high_overspeeding") for _ in range(15)]
        overspeeding_riders = [r for r in overspeeding_riders if r]
        braking_riders = [generate_rider(rng, archetype="high_hard_braking") for _ in range(15)]
        braking_riders = [r for r in braking_riders if r]

        mean_os_in_os_group = np.mean([r.profile_snapshot.recent.overspeeding_rate for r in overspeeding_riders])
        mean_os_in_braking_group = np.mean([r.profile_snapshot.recent.overspeeding_rate for r in braking_riders])
        assert mean_os_in_os_group > mean_os_in_braking_group

    def test_improving_rider_recent_tier_looks_safer_than_long_term_tier(self):
        rng = np.random.default_rng(13)
        found = False
        for _ in range(15):
            r = generate_rider(rng, archetype="improving")
            if r and r.num_shifts >= 10:  # need enough history for long_term to differ from recent
                found = True
                assert r.profile_snapshot.recent.hard_braking_rate <= r.profile_snapshot.long_term.hard_braking_rate + 3.0
                break
        assert found

    def test_deteriorating_rider_recent_tier_looks_worse_than_long_term_tier(self):
        rng = np.random.default_rng(14)
        found = False
        for _ in range(15):
            r = generate_rider(rng, archetype="deteriorating")
            if r and r.num_shifts >= 10:
                found = True
                assert r.profile_snapshot.recent.hard_braking_rate >= r.profile_snapshot.long_term.hard_braking_rate - 3.0
                break
        assert found

    def test_noisy_low_quality_has_lower_data_quality_than_safe(self):
        rng = np.random.default_rng(15)
        noisy = [generate_rider(rng, archetype="noisy_low_quality") for _ in range(15)]
        noisy = [r for r in noisy if r]
        safe = [generate_rider(rng, archetype="consistently_safe") for _ in range(15)]
        safe = [r for r in safe if r]
        assert np.mean([r.profile_snapshot.data_quality_score for r in noisy]) < \
               np.mean([r.profile_snapshot.data_quality_score for r in safe])

    def test_sparse_telemetry_can_legitimately_yield_no_rider(self):
        # Not asserting it ALWAYS fails — just that None is a possible,
        # handled outcome, not a crash.
        rng = np.random.default_rng(16)
        results = [generate_rider(rng, archetype="sparse_telemetry") for _ in range(30)]
        assert all(r is None or 0.0 <= r.true_risk <= 100.0 for r in results)


class TestGenerateRiders:
    def test_produces_requested_count_when_possible(self):
        riders = generate_riders(n_riders=50, seed=1)
        assert len(riders) <= 50
        assert len(riders) > 40  # most archetypes should succeed most of the time

    def test_reproducible_dataset_generation(self):
        r1 = generate_riders(n_riders=30, seed=99)
        r2 = generate_riders(n_riders=30, seed=99)
        assert [r.rider_id for r in r1] == [r.rider_id for r in r2]
        assert [r.true_risk for r in r1] == [r.true_risk for r in r2]

    def test_rider_ids_are_unique(self):
        riders = generate_riders(n_riders=100, seed=7)
        ids = [r.rider_id for r in riders]
        assert len(ids) == len(set(ids))

    def test_multiple_archetypes_present(self):
        riders = generate_riders(n_riders=200, seed=5)
        archetypes = {r.archetype for r in riders}
        assert len(archetypes) >= 8
