import numpy as np

from eeg_pipeline.baseline import channelwise_changes, global_changes
from eeg_pipeline.config import EPOCH_WINDOWS, PipelineConfig
from eeg_pipeline.entropy import permutation_entropy
from eeg_pipeline.preprocessing import cluster_events


def test_configured_windows_and_cluster_identity():
    assert EPOCH_WINDOWS == {"baseline": (-5.5, -0.5), "early_response": (0.0, 1.0), "sustained_response": (0.5, 5.5)}
    records = cluster_events([10.0, 10.2, 20.0])
    assert [r["cluster_id"] for r in records] == [0, 0, 1]


def test_baseline_aggregation_methods_are_explicitly_different():
    event = np.array([2.0, 20.0]); baseline = np.array([1.0, 10.0])
    mean_relative, mean_db = channelwise_changes(event, baseline)
    global_relative, global_db = global_changes(event, baseline)
    assert np.isclose(mean_relative, 1.0)
    assert np.isclose(global_relative, 1.0)
    assert np.isclose(mean_db, 10 * np.log10(2))
    assert np.isclose(global_db, 10 * np.log10(2))
    assert np.isnan(channelwise_changes(event, [0, np.nan])[0])
    assert np.isnan(global_changes(event, [0, np.nan])[0])


def test_entropy_short_nan_constant_and_normalized():
    assert np.isnan(permutation_entropy(np.ones(5), order=3, delay=1))
    assert permutation_entropy(np.ones(100), order=3, delay=1) == 0
    rng = np.random.default_rng(42)
    value = permutation_entropy(rng.normal(size=1000), order=3, delay=1)
    assert 0 <= value <= 1
