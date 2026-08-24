import pandas as pd
import pytest

from ml_incident_engine.dataset import split_dataset, windows_to_dataframe
from ml_incident_engine.generate_synthetic_data import generate_dataset
from ml_incident_engine.sanity_checks import (
    SanityCheckError,
    check_class_balance,
    check_class_presence,
    check_no_constant_features,
    check_no_fully_dead_features,
    check_no_leakage,
    run_sanity_checks,
)


@pytest.fixture(scope="module")
def splits():
    windows = generate_dataset(events_per_class=15, augmentations_per_event=2,
                                num_riders=5, shifts_per_rider=2, seed=321)
    df = windows_to_dataframe(windows)
    return split_dataset(df, test_size=0.2, val_size=0.1, seed=1)


class TestHealthyDatasetPassesEverything:
    def test_run_sanity_checks_passes_and_reports(self, splits):
        train_df, val_df, test_df = splits
        report = run_sanity_checks(train_df, val_df, test_df)
        assert report["train_rows"] == len(train_df)
        assert set(report["train_class_counts"].keys()) <= {
            "normal", "hard_braking", "pothole", "sharp_turn", "crash"
        }


class TestIndividualChecksCatchInjectedFailures:
    def test_check_no_leakage_catches_a_duplicated_group(self, splits):
        train_df, val_df, test_df = splits
        corrupted_val = pd.concat([val_df, train_df.iloc[[0]]], ignore_index=True)
        with pytest.raises(AssertionError):
            check_no_leakage(train_df, corrupted_val, test_df)

    def test_check_class_presence_catches_a_missing_class(self, splits):
        train_df, _, _ = splits
        missing_one_class = train_df[train_df["class_label"] != "crash"]
        with pytest.raises(SanityCheckError, match="crash"):
            check_class_presence(missing_one_class, "train")

    def test_check_class_balance_catches_a_near_empty_class(self, splits):
        train_df, _, _ = splits
        crash_rows = train_df[train_df["class_label"] == "crash"]
        # Keep only 1 crash row out of many rows of everything else.
        skewed = pd.concat([
            train_df[train_df["class_label"] != "crash"],
            crash_rows.iloc[:1],
        ], ignore_index=True)
        with pytest.raises(SanityCheckError, match="crash"):
            check_class_balance(skewed, "train", min_fraction=0.05)

    def test_check_no_fully_dead_features_catches_an_all_nan_column(self, splits):
        train_df, _, _ = splits
        broken = train_df.copy()
        broken["speed_drop"] = None
        with pytest.raises(SanityCheckError, match="speed_drop"):
            check_no_fully_dead_features(broken)

    def test_check_no_fully_dead_features_passes_on_partial_nan(self, splits):
        train_df, _, _ = splits
        # speed_drop is Optional and legitimately has some NaN in real data —
        # that alone must not trip the "dead feature" check.
        check_no_fully_dead_features(train_df)

    def test_check_no_constant_features_catches_a_zeroed_out_column(self, splits):
        train_df, _, _ = splits
        broken = train_df.copy()
        broken["accel_std"] = 0.0
        with pytest.raises(SanityCheckError, match="accel_std"):
            check_no_constant_features(broken)

    def test_check_no_constant_features_passes_on_real_data(self, splits):
        train_df, _, _ = splits
        check_no_constant_features(train_df)
