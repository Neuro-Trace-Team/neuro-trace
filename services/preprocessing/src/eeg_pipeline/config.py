from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

EEG_CHANNELS = [
    "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8", "T7", "C3", "Cz",
    "C4", "T8", "P7", "P3", "Pz", "P4", "P8", "O1", "O2",
]
CHANNEL_ALIASES = {"T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8"}
BANDS = {"delta": (0.5, 4.0), "theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0), "gamma": (30.0, 45.0)}
EPOCH_WINDOWS = {
    "baseline": (-5.5, -0.5),
    "early_response": (0.0, 1.0),
    "sustained_response": (0.5, 5.5),
}

@dataclass
class PipelineConfig:
    highpass: float = 0.5
    lowpass: float = 45.0
    notch: Optional[float] = 50.0
    filter_method: str = "fir"
    notch_harmonics: bool = True
    target_sfreq: float = 256.0
    reference: str = "average"
    # Kept as a compatibility field for callers of the Python API. Only
    # event epochs are supported; the CLI does not expose a window mode.
    mode: str = "event"
    tmin: float = -0.2
    tmax: float = 0.8
    baseline: Optional[Tuple[float, float]] = (-0.2, 0.0)
    analysis_band: Tuple[float, float] = (0.5, 45.0)
    gamma_band: Tuple[float, float] = (30.0, 45.0)
    amplitude_uv: float = 500.0
    flat_std_uv: float = 1e-6
    artifact_window_seconds: float = 1.0
    enable_ica: bool = False
    ica_random_state: int = 42
    connectivity_min_observations: int = 8
    microstate_classes: int = 4
    microstate_random_state: int = 42
    microstate_max_samples: int = 20000
    alpha_peak_min_snr: float = 1.5
    alpha_min_power: float = 0.0
    graph_density: float = 0.2
    event_mode: str = "clustered"
    event_cluster_threshold: float = 0.5
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
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.mode != "event":
            raise ValueError("Only event-based segmentation is supported")
        if self.event_mode not in {"raw_events", "clustered_events", "clustered"}:
            raise ValueError("event_mode must be raw_events or clustered_events")
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

