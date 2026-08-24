"""
Assembles generated TelemetryWindows into a flat, tabular dataset (one row
per window, one column per feature + metadata) and provides a group-based
train/val/test split that never lets windows from the same base event end
up in more than one split.

Grouping key: a window's "base event identity" is its own event_id if it's
an original (is_augmented=False), or its source_event_id if it's an
augmented sibling. Splitting on this key means an original event and every
one of its augmented variants always land in the same split together —
without this, augmentation would leak information across the split even if
raw event_id-only grouping looked correct.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from . import config as cfg
from .feature_extraction import FEATURE_NAMES, extract_feature_vector
from .generate_synthetic_data import TelemetryWindow

METADATA_COLUMNS = [
    "event_id", "rider_id", "shift_id", "class_label",
    "is_augmented", "source_event_id", "group_key",
]


def windows_to_dataframe(windows: list[TelemetryWindow]) -> pd.DataFrame:
    rows = []
    for w in windows:
        feats = extract_feature_vector(w)
        row = {
            "event_id": w.event_id,
            "rider_id": w.rider_id,
            "shift_id": w.shift_id,
            "class_label": w.class_label,
            "is_augmented": w.is_augmented,
            "source_event_id": w.source_event_id,
            # group_key is what split_dataset() actually groups by — see
            # module docstring. For non-augmented events this equals
            # event_id (== source_event_id already, by construction).
            "group_key": w.source_event_id,
            **feats,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    ordered_columns = METADATA_COLUMNS + FEATURE_NAMES
    return df[ordered_columns]


def _group_split_one_class(class_df: pd.DataFrame, test_size: float, val_size: float,
                            seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    groups = class_df["group_key"].values

    gss_test = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train_val_idx, test_idx = next(gss_test.split(class_df, groups=groups))
    train_val_df = class_df.iloc[train_val_idx]
    test_df = class_df.iloc[test_idx]

    relative_val_size = val_size / (1.0 - test_size)
    gss_val = GroupShuffleSplit(n_splits=1, test_size=relative_val_size, random_state=seed)
    train_idx, val_idx = next(gss_val.split(train_val_df, groups=train_val_df["group_key"].values))

    return train_val_df.iloc[train_idx], train_val_df.iloc[val_idx], test_df


def split_dataset(
    df: pd.DataFrame,
    test_size: float = 0.2,
    val_size: float = 0.1,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Group-based split (grouped by `group_key`, see module docstring),
    done PER CLASS and then concatenated — not pooled across all classes
    at once. A single pooled GroupShuffleSplit doesn't stratify by class,
    so with a modest number of groups per class it's easy for one class to
    land with zero groups in val or test purely by chance (this is exactly
    what a Phase 3 sanity check caught: 'val split is missing classes').
    Splitting per class guarantees every class is represented in every
    split (given enough groups per class to begin with), at the cost of
    doing GroupShuffleSplit N_CLASSES times instead of once — cheap either
    way at this dataset size.

    `test_size`/`val_size` are fractions of each class's own rows; val is
    carved out of what remains after test is removed, same semantics as
    before, just applied within each class rather than across all of them.
    """
    train_parts, val_parts, test_parts = [], [], []
    for class_label in sorted(df["class_label"].unique()):
        class_df = df[df["class_label"] == class_label]
        train_c, val_c, test_c = _group_split_one_class(class_df, test_size, val_size, seed)
        train_parts.append(train_c)
        val_parts.append(val_c)
        test_parts.append(test_c)

    train_df = pd.concat(train_parts, ignore_index=True)
    val_df = pd.concat(val_parts, ignore_index=True)
    test_df = pd.concat(test_parts, ignore_index=True)

    return train_df, val_df, test_df


def assert_no_group_leakage(*dfs: pd.DataFrame) -> None:
    """Raises AssertionError if any group_key appears in more than one of
    the given dataframes. Used both by dataset.py's own tests and safe to
    call again in train_model.py later as a defensive check."""
    seen: dict[str, int] = {}
    for i, df in enumerate(dfs):
        for key in df["group_key"].unique():
            if key in seen and seen[key] != i:
                raise AssertionError(
                    f"Data leakage: group_key {key!r} appears in split {seen[key]} and split {i}"
                )
            seen[key] = i


def class_distribution(df: pd.DataFrame) -> pd.Series:
    return df["class_label"].value_counts()


def save_dataset(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_dataset(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# CLI orchestration
# ---------------------------------------------------------------------------


def build_and_save(
    output_dir: str | Path,
    events_per_class: int = 200,
    augmentations_per_event: int = 3,
    num_riders: int = 20,
    shifts_per_rider: int = 3,
    seed: int = 42,
    test_size: float = 0.2,
    val_size: float = 0.1,
) -> dict:
    # Imported here (not at module top) so `dataset.py` can be imported by
    # other modules without pulling in the generator unless actually needed.
    from .generate_synthetic_data import generate_dataset

    output_dir = Path(output_dir)
    windows = generate_dataset(
        events_per_class=events_per_class,
        augmentations_per_event=augmentations_per_event,
        num_riders=num_riders,
        shifts_per_rider=shifts_per_rider,
        seed=seed,
    )
    df = windows_to_dataframe(windows)

    train_df, val_df, test_df = split_dataset(df, test_size=test_size, val_size=val_size, seed=seed)
    assert_no_group_leakage(train_df, val_df, test_df)

    save_dataset(df, output_dir / "synthetic_dataset_full.parquet")
    save_dataset(train_df, output_dir / "synthetic_dataset_train.parquet")
    save_dataset(val_df, output_dir / "synthetic_dataset_val.parquet")
    save_dataset(test_df, output_dir / "synthetic_dataset_test.parquet")

    summary = {
        "total_windows": len(df),
        "total_base_events": int(df["is_augmented"].eq(False).sum()),
        "total_augmented_windows": int(df["is_augmented"].eq(True).sum()),
        "class_distribution_full": class_distribution(df).to_dict(),
        "class_distribution_train": class_distribution(train_df).to_dict(),
        "class_distribution_val": class_distribution(val_df).to_dict(),
        "class_distribution_test": class_distribution(test_df).to_dict(),
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
    }
    return summary


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Generate the Phase 1 synthetic ML Incident Engine dataset.")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent / "artifacts"))
    parser.add_argument("--events-per-class", type=int, default=200)
    parser.add_argument("--augmentations-per-event", type=int, default=3)
    parser.add_argument("--num-riders", type=int, default=20)
    parser.add_argument("--shifts-per-rider", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = build_and_save(
        output_dir=args.output_dir,
        events_per_class=args.events_per_class,
        augmentations_per_event=args.augmentations_per_event,
        num_riders=args.num_riders,
        shifts_per_rider=args.shifts_per_rider,
        seed=args.seed,
    )
    print(json.dumps(result, indent=2))
