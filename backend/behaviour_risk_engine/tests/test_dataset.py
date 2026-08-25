from pathlib import Path

import pandas as pd
import pytest

from behaviour_risk_engine import config as cfg
from behaviour_risk_engine.dataset import (
    assert_no_rider_leakage,
    build_and_save,
    load_dataset,
    riders_to_dataframe,
    save_dataset,
    split_riders_by_id,
)
from behaviour_risk_engine.generate_synthetic_riders import generate_riders


@pytest.fixture(scope="module")
def small_df():
    riders = generate_riders(n_riders=150, seed=123)
    return riders_to_dataframe(riders)


class TestRidersToDataframe:
    def test_expected_columns(self, small_df):
        expected = ["rider_id", "archetype", "num_shifts", cfg.TARGET_NAME] + cfg.FEATURE_NAMES
        assert list(small_df.columns) == expected

    def test_feature_columns_match_real_rider_behaviour_profile_model(self, small_df):
        from db.models.rider_behaviour_profile import RiderBehaviourProfile
        import sys, os
        backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        model_columns = {c.name for c in RiderBehaviourProfile.__table__.columns}
        # Every tier/overall feature name (after stripping tier prefixes
        # that don't exist verbatim, e.g. "recent_avg_speed" IS a real
        # column) must correspond to a real column.
        for name in cfg.FEATURE_NAMES:
            assert name in model_columns, f"{name} is not a real RiderBehaviourProfile column"

    def test_target_in_range(self, small_df):
        assert small_df[cfg.TARGET_NAME].between(0, 100).all()

    def test_no_duplicate_rider_ids(self, small_df):
        assert small_df["rider_id"].nunique() == len(small_df)


class TestSplitRidersById:
    def test_no_leakage(self, small_df):
        train_df, val_df, test_df = split_riders_by_id(small_df, seed=1)
        assert_no_rider_leakage(train_df, val_df, test_df)  # raises on failure

    def test_leakage_check_detects_a_planted_duplicate(self, small_df):
        train_df, val_df, test_df = split_riders_by_id(small_df, seed=1)
        corrupted_val = pd.concat([val_df, train_df.iloc[[0]]], ignore_index=True)
        with pytest.raises(AssertionError):
            assert_no_rider_leakage(train_df, corrupted_val, test_df)

    def test_every_row_lands_in_exactly_one_split(self, small_df):
        train_df, val_df, test_df = split_riders_by_id(small_df, seed=1)
        assert len(train_df) + len(val_df) + len(test_df) == len(small_df)

    def test_split_is_reproducible(self, small_df):
        t1, v1, te1 = split_riders_by_id(small_df, seed=5)
        t2, v2, te2 = split_riders_by_id(small_df, seed=5)
        assert set(t1["rider_id"]) == set(t2["rider_id"])
        assert set(te1["rider_id"]) == set(te2["rider_id"])

    def test_multiple_archetypes_present_in_every_split(self, small_df):
        train_df, val_df, test_df = split_riders_by_id(small_df, seed=1)
        assert train_df["archetype"].nunique() >= 5
        assert test_df["archetype"].nunique() >= 3


class TestSaveLoadRoundTrip:
    def test_parquet_round_trip(self, small_df, tmp_path):
        path = tmp_path / "riders.parquet"
        save_dataset(small_df, path)
        loaded = load_dataset(path)
        assert len(loaded) == len(small_df)
        pd.testing.assert_frame_equal(
            loaded.sort_values("rider_id").reset_index(drop=True),
            small_df.sort_values("rider_id").reset_index(drop=True),
            check_dtype=False,
        )


class TestBuildAndSave:
    def test_end_to_end_pipeline(self, tmp_path):
        summary = build_and_save(output_dir=tmp_path, n_riders=100, seed=3)
        assert summary["total_riders"] <= 100
        assert summary["train_riders"] + summary["val_riders"] + summary["test_riders"] == summary["total_riders"]
        assert (Path(tmp_path) / "synthetic_riders_full.parquet").exists()
        assert (Path(tmp_path) / "synthetic_riders_train.parquet").exists()
        assert (Path(tmp_path) / "synthetic_riders_val.parquet").exists()
        assert (Path(tmp_path) / "synthetic_riders_test.parquet").exists()
