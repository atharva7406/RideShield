"""
Turns a list of SyntheticRider objects into a flat feature DataFrame and a
RIDER-LEVEL train/val/test split — critical requirement (Phase 4 spec
item 4): no rider may appear in more than one split. Since each training
row already IS one rider (a RiderProfileSnapshot aggregates all of that
rider's shifts into a single feature vector — there is no shift-level row
to leak across splits in the first place), the split itself is just a
partition of rider_ids. Verified explicitly in tests anyway, not just
assumed correct from the data shape.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg
from .generate_synthetic_riders import SyntheticRider, generate_riders

METADATA_COLUMNS = ["rider_id", "archetype", "num_shifts"]


def _tier_features(snapshot, tier_name: str) -> dict:
    tier = getattr(snapshot, tier_name)
    return {
        f"{tier_name}_avg_speed": tier.avg_speed,
        f"{tier_name}_max_speed": tier.max_speed,
        f"{tier_name}_hard_braking_rate": tier.hard_braking_rate,
        f"{tier_name}_hard_acceleration_rate": tier.hard_acceleration_rate,
        f"{tier_name}_overspeeding_rate": tier.overspeeding_rate,
        f"{tier_name}_sharp_turn_rate": tier.sharp_turn_rate,
        f"{tier_name}_max_g": tier.max_g,
        f"{tier_name}_data_quality": tier.data_quality,
    }


def rider_to_row(rider: SyntheticRider) -> dict:
    snapshot = rider.profile_snapshot
    row = {
        "rider_id": rider.rider_id,
        "archetype": rider.archetype,
        "num_shifts": rider.num_shifts,
        cfg.TARGET_NAME: rider.true_risk,
    }
    row.update(_tier_features(snapshot, "recent"))
    row.update(_tier_features(snapshot, "medium"))
    row.update(_tier_features(snapshot, "long_term"))
    row.update({
        "overall_behaviour_score": snapshot.overall_behaviour_score,
        "behaviour_consistency_score": snapshot.consistency.consistency_score,
        "data_quality_score": snapshot.data_quality_score,
        "based_on_valid_shift_count": snapshot.based_on_valid_shift_count,
        "based_on_shift_count": snapshot.based_on_shift_count,
        "confidence": snapshot.confidence,
        "hard_braking_rate_variance": snapshot.consistency.hard_braking_rate_variance,
        "overspeeding_rate_variance": snapshot.consistency.overspeeding_rate_variance,
        "speed_variability": snapshot.consistency.speed_variability,
    })
    return row


def riders_to_dataframe(riders: list[SyntheticRider]) -> pd.DataFrame:
    df = pd.DataFrame([rider_to_row(r) for r in riders])
    ordered_columns = METADATA_COLUMNS + [cfg.TARGET_NAME] + cfg.FEATURE_NAMES
    return df[ordered_columns]


def split_riders_by_id(
    df: pd.DataFrame, test_size: float = 0.2, val_size: float = 0.1, seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Splits by rider_id — since one row already equals one rider, this
    is a plain rider-id partition, not a group-split algorithm; done
    per-archetype (stratified) so every split sees every behaviour
    pattern, same reasoning as ml_incident_engine's per-class stratified
    split (a pooled random split can, by chance, drop a whole archetype
    from a small split)."""
    rng = np.random.default_rng(seed)
    train_parts, val_parts, test_parts = [], [], []

    for archetype in sorted(df["archetype"].unique()):
        archetype_df = df[df["archetype"] == archetype].sample(frac=1.0, random_state=seed).reset_index(drop=True)
        n = len(archetype_df)
        n_test = max(1, int(round(n * test_size))) if n >= 3 else (1 if n > 1 else 0)
        n_val = max(1, int(round(n * val_size))) if n >= 5 else (1 if n - n_test > 1 else 0)
        n_test = min(n_test, n)
        n_val = min(n_val, max(0, n - n_test))

        test_parts.append(archetype_df.iloc[:n_test])
        val_parts.append(archetype_df.iloc[n_test:n_test + n_val])
        train_parts.append(archetype_df.iloc[n_test + n_val:])

    train_df = pd.concat(train_parts, ignore_index=True) if train_parts else df.iloc[0:0]
    val_df = pd.concat(val_parts, ignore_index=True) if val_parts else df.iloc[0:0]
    test_df = pd.concat(test_parts, ignore_index=True) if test_parts else df.iloc[0:0]
    return train_df, val_df, test_df


def assert_no_rider_leakage(*dfs: pd.DataFrame) -> None:
    seen: dict[str, int] = {}
    for i, df in enumerate(dfs):
        for rider_id in df["rider_id"]:
            if rider_id in seen and seen[rider_id] != i:
                raise AssertionError(f"Rider leakage: rider_id {rider_id!r} appears in split {seen[rider_id]} and split {i}")
            seen[rider_id] = i


def save_dataset(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_dataset(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def build_and_save(output_dir: str | Path, n_riders: int = 600, seed: int = 42,
                    test_size: float = 0.2, val_size: float = 0.1) -> dict:
    output_dir = Path(output_dir)
    riders = generate_riders(n_riders=n_riders, seed=seed)
    df = riders_to_dataframe(riders)

    train_df, val_df, test_df = split_riders_by_id(df, test_size=test_size, val_size=val_size, seed=seed)
    assert_no_rider_leakage(train_df, val_df, test_df)

    save_dataset(df, output_dir / "synthetic_riders_full.parquet")
    save_dataset(train_df, output_dir / "synthetic_riders_train.parquet")
    save_dataset(val_df, output_dir / "synthetic_riders_val.parquet")
    save_dataset(test_df, output_dir / "synthetic_riders_test.parquet")

    return {
        "total_riders": len(df),
        "requested_riders": n_riders,
        "skipped_zero_valid_shift_riders": n_riders - len(riders) if len(riders) < n_riders else 0,
        "train_riders": len(train_df),
        "val_riders": len(val_df),
        "test_riders": len(test_df),
        "archetype_distribution": df["archetype"].value_counts().to_dict(),
        "target_stats": {
            "min": float(df[cfg.TARGET_NAME].min()),
            "max": float(df[cfg.TARGET_NAME].max()),
            "mean": float(df[cfg.TARGET_NAME].mean()),
            "std": float(df[cfg.TARGET_NAME].std()),
        },
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Generate the Phase 4 synthetic multi-shift rider dataset.")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent / "artifacts"))
    parser.add_argument("--n-riders", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = build_and_save(output_dir=args.output_dir, n_riders=args.n_riders, seed=args.seed)
    print(json.dumps(result, indent=2, default=str))
