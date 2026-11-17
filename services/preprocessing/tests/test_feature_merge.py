import numpy as np
import pandas as pd
import pytest

from eeg_pipeline.feature_merge import combine_feature_tables


KEYS = {"experiment_id": "exp", "subject_id": "sub", "recording_id": "run", "window_id": 0}


def test_combined_features_pivots_without_mixing_recordings():
    features = pd.DataFrame([
        {**KEYS, "relative_alpha_power": 1.0},
        {**KEYS, "window_id": 1, "relative_alpha_power": 2.0},
    ])
    microstates = pd.DataFrame([
        {**KEYS, "microstate_class": 0, "duration_ms": 10, "coverage": .2, "occurrence_per_s": 1},
        {**KEYS, "window_id": 1, "microstate_class": 1, "duration_ms": 20, "coverage": .3, "occurrence_per_s": 2},
        {**KEYS, "recording_id": "other", "microstate_class": 0, "duration_ms": 99, "coverage": .9, "occurrence_per_s": 9},
    ])
    network = pd.DataFrame([
        {**KEYS, "band": "alpha", "global_efficiency": .5, "local_efficiency": .2,
         "characteristic_path_length": 3, "node_degree": np.arange(19)},
        {**KEYS, "window_id": 1, "band": "delta", "global_efficiency": .4,
         "local_efficiency": .1, "characteristic_path_length": 4, "node_degree": np.arange(19)},
    ])

    result = combine_feature_tables(features, microstates, network)

    assert len(result) == len(features)
    assert list(result["window_id"]) == [0, 1]
    assert result.loc[0, "microstate_0_duration"] == 10
    assert pd.isna(result.loc[0, "microstate_1_duration"])
    assert result.loc[1, "microstate_1_occurrence"] == 2
    assert result.loc[0, "alpha_global_efficiency"] == .5
    assert result.loc[1, "delta_global_efficiency"] == .4
    assert "alpha_node_degree" not in result


def test_duplicate_epoch_band_is_rejected():
    features = pd.DataFrame([{**KEYS, "feature": 1}])
    microstates = pd.DataFrame([{**KEYS, "microstate_class": 0, "duration_ms": 1}])
    network = pd.DataFrame([
        {**KEYS, "band": "alpha", "global_efficiency": 1},
        {**KEYS, "band": "alpha", "global_efficiency": 2},
    ])
    with pytest.raises(ValueError, match="Duplicate network"):
        combine_feature_tables(features, microstates, network)


def test_empty_event_result_still_has_combined_schema():
    result = combine_feature_tables(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert result.empty
    assert "window_id" in result.columns
    assert "microstate_3_occurrence" in result.columns
    assert "beta_characteristic_path_length" in result.columns
