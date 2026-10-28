import numpy as np
from eeg_pipeline.spectral_features import spectral_features

def test_dominant_alpha_and_power():
    sf=256; t=np.arange(0, 4, 1/sf); x=np.sin(2*np.pi*10*t)[None, :]
    out=spectral_features(x, sf, alpha_peak_min_snr=1.0)
    assert abs(out["paf_hz"][0]-10) < 1.0
    assert out["absolute_alpha_power"][0] > out["absolute_theta_power"][0]

def test_theta_alpha_ratio():
    sf=256; t=np.arange(0, 4, 1/sf); x=(np.sin(2*np.pi*6*t)+.5*np.sin(2*np.pi*10*t))[None,:]
    out=spectral_features(x,sf)
    assert out["theta_alpha_ratio"][0] > 1

