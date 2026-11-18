from __future__ import annotations

from dataclasses import dataclass, field, InitVar
from typing import Optional, Tuple
import math

EEG_CHANNELS = [
    "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8", "T7", "C3", "Cz",
    "C4", "T8", "P7", "P3", "Pz", "P4", "P8", "O1", "O2",
]
CHANNEL_ALIASES = {"T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8"}
BANDS = {"delta": (0.5, 4.0), "theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0), "gamma": (30.0, 45.0)}
EPOCH_WINDOWS = {
    "baseline": (-5.5, -0.5),
    "early_response": (0.0, 1.0),
    "sustained_response": (1.0, 3.0),
}

_UNSET = object()

@dataclass
class PipelineConfig:
    highpass: float = 0.5
    lowpass: float = 100.0
    notch: Optional[float] = 50.0
    filter_method: str = "fir"
    filter_phase: str = "zero"
    notch_harmonics: bool = True
    target_sfreq: float = 256.0
    reference: str = "average"
    # Kept as a compatibility field for callers of the Python API. Only
    # event epochs are supported; the CLI does not expose a window mode.
    mode: str = "event"
    tmin: float = -0.2
    tmax: float = 0.8
    baseline: Optional[Tuple[float, float]] = (-0.2, 0.0)
    analysis_band: Tuple[float, float] = (0.5, 100.0)
    high_gamma_band: Optional[Tuple[float, float]] = (60.0, 90.0)
    gamma_band: Tuple[float, float] = (30.0, 45.0)
    # Keyword-only to prevent interpreting an old positional amplitude as PTP.
    epoch_peak_to_peak_uv: float = field(default=200.0, kw_only=True)
    # Gross source corruption has a separate screen from residual epoch QC.
    # Ordinary blinks are assessed after ICA, not permanently masked before it.
    source_artifact_peak_to_peak_uv: float = 2000.0
    amplitude_uv: InitVar[object] = _UNSET
    flat_std_uv: float = 1e-6
    # Bad-channel detection thresholds are starting points for empirical
    # calibration, not clinical limits. Signal amplitudes are converted V -> µV.
    bad_channel_auto_detect: bool = True
    bad_channel_manual: tuple[str, ...] = ()
    bad_channel_window_seconds: float = 2.0
    bad_channel_flat_std_uv: float = 0.01
    bad_channel_noise_std_uv: float = 100.0
    bad_channel_noise_mad_z: float = 8.0
    bad_channel_noise_window_fraction: float = 0.5
    bad_channel_max_interpolated: int = 4
    artifact_window_seconds: float = 1.0
    enable_ica: bool = True
    ica_random_state: int = 42
    ica_highpass: float = 1.0
    ica_lowpass: float = 100.0
    ica_allow_band_deviation: bool = False
    ica_method: str = "infomax"
    ica_max_iter: int = 1000
    ica_rank_rtol: float = 1e-6
    ica_min_rank: int = 2
    ica_max_condition: float = 1e6
    ica_fit_window_seconds: float = 2.0
    ica_fit_peak_to_peak_uv: float = 2000.0
    ica_min_fit_seconds: float = 30.0
    ica_min_samples_per_component_squared: float = 20.0
    ica_artifact_thresholds: dict = field(default_factory=lambda: {
        "eye blink": 0.9, "muscle artifact": 0.9})
    ica_exclude: tuple[int, ...] = ()
    ica_keep: tuple[int, ...] = ()
    ica_max_excluded_fraction: float = 0.5
    ica_failure_policy: str = "raise"
    ica_export_diagnostics: bool = False
    ica_export_seconds: float = 10.0
    connectivity_min_observations: int = 8
    microstate_classes: int = 4
    microstate_random_state: int = 42
    microstate_max_samples: int = 20000
    alpha_peak_min_snr: float = 1.5
    alpha_min_power: float = 0.0
    graph_density: float = 0.2
    event_mode: str = "clustered"
    event_cluster_threshold: float = 0.5
    isi_warning_threshold_seconds: float = 11.0
    baseline_protected_response_seconds: float = 5.5
    baseline_overlap_policy: str = "trim"
    baseline_min_seconds: float = 2.0
    event_time_unit: str = "seconds"
    baseline_window: Tuple[float, float] = EPOCH_WINDOWS["baseline"]
    response_windows: dict = field(default_factory=lambda: {
        key: value for key, value in EPOCH_WINDOWS.items() if key != "baseline"
    })
    psd_nperseg: Optional[int] = None
    psd_overlap: float = 0.5
    entropy_order: int = 3
    entropy_delay: int = 1
    entropy_normalize: bool = True
    connectivity_segment_seconds: float = 0.5
    connectivity_include_gamma: bool = True
    # scipy's prominence is in PSD units; zero means peak detection is used
    # and the scale-free prominence/SNR threshold remains alpha_peak_min_snr.
    paf_prominence: float = 0.0
    paf_min_cycles: float = 2.0
    seed: int = 42
    tfr: dict = field(default_factory=dict)
    lep: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    @property
    def spectral_bands(self):
        bands = {**BANDS, "gamma": self.gamma_band}
        if self.high_gamma_band is not None:
            bands["high_gamma"] = self.high_gamma_band
        return bands

    @property
    def connectivity_bands(self):
        return {name: band for name, band in self.spectral_bands.items()
                if name in ("delta", "theta", "alpha", "beta") or
                (name == "gamma" and self.connectivity_include_gamma)}

    def __post_init__(self, amplitude_uv):
        if self.reference not in ('average', 'none', None):
            raise ValueError('Supported reference values: average, none, None')
        if self.psd_nperseg is not None and (type(self.psd_nperseg) is not int or self.psd_nperseg < 8):
            raise ValueError('psd_nperseg must be an integer >= 8')
        if not math.isfinite(self.psd_overlap) or not 0 <= self.psd_overlap < 1:
            raise ValueError('psd_overlap must be in [0, 1)')
        from .lep import LEPConfig
        LEPConfig(**self.lep)
        from .tfr import TFRConfig
        TFRConfig(**self.tfr)
        if amplitude_uv is not _UNSET:
            raise ValueError("amplitude_uv (max(abs(x))) was removed; use epoch_peak_to_peak_uv "
                             "(per-channel max(x)-min(x)); no universal conversion exists")
        if self.filter_method != "fir":
            raise ValueError("Only zero-phase FIR filtering is supported")
        if self.filter_phase not in {'zero', 'zero-double'}:
            raise ValueError('filter_phase must be zero or zero-double')
        if not all(math.isfinite(v) for v in (self.highpass, self.lowpass)) or not 0 < self.highpass < self.lowpass:
            raise ValueError("Invalid analytical filter band")
        if self.target_sfreq is not None and (not math.isfinite(self.target_sfreq) or self.target_sfreq <= 0):
            raise ValueError("target_sfreq must be positive and finite or None")
        if self.notch is not None and (not math.isfinite(self.notch) or self.notch <= 0):
            raise ValueError("notch must be positive and finite or None")
        for name, band in {"analysis": self.analysis_band, **self.spectral_bands}.items():
            if len(band) != 2 or not all(math.isfinite(v) for v in band) or not 0 <= band[0] < band[1]:
                raise ValueError(f"Invalid {name} band")
        from .window_quality import validate_threshold
        validate_threshold(self.epoch_peak_to_peak_uv)
        validate_threshold(self.source_artifact_peak_to_peak_uv)
        for key in ("enable_ica", "ica_allow_band_deviation", "ica_export_diagnostics"):
            if not isinstance(getattr(self, key), bool):
                raise ValueError(f"{key} must be boolean")
        if type(self.ica_random_state) is not int or not 0 <= self.ica_random_state < 2**32:
            raise ValueError("ica_random_state must be an integer in [0, 2**32)")
        if self.ica_method != "infomax":
            raise ValueError("ICA supports extended infomax only")
        if self.ica_failure_policy not in {"raise", "skip"}:
            raise ValueError("ica_failure_policy must be raise or skip")
        if (not all(math.isfinite(v) for v in (self.ica_highpass, self.ica_lowpass))
                or not 0 < self.ica_highpass < self.ica_lowpass):
            raise ValueError("Invalid ICA band")
        if not self.ica_allow_band_deviation and (self.ica_highpass, self.ica_lowpass) != (1., 100.):
            raise ValueError("Nonstandard ICLabel band requires ica_allow_band_deviation")
        for key in ("ica_rank_rtol", "ica_max_condition", "ica_fit_window_seconds",
                    "ica_fit_peak_to_peak_uv", "ica_min_fit_seconds",
                    "ica_min_samples_per_component_squared", "ica_export_seconds"):
            if not math.isfinite(getattr(self, key)) or getattr(self, key) <= 0:
                raise ValueError(f"{key} must be positive and finite")
        if self.ica_export_seconds > 60:
            raise ValueError("ica_export_seconds must not exceed 60 seconds")
        if not 0 < self.ica_rank_rtol < 1 or self.ica_max_condition <= 1:
            raise ValueError("Invalid ICA rank tolerances")
        if not isinstance(self.ica_max_iter, int) or self.ica_max_iter < 1:
            raise ValueError("ica_max_iter must be a positive integer")
        if not isinstance(self.ica_min_rank, int) or not 2 <= self.ica_min_rank <= 18:
            raise ValueError("ica_min_rank must be between 2 and 18")
        if not 0 < self.ica_max_excluded_fraction < 1:
            raise ValueError("ica_max_excluded_fraction must be in (0, 1)")
        classes = {"muscle artifact", "eye blink", "heart beat", "line noise", "channel noise"}
        for label, threshold in self.ica_artifact_thresholds.items():
            if label not in classes or not math.isfinite(threshold) or not 0 < threshold <= 1:
                raise ValueError("Invalid ICA artifact class or confidence threshold")
        legacy = self.extra.get("ica_exclude", ())
        if legacy and self.ica_exclude:
            raise ValueError("Use either ica_exclude or extra['ica_exclude'], not both")
        for indices in (self.ica_exclude, self.ica_keep, legacy):
            if any(type(i) is not int or i < 0 for i in indices):
                raise ValueError("ICA indices must be non-negative integers")
        if set(self.ica_exclude or legacy) & set(self.ica_keep):
            raise ValueError("Conflicting ICA keep and exclude indices")
        if not isinstance(self.bad_channel_auto_detect, bool):
            raise ValueError("bad_channel_auto_detect must be boolean")
        if not math.isfinite(self.bad_channel_window_seconds) or self.bad_channel_window_seconds <= 0:
            raise ValueError("bad_channel_window_seconds must be positive")
        if (not math.isfinite(self.bad_channel_flat_std_uv) or self.bad_channel_flat_std_uv < 0
                or not math.isfinite(self.bad_channel_noise_std_uv) or self.bad_channel_noise_std_uv <= 0):
            raise ValueError("Bad-channel amplitude thresholds must be positive")
        if not math.isfinite(self.bad_channel_noise_mad_z) or self.bad_channel_noise_mad_z <= 0:
            raise ValueError("bad_channel_noise_mad_z must be positive")
        if (not math.isfinite(self.bad_channel_noise_window_fraction)
                or not 0 < self.bad_channel_noise_window_fraction <= 1):
            raise ValueError("bad_channel_noise_window_fraction must be in (0, 1]")
        if not isinstance(self.bad_channel_max_interpolated, int) or self.bad_channel_max_interpolated < 0:
            raise ValueError("bad_channel_max_interpolated must be a non-negative integer")
        if isinstance(self.bad_channel_manual, str):
            raise ValueError("bad_channel_manual must be a sequence of channel names")
        if any(not isinstance(name, str) or not name.strip() for name in self.bad_channel_manual):
            raise ValueError("bad_channel_manual entries must be non-empty channel names")
        if self.mode != "event":
            raise ValueError("Only event-based segmentation is supported")
        if self.event_mode not in {"raw_events", "clustered_events", "clustered"}:
            raise ValueError("event_mode must be raw_events or clustered_events")
        for key in ("isi_warning_threshold_seconds", "baseline_protected_response_seconds", "baseline_min_seconds"):
            value = getattr(self, key)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be positive and finite")
        if self.baseline_overlap_policy not in {"reject", "trim"}:
            raise ValueError("baseline_overlap_policy must be reject or trim")
        if self.event_cluster_threshold < 0:
            raise ValueError("event_cluster_threshold must be non-negative")
        if self.event_time_unit not in {"seconds", "milliseconds", "samples"}:
            raise ValueError("event_time_unit must be seconds, milliseconds or samples")
        if not 0 < self.psd_overlap < 1:
            raise ValueError("psd_overlap must be between 0 and 1")
        for name, band in {"analysis": self.analysis_band, "gamma": self.gamma_band, **BANDS}.items():
            if len(band) != 2 or not 0 <= band[0] < band[1]:
                raise ValueError(f"Invalid {name} frequency band")
        for name, window in {"baseline": self.baseline_window, **self.response_windows}.items():
            if len(window) != 2 or window[0] >= window[1]:
                raise ValueError(f"Invalid {name} epoch window")

