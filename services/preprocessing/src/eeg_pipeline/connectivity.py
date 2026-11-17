from __future__ import annotations
import numpy as np
from .config import BANDS

def _analytic(x, sfreq, band):
    from scipy.signal import butter, sosfiltfilt, hilbert
    nyq=sfreq/2; lo, hi=band
    if hi >= nyq: hi=nyq*.99
    sos=butter(4, [lo/nyq, hi/nyq], btype="band", output="sos")
    return hilbert(sosfiltfilt(sos, x, axis=-1), axis=-1)

def dwpli_with_metadata(epoch, sfreq, band, min_observations=8, segment_seconds=0.5):
    """Estimate debiased wPLI from independent non-overlapping segments.

    Time samples within one segment are not treated as independent
    observations.  The returned matrix can contain negative finite-sample
    debiased estimates; these are reported rather than silently clipped.
    """
    segment_samples = max(8, int(round(segment_seconds * sfreq)))
    n_segments = epoch.shape[-1] // segment_samples
    valid_observations = n_segments
    if n_segments < min_observations:
        return np.full((epoch.shape[0], epoch.shape[0]), np.nan), valid_observations, False
    try: analytic = _analytic(epoch[..., :n_segments * segment_samples], sfreq, band)
    except ImportError: return np.full((epoch.shape[0], epoch.shape[0]), np.nan), valid_observations, False
    analytic = analytic.reshape(epoch.shape[0], n_segments, segment_samples)
    out=np.full((epoch.shape[0], epoch.shape[0]), np.nan)
    np.fill_diagonal(out, 1.0)
    for i in range(epoch.shape[0]):
        for j in range(i):
            cross = analytic[i] * np.conj(analytic[j])
            imag = np.imag(np.mean(cross, axis=-1))
            s=np.sum(imag); ss=np.sum(imag * imag); sa=np.sum(np.abs(imag))
            # Vinck et al. debiased wPLI estimator.
            num=s*s-ss; den=sa*sa-ss
            value=num/den if den > 0 else np.nan
            out[i,j]=out[j,i]=value
    return out, valid_observations, True

def dwpli(epoch, sfreq, band, min_observations=8, segment_seconds=0.5):
    """Compatibility wrapper returning only the pairwise dwPLI matrix."""
    return dwpli_with_metadata(epoch, sfreq, band, min_observations, segment_seconds)[0]

def connectivity_by_band(epoch, sfreq, min_observations=8, segment_seconds=0.5, include_gamma=False):
    bands = BANDS if include_gamma else {name: band for name, band in BANDS.items() if name != "gamma"}
    return {name: dwpli(epoch, sfreq, band, min_observations, segment_seconds)
            for name, band in bands.items()}

def connectivity_pair_rows(epoch, sfreq, event_id, event_timestamp, window_type,
                           min_observations=8, segment_seconds=0.5, include_gamma=True):
    rows = []
    channel_names = ["Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8", "T7", "C3", "Cz",
                     "C4", "T8", "P7", "P3", "Pz", "P4", "P8", "O1", "O2"]
    bands = BANDS if include_gamma else {name: band for name, band in BANDS.items() if name != "gamma"}
    for band_name, band in bands.items():
        matrix, n_obs, valid = dwpli_with_metadata(epoch, sfreq, band, min_observations, segment_seconds)
        for i in range(len(channel_names)):
            for j in range(i + 1, len(channel_names)):
                rows.append({"event_id": event_id, "event_timestamp": event_timestamp,
                             "window_type": window_type, "frequency_band": band_name,
                             "channel_1": channel_names[i], "channel_2": channel_names[j],
                             "dwpli": matrix[i, j], "n_valid_observations": n_obs,
                             "dwpli_valid": bool(valid and np.isfinite(matrix[i, j]))})
    return rows

