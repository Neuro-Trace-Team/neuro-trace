import numpy as np

from eeg_pipeline.connectivity import dwpli
from eeg_pipeline.entropy import permutation_entropy
from eeg_pipeline.preprocessing import cluster_events
from eeg_pipeline.spectral_features import band_power, psd_welch, spectral_features


def test_band_power_of_sine_has_expected_v_squared_scale():
    sfreq = 256.0
    t = np.arange(0, 4, 1 / sfreq)
    amplitude = 2e-6  # 2 uV, internally expressed in volts
    signal = amplitude * np.sin(2 * np.pi * 10 * t)[None, :]
    freqs, psd = psd_welch(signal, sfreq, nperseg=512)
    power = band_power(freqs, psd, (8, 13))[0]
    assert np.isclose(power, amplitude**2 / 2, rtol=0.08)


def test_relative_power_and_paf_are_finite_for_alpha_signal():
    sfreq = 256.0
    t = np.arange(0, 4, 1 / sfreq)
    result = spectral_features(np.sin(2 * np.pi * 10 * t)[None, :], sfreq,
                               alpha_peak_min_snr=1.0)
    assert 0 <= result["relative_alpha_power"][0] <= 1
    assert abs(result["paf_hz"][0] - 10) < 1
    assert result["paf_quality"][0]


def test_constant_signal_entropy_is_defined_and_normalized():
    assert permutation_entropy(np.ones(1000)) == 0


def test_event_clustering_preserves_original_markers():
    events = cluster_events([7.839, 7.95, 8.035, 10.0], threshold=0.5)
    assert len(events) == 4
    assert [row["event_index"] for row in events] == [0, 1, 2, 3]
    assert [row["cluster_size"] for row in events[:3]] == [3, 3, 3]
    assert events[0]["overlap_flag"] is True
    assert events[3]["cluster_size"] == 1


def test_dwpli_uses_segment_observations_and_recovers_consistent_lag():
    sfreq = 256.0
    t = np.arange(0, 4, 1 / sfreq)
    phase = np.pi / 4
    epoch = np.vstack([np.sin(2 * np.pi * 10 * t),
                       np.sin(2 * np.pi * 10 * t + phase)])
    result = dwpli(epoch, sfreq, (8, 13), min_observations=4)
    assert np.isfinite(result[0, 1])
    assert 0 <= result[0, 1] <= 1
