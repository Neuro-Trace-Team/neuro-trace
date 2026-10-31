"""Build the one-row-per-epoch feature table from existing CSV tables."""

from __future__ import annotations

from pathlib import Path
from numbers import Number
from typing import Iterable

import pandas as pd


MICROSTATE_COLUMNS = {
    "duration_ms": "duration",
    "coverage": "coverage",
    "occurrence_per_s": "occurrence",
}
NETWORK_PRIORITY = (
    "global_efficiency",
    "local_efficiency",
    "characteristic_path_length",
)
NETWORK_METRIC_CANDIDATES = NETWORK_PRIORITY + ("clustering_coefficient",)
DEFAULT_EPOCH_KEYS = ("experiment_id", "subject_id", "recording_id", "window_id")


def _expected_microstate_columns() -> list[str]:
    return [
        f"microstate_{state}_{label}"
        for state in range(4)
        for label in MICROSTATE_COLUMNS.values()
    ]


def _expected_network_columns() -> list[str]:
    return [f"{band}_{metric}" for band in ("delta", "theta", "alpha", "beta") for metric in NETWORK_PRIORITY]


def _epoch_keys(*frames: pd.DataFrame) -> list[str]:
    """Return the shared recording/epoch identity columns in stable order."""
    base = frames[0]
    keys = [
        name for name in DEFAULT_EPOCH_KEYS
        if name in base.columns and all(frame.empty or name in frame.columns for frame in frames[1:])
    ]
    if keys != list(DEFAULT_EPOCH_KEYS):
        raise ValueError(
            "Feature tables must contain experiment_id, subject_id, recording_id and window_id"
        )
    return keys


def _assert_unique(frame: pd.DataFrame, keys: Iterable[str], description: str) -> None:
    key_list = list(keys)
    if frame.duplicated(key_list).any():
        duplicates = frame.loc[frame.duplicated(key_list, keep=False), key_list].drop_duplicates()
        raise ValueError(f"Duplicate {description} keys: {duplicates.to_dict('records')}")


def _pivot_microstates(microstates: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if microstates.empty:
        return pd.DataFrame(columns=keys + _expected_microstate_columns())
    required = set(keys) | {"microstate_class"}
    missing = required - set(microstates.columns)
    if missing:
        raise ValueError(f"microstates.csv is missing columns: {sorted(missing)}")
    _assert_unique(microstates, [*keys, "microstate_class"], "microstate")

    values = [column for column in MICROSTATE_COLUMNS if column in microstates.columns]
    if not values:
        return pd.DataFrame(columns=keys)
    classes = pd.to_numeric(microstates["microstate_class"], errors="coerce")
    selected = microstates.loc[classes.notna()].copy()
    selected["microstate_class"] = classes.loc[classes.notna()].astype(int)
    pivoted = selected.pivot(index=keys, columns="microstate_class", values=values)
    pivoted.columns = [
        f"microstate_{int(state)}_{MICROSTATE_COLUMNS[metric]}"
        for metric, state in pivoted.columns
    ]
    pivoted = pivoted.reset_index()
    expected = _expected_microstate_columns()
    for column in expected:
        if column not in pivoted:
            pivoted[column] = pd.NA
    return pivoted[keys + expected]


def _is_scalar_number(value) -> bool:
    return isinstance(value, Number)


def _pivot_network_metrics(network: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if network.empty:
        return pd.DataFrame(columns=keys + _expected_network_columns())
    required = set(keys) | {"band"}
    missing = required - set(network.columns)
    if missing:
        raise ValueError(f"network_metrics.csv is missing columns: {sorted(missing)}")
    _assert_unique(network, [*keys, "band"], "network")

    excluded = set(keys) | {"band"}
    metric_columns = []
    for column in network.columns:
        if column in excluded or column not in NETWORK_METRIC_CANDIDATES:
            continue
        values = network[column].dropna()
        if len(values) and all(_is_scalar_number(value) for value in values):
            numeric = pd.to_numeric(values, errors="coerce")
            if numeric.notna().any():
                metric_columns.append(column)
    # Arrays such as node degree and node strength are intentionally excluded.
    if not metric_columns:
        return pd.DataFrame(columns=keys)
    pivoted = network.pivot(index=keys, columns="band", values=metric_columns)
    pivoted.columns = [f"{str(band).lower()}_{metric}" for metric, band in pivoted.columns]
    return pivoted.reset_index()


def combine_feature_tables(
    features: pd.DataFrame,
    microstates: pd.DataFrame,
    network_metrics: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join pivoted derived features onto the original features table."""
    # In event mode every requested event can legitimately be rejected (for
    # example when it falls outside the recording). In that case
    # ``pd.DataFrame([])`` has no columns, so there are no identifiers to
    # validate. Still emit a well-shaped empty combined table.
    if features.empty and not len(features.columns) and microstates.empty and network_metrics.empty:
        return pd.DataFrame(columns=list(DEFAULT_EPOCH_KEYS) + _expected_microstate_columns() + _expected_network_columns())
    keys = _epoch_keys(features, microstates, network_metrics)
    _assert_unique(features, keys, "base feature")
    micro_pivot = _pivot_microstates(microstates, keys)
    network_pivot = _pivot_network_metrics(network_metrics, keys)
    _assert_unique(micro_pivot, keys, "pivoted microstate") if not micro_pivot.empty else None
    _assert_unique(network_pivot, keys, "pivoted network") if not network_pivot.empty else None

    combined = features.merge(micro_pivot, on=keys, how="left", sort=False, validate="one_to_one")
    combined = combined.merge(network_pivot, on=keys, how="left", sort=False, validate="one_to_one")
    if len(combined) != len(features):
        raise AssertionError("combined_features row count differs from features.csv")
    if combined[keys].duplicated().any():
        raise AssertionError("combined_features contains duplicate epoch identifiers")
    return combined


def export_combined_features(output_dir: str | Path) -> pd.DataFrame:
    """Read the existing exports, create and write combined_features.csv."""
    output = Path(output_dir)
    features = pd.read_csv(output / "features.csv")
    microstates = pd.read_csv(output / "microstates.csv")
    network_metrics = pd.read_csv(output / "network_metrics.csv")
    combined = combine_feature_tables(features, microstates, network_metrics)
    combined.to_csv(output / "combined_features.csv", index=False)
    return combined
