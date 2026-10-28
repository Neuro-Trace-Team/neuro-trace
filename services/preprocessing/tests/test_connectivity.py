import numpy as np
from eeg_pipeline.connectivity import connectivity_by_band

def test_connectivity_shape_without_scipy():
    out=connectivity_by_band(np.zeros((19, 256)), 256)
    assert set(out)=={"delta","theta","alpha","beta"}
    assert all(v.shape==(19,19) for v in out.values())

