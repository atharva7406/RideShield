import pandas as pd
import pytest

from behaviour_risk_engine import config as cfg
from behaviour_risk_engine.dataset import riders_to_dataframe, split_riders_by_id
from behaviour_risk_engine.generate_synthetic_riders import generate_riders
from behaviour_risk_engine.sanity_checks import (
    SanityCheckError,
    check_archetype_diversity,
    check_no_constant_features,
    check_no_fully_dead_features,
    check_no_rider_leakage,
    check_target_not_constant,
    check_target_range,
    run_sanity_checks,
)


@pytest.fixture(scope="module")
def splits():
    riders = generate_riders(n_riders=150, seed=321)
    df = riders_to_dataframe(riders)
    return split_riders_by_id(df, seed=1)


class TestHealthyDatasetPasses:
    def test_run_sanity_checks_passes(self, splits):
        train_df, val_df, test_df = splits
        report = run_sanity_checks(train_df, val_df, test_df)
        assert report["train_riders"] == len(train_df)


class TestCriticalRiderLevelSplitCheck:
    """This is the CRITICAL test called out explicitly in the Phase 4
    spec: the same rider must never appear in more than one split."""

    def test_no_rider_appears_in_more_than_one_split(self, splits):
        train_df, val_df, test_df = splits
        check_no_rider_leakage(train_df, val_df, test_df)  # raises on failure

        train_ids = set(train_df["rider_id"])
        val_ids = set(val_df["rider_id"])
        test_ids = set(test_df["rider_id"])
        assert train_ids.isdisjoint(val_ids)
        assert train_ids.isdisjoint(test_ids)
        assert val_ids.isdisjoint(test_ids)

    def test_catches_a_rider_planted_in_two_splits(self, splits):
        train_df, val_df, test_df = splits
        leaked = pd.concat([test_df, train_df.iloc[[0]]], ignore_index=True)
        with pytest.raises(AssertionError):
            check_no_rider_leakage(train_df, val_df, leaked)


class TestIndividualChecks:
    def test_target_range_catches_out_of_bounds(self, splits):
        train_df, _, _ = splits
        broken = train_df.copy()
        broken.loc[broken.index[0], cfg.TARGET_NAME] = 150.0
        with pytest.raises(SanityCheckError):
            check_target_range(broken)

    def test_target_not_constant_catches_degenerate_target(self, splits):
        train_df, _, _ = splits
        broken = train_df.copy()
        broken[cfg.TARGET_NAME] = 50.0
        with pytest.raises(SanityCheckError):
            check_target_not_constant(broken)

    def test_no_dead_features_passes_on_real_data(self, splits):
        train_df, _, _ = splits
        check_no_fully_dead_features(train_df)

    def test_no_constant_features_catches_zeroed_column(self, splits):
        train_df, _, _ = splits
        broken = train_df.copy()
        broken["recent_hard_braking_rate"] = 0.0
        with pytest.raises(SanityCheckError):
            check_no_constant_features(broken)

    def test_archetype_diversity_catches_too_few_archetypes(self, splits):
        train_df, _, _ = splits
        broken = train_df[train_df["archetype"] == train_df["archetype"].iloc[0]]
        with pytest.raises(SanityCheckError):
            check_archetype_diversity(broken)
