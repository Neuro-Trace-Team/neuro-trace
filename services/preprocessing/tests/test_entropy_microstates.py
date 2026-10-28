import numpy as np
from eeg_pipeline.entropy import permutation_entropy
from eeg_pipeline.microstates import microstate_metrics

def test_entropy_range():
    value=permutation_entropy(np.sin(np.linspace(0,20,1000)))
    assert 0 <= value <= 1

def test_microstate_metrics():
    rng=np.random.default_rng(2); rows=microstate_metrics(rng.normal(size=(19,1000)), 100, 4)
    assert len(rows)==4
    assert all(0 <= row["coverage"] <= 1 for row in rows)

