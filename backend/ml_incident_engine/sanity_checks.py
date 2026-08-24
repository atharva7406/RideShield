"""
Phase 3 pre-training sanity checks.

Run before any model touches the dataset — meant to catch data problems
(leakage, dead/constant features, missing classes, degenerate splits)
cheaply and explicitly, before they show up disguised as a suspiciously
good or bad model metric three steps later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .dataset import assert_no_group_leakage
from .feature_extraction import FEATURE_NAMES


class SanityCheckError(Exception):
    pass


def check_no_leakage(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    assert_no_group_leakage(train_df, val_df, test_df)  # raises AssertionError, not SanityCheckError — caller's choice to catch broadly


def check_class_presence(df: pd.DataFrame, split_name: str) -> None:
    missing = set(cfg.EVENT_CLASSES) - set(df["class_label"].unique())
    if missing:
        raise SanityCheckError(f"{split_name} split is missing classes: {sorted(missing)}")


def check_feature_nan_rates(df: pd.DataFrame) -> pd.Series:
    """NaN rate per feature column. Some Optional-typed features
    (speed_drop, post_impact_*_variance, accel_gyro_correlation, ...) are
    EXPECTED to have some NaN — XGBoost handles missing values natively —
    but a ~100% NaN rate on any feature would mean it's dead weight."""
    return df[FEATURE_NAMES].isna().mean()


def check_no_fully_dead_features(df: pd.DataFrame, max_nan_rate: float = 0.999) -> None:
    nan_rates = check_feature_nan_rates(df)
    dead = nan_rates[nan_rates >= max_nan_rate]
    if len(dead):
        raise SanityCheckError(f"Feature(s) with ~{max_nan_rate:.1%}+ NaN (dead weight): {list(dead.index)}")


def check_no_constant_features(df: pd.DataFrame) -> None:
    """A feature with zero variance across the whole split can't help the
    model and may signal a generator bug (e.g. a parameter that never
    actually got randomized)."""
    numeric_df = df[FEATURE_NAMES].select_dtypes(include=[np.number, bool])
    constant = [c for c in numeric_df.columns if numeric_df[c].dropna().nunique() <= 1]
    if constant:
        raise SanityCheckError(f"Constant (zero-variance) feature(s): {constant}")


def check_class_balance(df: pd.DataFrame, split_name: str, min_fraction: float = 0.05) -> None:
    """Not a strict requirement in general, but for THIS dataset every
    class is generated in equal counts (see generate_dataset), so any
    class falling well below an even share signals a split or generation
    problem worth looking at before training."""
    counts = df["class_label"].value_counts(normalize=True)
    too_small = counts[counts < min_fraction]
    if len(too_small):
        raise SanityCheckError(
            f"{split_name} split: class(es) under {min_fraction:.0%} of rows: {too_small.round(4).to_dict()}"
        )


def run_sanity_checks(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    """Runs the full battery in order, raising on the first failure.
    Returns a report dict on success — meant to be printed/logged, not
    just silently discarded, so a human can see what was actually checked."""
    check_no_leakage(train_df, val_df, test_df)
    for name, df in (("train", train_df), ("val", val_df), ("test", test_df)):
        check_class_presence(df, name)
        check_class_balance(df, name)

    check_no_fully_dead_features(train_df)
    check_no_constant_features(train_df)

    return {
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "train_class_counts": train_df["class_label"].value_counts().to_dict(),
        "val_class_counts": val_df["class_label"].value_counts().to_dict(),
        "test_class_counts": test_df["class_label"].value_counts().to_dict(),
        "feature_nan_rates_train": check_feature_nan_rates(train_df).round(4).to_dict(),
    }
