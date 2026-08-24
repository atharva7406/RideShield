from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml_incident_engine import config as cfg
from ml_incident_engine.dataset import (
    METADATA_COLUMNS,
    assert_no_group_leakage,
    build_and_save,
    load_dataset,
    save_dataset,
    split_dataset,
    windows_to_dataframe,
)
from ml_incident_engine.feature_extraction import FEATURE_NAMES
from ml_incident_engine.generate_synthetic_data import generate_dataset


@pytest.fixture(scope="module")
def small_windows():
    return generate_dataset(events_per_class=15, augmentations_per_event=3,
                             num_riders=5, shifts_per_rider=2, seed=123)


@pytest.fixture(scope="module")
def small_df(small_windows):
    return windows_to_dataframe(small_windows)


class TestWindowsToDataframe:
    def test_row_count_matches_window_count(self, small_windows, small_df):
        assert len(small_df) == len(small_windows)

    def test_expected_columns_present(self, small_df):
        assert list(small_df.columns) == METADATA_COLUMNS + FEATURE_NAMES

    def test_no_missing_metadata(self, small_df):
        for col in ("event_id", "rider_id", "shift_id", "class_label", "source_event_id", "group_key"):
            assert small_df[col].notna().all()

    def test_group_key_equals_event_id_for_originals(self, small_df):
        originals = small_df[~small_df["is_augmented"]]
        assert (originals["group_key"] == originals["event_id"]).all()

    def test_group_key_equals_source_event_id_for_augmented(self, small_df):
        augmented = small_df[small_df["is_augmented"]]
        assert (augmented["group_key"] == augmented["source_event_id"]).all()
        # And that source_event_id actually points at a real original event.
        original_ids = set(small_df.loc[~small_df["is_augmented"], "event_id"])
        assert set(augmented["source_event_id"]).issubset(original_ids)


class TestSplitDataset:
    def test_no_group_leakage_across_splits(self, small_df):
        train_df, val_df, test_df = split_dataset(small_df, test_size=0.2, val_size=0.1, seed=1)
        assert_no_group_leakage(train_df, val_df, test_df)  # raises on failure

    def test_leakage_check_actually_detects_leakage(self, small_df):
        train_df, val_df, test_df = split_dataset(small_df, test_size=0.2, val_size=0.1, seed=1)
        corrupted_val = pd.concat([val_df, train_df.iloc[[0]]], ignore_index=True)
        with pytest.raises(AssertionError):
            assert_no_group_leakage(train_df, corrupted_val, test_df)

    def test_split_sizes_are_roughly_as_requested(self, small_df):
        train_df, val_df, test_df = split_dataset(small_df, test_size=0.2, val_size=0.1, seed=1)
        total = len(small_df)
        assert len(train_df) + len(val_df) + len(test_df) == total
        # Group-based splitting means sizes are approximate, not exact.
        assert 0.55 * total < len(train_df) < 0.85 * total
        assert len(test_df) > 0
        assert len(val_df) > 0

    def test_augmented_siblings_stay_with_their_original(self, small_df):
        train_df, val_df, test_df = split_dataset(small_df, test_size=0.2, val_size=0.1, seed=1)
        row_to_split = {}
        for name, df in (("train", train_df), ("val", val_df), ("test", test_df)):
            for event_id in df["event_id"]:
                row_to_split[event_id] = name

        # Every augmented row's split must match the split its own original
        # (source) event landed in — proves siblings travel together.
        originals_split = {
            row["event_id"]: row_to_split[row["event_id"]]
            for _, row in small_df[~small_df["is_augmented"]].iterrows()
        }
        for _, row in small_df[small_df["is_augmented"]].iterrows():
            assert row_to_split[row["event_id"]] == originals_split[row["source_event_id"]]

    def test_split_is_reproducible_with_same_seed(self, small_df):
        t1, v1, te1 = split_dataset(small_df, seed=7)
        t2, v2, te2 = split_dataset(small_df, seed=7)
        assert list(t1["event_id"]) == list(t2["event_id"])
        assert list(te1["event_id"]) == list(te2["event_id"])


class TestSaveLoadRoundTrip:
    def test_parquet_round_trip_preserves_data(self, small_df, tmp_path):
        path = tmp_path / "dataset.parquet"
        save_dataset(small_df, path)
        loaded = load_dataset(path)

        assert len(loaded) == len(small_df)
        assert list(loaded.columns) == list(small_df.columns)
        pd.testing.assert_frame_equal(
            loaded.sort_values("event_id").reset_index(drop=True),
            small_df.sort_values("event_id").reset_index(drop=True),
            check_dtype=False,
        )


class TestBuildAndSave:
    def test_end_to_end_pipeline_runs_and_reports_sane_summary(self, tmp_path):
        summary = build_and_save(
            output_dir=tmp_path,
            events_per_class=8,
            augmentations_per_event=2,
            num_riders=3,
            shifts_per_rider=2,
            seed=5,
        )

        assert summary["total_windows"] == len(cfg.EVENT_CLASSES) * 8 * 3
        assert summary["total_base_events"] == len(cfg.EVENT_CLASSES) * 8
        assert set(summary["class_distribution_full"].keys()) == set(cfg.EVENT_CLASSES)
        assert (Path(tmp_path) / "synthetic_dataset_full.parquet").exists()
        assert (Path(tmp_path) / "synthetic_dataset_train.parquet").exists()
        assert (Path(tmp_path) / "synthetic_dataset_val.parquet").exists()
        assert (Path(tmp_path) / "synthetic_dataset_test.parquet").exists()
