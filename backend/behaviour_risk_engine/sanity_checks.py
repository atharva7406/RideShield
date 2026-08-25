"""Phase 4 pre-training sanity checks — same discipline as
ml_incident_engine/sanity_checks.py: catch data problems (rider leakage,
dead/constant features, degenerate splits) explicitly before they show up
disguised as a suspicious model metric."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .dataset import assert_no_rider_leakage


class SanityCheckError(Exception):
    pass


def check_no_rider_leakage(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    assert_no_rider_leakage(train_df, val_df, test_df)


def check_target_range(df: pd.DataFrame) -> None:
    if df[cfg.TARGET_NAME].min() < 0 or df[cfg.TARGET_NAME].max() > 100:
        raise SanityCheckError(
            f"{cfg.TARGET_NAME} out of [0,100] range: "
            f"min={df[cfg.TARGET_NAME].min()}, max={df[cfg.TARGET_NAME].max()}"
        )


def check_target_not_constant(df: pd.DataFrame) -> None:
    if df[cfg.TARGET_NAME].nunique() <= 1:
        raise SanityCheckError(f"{cfg.TARGET_NAME} is constant across the dataset — nothing to learn")


def check_feature_nan_rates(df: pd.DataFrame) -> pd.Series:
    return df[cfg.FEATURE_NAMES].isna().mean()


def check_no_fully_dead_features(df: pd.DataFrame, max_nan_rate: float = 0.999) -> None:
    nan_rates = check_feature_nan_rates(df)
    dead = nan_rates[nan_rates >= max_nan_rate]
    if len(dead):
        raise SanityCheckError(f"Feature(s) with ~{max_nan_rate:.1%}+ NaN (dead weight): {list(dead.index)}")


def check_no_constant_features(df: pd.DataFrame) -> None:
    numeric_df = df[cfg.FEATURE_NAMES].select_dtypes(include=[np.number, bool])
    constant = [c for c in numeric_df.columns if numeric_df[c].dropna().nunique() <= 1]
    if constant:
        raise SanityCheckError(f"Constant (zero-variance) feature(s): {constant}")


def check_archetype_diversity(df: pd.DataFrame, min_archetypes: int = 8) -> None:
    n = df["archetype"].nunique()
    if n < min_archetypes:
        raise SanityCheckError(f"Only {n} archetypes present, expected at least {min_archetypes}")


def run_sanity_checks(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    check_no_rider_leakage(train_df, val_df, test_df)
    full = pd.concat([train_df, val_df, test_df], ignore_index=True)
    check_target_range(full)
    check_target_not_constant(full)
    check_no_fully_dead_features(train_df)
    check_no_constant_features(train_df)
    check_archetype_diversity(full)

    return {
        "train_riders": len(train_df),
        "val_riders": len(val_df),
        "test_riders": len(test_df),
        "target_min": float(full[cfg.TARGET_NAME].min()),
        "target_max": float(full[cfg.TARGET_NAME].max()),
        "target_mean": float(full[cfg.TARGET_NAME].mean()),
        "archetype_count": int(full["archetype"].nunique()),
        "feature_nan_rates_train": check_feature_nan_rates(train_df).round(4).to_dict(),
    }
