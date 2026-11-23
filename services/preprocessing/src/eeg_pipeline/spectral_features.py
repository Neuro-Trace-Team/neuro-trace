from __future__ import annotations
import numpy as np
from scipy.signal import find_peaks, peak_prominences
from .config import BANDS

def psd_welch(epoch: np.ndarray, sfreq: float, nperseg=None, overlap=0.5):
    if not np.isfinite(sfreq) or sfreq <= 0:
        raise ValueError('sfreq must be positive and finite')
    if nperseg is not None and (type(nperseg) is not int or nperseg < 8):
        raise ValueError('nperseg must be an integer >= 8')
    if not np.isfinite(overlap) or not 0 <= overlap < 1:
        raise ValueError('overlap must be in [0, 1)')
    try:
        from scipy.signal import welch
        nperseg = min(epoch.shape[-1], int(sfreq * 2), nperseg or max(8, int(sfreq * 2)))
        if nperseg < 8:
            return np.array([]), np.full((*epoch.shape[:-1], 0), np.nan)
        noverlap = min(int(nperseg * overlap), nperseg - 1)
        return welch(epoch, fs=sfreq, axis=-1, nperseg=nperseg,
                     noverlap=noverlap, detrend="constant", scaling="density")
    except ImportError:
        freqs = np.fft.rfftfreq(epoch.shape[-1], 1/sfreq)
        x = epoch - epoch.mean(axis=-1, keepdims=True)
        return freqs, np.abs(np.fft.rfft(x, axis=-1))**2 / (sfreq * epoch.shape[-1])

def band_power(freqs, psd, band):
    lo, hi = band
    if len(freqs) < 2 or lo < freqs[0] or hi > freqs[-1]:
        return np.full(psd.shape[:-1], np.nan)
    inside = (freqs > lo) & (freqs < hi)
    points = np.concatenate(([lo], freqs[inside], [hi]))
    values = np.stack([np.interp(points, freqs, row) for row in np.asarray(psd).reshape(-1, len(freqs))])
    integrate = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    return integrate(values, points, axis=-1).reshape(psd.shape[:-1])

def spectral_features(epoch, sfreq, analysis_band=(0.5,100), gamma_band=(30,45), alpha_peak_min_snr=1.5, alpha_min_power=0.0, nperseg=None, overlap=0.5, alpha_prominence=None, high_gamma_band=(60,90), bands=None):
    f, p = psd_welch(epoch, sfreq, nperseg, overlap); total = band_power(f, p, analysis_band)
    out = {}
    duration = epoch.shape[-1] / sfreq
    if bands is None:
        bands = {**BANDS, "gamma": gamma_band}
        if high_gamma_band is not None:
            bands["high_gamma"] = high_gamma_band
    for name, band in bands.items():
        power = band_power(f, p, band)
        # One second cannot support a defensible delta estimate with the
        # default two-second Welch segment.  Keep the column, but mark it
        # undefined rather than presenting a precise-looking number.
        if name == "delta" and duration < 2.0:
            power = np.full(epoch.shape[0], np.nan)
        out[f"absolute_{name}_power"] = power
        out[f"{name}_power_valid"] = np.isfinite(power)
    out["gamma_power"] = out["absolute_gamma_power"]
    out["absolute_spectral_power"] = total
    safe = np.where(total > 0, total, np.nan)
    for name in ("delta", "theta", "alpha", "beta"):
        out[f"relative_{name}_power"] = out[f"absolute_{name}_power"] / safe
    alpha_mask = (f >= 8) & (f <= 13) if len(f) else np.array([], dtype=bool)
    paf = np.full(epoch.shape[0], np.nan)
    paf_prominence = np.full(epoch.shape[0], np.nan)
    paf_quality = np.zeros(epoch.shape[0], dtype=bool)
    if alpha_mask.sum() >= 3:
        # Include one neighboring bin on either side, preserving the old interior prominence.
        ids = np.flatnonzero(alpha_mask)
        context = np.arange(max(0, ids[0]-1), min(len(f), ids[-1]+2))
        ap = p[:, context]; af = f[context]
        for channel in range(ap.shape[0]):
            peak_indices, props = find_peaks(ap[channel], prominence=0.0)
            inside = (af[peak_indices] >= 8) & (af[peak_indices] <= 13)
            peak_indices = peak_indices[inside]
            props['prominences'] = props['prominences'][inside]
            # Keep the historical prominence estimator for interior alpha peaks;
            # only endpoint peaks need their newly available outer neighbors.
            local = np.searchsorted(ids, context[peak_indices])
            interior = (local > 0) & (local < len(ids)-1)
            if interior.any():
                props['prominences'][interior] = peak_prominences(p[channel, alpha_mask], local[interior])[0]
            keep = props['prominences'] >= (alpha_prominence or 0.0)
            peak_indices = peak_indices[keep]
            props['prominences'] = props['prominences'][keep]
            if not len(peak_indices):
                continue
            best = peak_indices[np.argmax(ap[channel, peak_indices])]
            prominence = float(props["prominences"][np.argmax(ap[channel, peak_indices])])
            background = max(float(np.median(p[channel, alpha_mask])), np.finfo(float).tiny)
            ratio = prominence / background
            paf_prominence[channel] = ratio
            # A peak must be separated by the available frequency resolution
            # and have meaningful alpha power.  The value is reported at the
            # Welch bin, never as fabricated sub-bin precision.
            resolution = float(np.median(np.diff(f))) if len(f) > 1 else np.inf
            valid = (out["absolute_alpha_power"][channel] > alpha_min_power and
                     ratio >= alpha_peak_min_snr and np.isfinite(resolution))
            if valid:
                paf[channel] = round(float(af[best]), 2)
                paf_quality[channel] = True
    out["paf_hz"] = paf
    out["paf_prominence"] = paf_prominence
    out["paf_quality"] = paf_quality
    out["theta_alpha_ratio"] = np.divide(out["absolute_theta_power"], out["absolute_alpha_power"], out=np.full_like(total, np.nan), where=out["absolute_alpha_power"] > np.finfo(float).eps)
    return out

