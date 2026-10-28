from __future__ import annotations
import logging
from dataclasses import dataclass, field
import numpy as np
from .config import EEG_CHANNELS, CHANNEL_ALIASES, PipelineConfig

LOGGER = logging.getLogger(__name__)

@dataclass
class Preprocessed:
    data: np.ndarray
    sfreq: float
    channel_names: list[str]
    epochs: list[np.ndarray] = field(default_factory=list)
    epoch_times: list[tuple[float, float]] = field(default_factory=list)
    epoch_event_indices: list[int | None] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    event_records: list[dict] = field(default_factory=list)
    event_windows: list[dict] = field(default_factory=list)

def canonical_channel(name: str) -> str:
    key = name.strip().upper().replace("EEG ", "").replace("-REF", "")
    for target in EEG_CHANNELS:
        if key == target.upper(): return target
    return CHANNEL_ALIASES.get(key.title(), key.title())

def select_channels(raw, required=EEG_CHANNELS):
    names = list(raw.ch_names)
    normalized = [canonical_channel(n) for n in names]
    if len(set(normalized)) != len(normalized):
        raise ValueError("Duplicate canonical EEG channel names in recording")
    indices = []
    for wanted in required:
        matches = [i for i, n in enumerate(normalized) if n == wanted]
        if len(matches) != 1: raise ValueError(f"Required channel {wanted} missing or ambiguous")
        indices.append(matches[0])
    selected = [names[i] for i in indices]
    selected_canonical = [normalized[i] for i in indices]
    if selected_canonical != list(required):
        raise ValueError(f"Required EEG channel ordering mismatch: {selected_canonical}")
    return indices, selected

def _filter(data, sfreq, cfg):
    nyq = sfreq / 2
    low, high = max(0.0, cfg.highpass), min(cfg.lowpass, nyq * .99)
    try:
        import mne
        if high <= low: raise ValueError("Invalid filter limits")
        if cfg.filter_method != "fir":
            raise ValueError("Only zero-phase FIR filtering is supported for EEG")
        data = mne.filter.filter_data(data, sfreq, l_freq=low or None, h_freq=high,
                                      method="fir", phase="zero-double", verbose="ERROR")
        # A 50 Hz notch is redundant when the low-pass is below 50 Hz.  When
        # needed, include harmonics that are still inside the retained band.
        if cfg.notch and 0 < cfg.notch < nyq and high > cfg.notch:
            freqs = np.arange(cfg.notch, high + 1e-9, cfg.notch) if cfg.notch_harmonics else [cfg.notch]
            data = mne.filter.notch_filter(data, sfreq, freqs=freqs, method="fir",
                                           phase="zero-double", verbose="ERROR")
        return data
    except ImportError as exc:
        raise ImportError("Filtering requires mne") from exc


def cluster_events(events_seconds, threshold=0.5, mode="clustered_events"):
    """Return traceable event records without discarding original markers."""
    indexed = sorted(enumerate(float(value) for value in events_seconds), key=lambda item: item[1])
    events = [value for _, value in indexed]
    source_indices = [index for index, _ in indexed]
    if mode == "raw_events":
        return [{"event_index": source_indices[i], "event": value, "cluster_id": i,
                 "cluster_event": value, "cluster_size": 1,
                 "overlap_flag": False} for i, value in enumerate(events)]
    records = []
    cluster_id = -1
    cluster = []
    for position, value in enumerate(events):
        index = source_indices[position]
        if not cluster or value - cluster[-1]["event"] <= threshold:
            cluster.append({"event_index": index, "event": value})
        else:
            cluster_id += 1
            records.extend(_finish_cluster(cluster, cluster_id))
            cluster = [{"event_index": index, "event": value}]
    if cluster:
        cluster_id += 1
        records.extend(_finish_cluster(cluster, cluster_id))
    return records


def _finish_cluster(cluster, cluster_id):
    representative = float(np.mean([item["event"] for item in cluster]))
    size = len(cluster)
    return [{**item, "cluster_id": cluster_id, "cluster_event": representative,
             "cluster_size": size, "overlap_flag": size > 1} for item in cluster]

def _optional_ica(data, sfreq, names, cfg, warnings):
    """Apply only explicitly requested ICA exclusions; never guess ocular components."""
    if not cfg.enable_ica:
        return data
    exclude = cfg.extra.get("ica_exclude", [])
    if not exclude:
        warnings.append("ICA requested but no explicit ica_exclude components supplied; ICA not applied")
        return data
    try:
        import mne
        from mne.preprocessing import ICA
        info = mne.create_info(names, sfreq, ch_types="eeg")
        temp = mne.io.RawArray(data, info, verbose="ERROR")
        ica = ICA(n_components=0.99, method="fastica", random_state=cfg.ica_random_state, max_iter="auto", verbose="ERROR")
        ica.fit(temp, verbose="ERROR")
        ica.exclude = [int(i) for i in exclude]
        return ica.apply(temp.copy(), verbose="ERROR").get_data()
    except Exception as exc:
        warnings.append(f"ICA failed and was skipped: {exc}")
        return data

def preprocess_raw(raw, config: PipelineConfig | None = None, events_seconds=None) -> Preprocessed:
    cfg = config or PipelineConfig()
    try:
        sfreq = float(raw.info["sfreq"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Missing valid sampling frequency required for preprocessing") from exc
    if not np.isfinite(sfreq) or sfreq <= 0:
        raise ValueError("Missing valid sampling frequency required for preprocessing")
    if not getattr(raw, "ch_names", None):
        raise ValueError("Missing channel names required for preprocessing")
    try:
        channel_types = raw.get_channel_types()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Missing channel types required for preprocessing") from exc
    if len(channel_types) != len(raw.ch_names) or any(not kind for kind in channel_types):
        raise ValueError("Incomplete channel types required for preprocessing")
    try:
        raw.set_montage("standard_1020", match_case=False, on_missing="ignore", verbose="ERROR")
    except Exception as exc:
        LOGGER.warning("Could not apply standard_1020 montage: %s", exc)
    indices, selected_names = select_channels(raw)
    selected_types = [channel_types[i].lower() for i in indices]
    non_eeg = [name for name, kind in zip(selected_names, selected_types) if kind != "eeg"]
    if non_eeg:
        raise ValueError("Required channels are not marked as EEG: " + ", ".join(non_eeg))
    data = raw.get_data(picks=indices)
    bad = []
    finite = np.isfinite(data).all(axis=1)
    std = np.nanstd(data, axis=1)
    amp = np.nanmax(np.abs(data), axis=1)
    for n, ok, s, a in zip(selected_names, finite, std, amp):
        if not ok: bad.append(f"non_finite:{n}")
        elif s <= cfg.flat_std_uv * 1e-6: bad.append(f"flat_channel:{n}")
    if bad: raise ValueError("Invalid required EEG channels: " + ", ".join(bad))
    data = _filter(data, sfreq, cfg)
    if cfg.reference == "average": data = data - data.mean(axis=0, keepdims=True)
    elif cfg.reference not in {"none", "unknown", None}: LOGGER.warning("Reference %s not applied", cfg.reference)
    post_filter_amplitude = np.nanmax(np.abs(data), axis=1)
    excessive = [f"amplitude:{name}" for name, value in zip(selected_names, post_filter_amplitude) if value > cfg.amplitude_uv * 1e-6]
    warnings = []
    if excessive:
        warnings.append("High amplitude detected; affected fragments will be rejected: " + ", ".join(excessive))
    data = _optional_ica(data, sfreq, selected_names, cfg, warnings)
    if cfg.target_sfreq and abs(cfg.target_sfreq - sfreq) > 1e-9:
        try:
            from scipy.signal import resample_poly
            from fractions import Fraction
            ratio = Fraction(cfg.target_sfreq / sfreq).limit_denominator(1000)
            data = resample_poly(data, ratio.numerator, ratio.denominator, axis=-1)
            sfreq = cfg.target_sfreq
        except ImportError as exc: raise ImportError("Resampling requires scipy") from exc
    if not np.isfinite(data).all():
        raise ValueError("Preprocessing produced non-finite EEG samples")
    epochs, times, epoch_event_indices, rejected, event_windows = [], [], [], [], []
    raw_events = [float(event) for event in (events_seconds or [])]
    if cfg.event_time_unit == "milliseconds":
        raw_events = [event / 1000.0 for event in raw_events]
    elif cfg.event_time_unit == "samples":
        raw_events = [event / sfreq for event in raw_events]
    event_records = cluster_events(raw_events, cfg.event_cluster_threshold, cfg.event_mode)
    for record in event_records:
        record["source_event"] = (events_seconds or [])[record["event_index"]]
        record["event_time_unit"] = cfg.event_time_unit
    # Clustered events are represented once for analysis, but raw markers are
    # retained in event_records and in the report for traceability.
    analysis_records = event_records
    if cfg.event_mode in {"clustered", "clustered_events"}:
        analysis_records = [record for record in event_records
                            if record["event_index"] == min(r["event_index"] for r in event_records
                                                            if r["cluster_id"] == record["cluster_id"])]
    for record in analysis_records:
        event_index, event = record["event_index"], record["cluster_event"]
        # Preserve the public legacy ``epochs`` interface.  New response
        # windows are stored independently below and never replace this
        # configurable tmin/tmax extraction.
        legacy_start = round((float(event) + cfg.tmin) * sfreq)
        legacy_stop = round((float(event) + cfg.tmax) * sfreq)
        if legacy_start >= 0 and legacy_stop <= data.shape[1] and legacy_stop > legacy_start:
            legacy_block = data[:, legacy_start:legacy_stop]
            if np.isfinite(legacy_block).all() and np.max(np.abs(legacy_block)) <= cfg.amplitude_uv * 1e-6:
                epochs.append(legacy_block)
                times.append((event + cfg.tmin, event + cfg.tmax))
                epoch_event_indices.append(event_index)
        windows = {}
        for name, (relative_start, relative_end) in {"baseline": cfg.baseline_window, **cfg.response_windows}.items():
            start = round((float(event) + relative_start) * sfreq)
            stop = round((float(event) + relative_end) * sfreq)
            valid = start >= 0 and stop <= data.shape[1] and stop > start
            block = data[:, start:stop] if valid else None
            reason = None
            if not valid:
                reason = "out_of_bounds"
            elif not np.isfinite(block).all() or np.max(np.abs(block)) > cfg.amplitude_uv * 1e-6:
                reason = "artifact_amplitude"; block = None
            overlaps = [other["cluster_event"] for other in analysis_records
                        if other["cluster_id"] != record["cluster_id"]
                        and float(event) < other["cluster_event"] < float(event) + relative_end]
            windows[name] = {"data": block, "start": start, "stop": stop,
                             "relative_start": relative_start, "relative_end": relative_end,
                             "valid": block is not None, "reason": reason,
                             "overlaps_next_event": bool(overlaps), "overlap_events": overlaps}
        record_copy = dict(record)
        record_copy["window_flags"] = {name: {key: value for key, value in item.items() if key != "data"}
                                        for name, item in windows.items()}
        event_windows.append({"record": record_copy, "windows": windows})
        early = windows.get("early_response")
        if not early or not early["valid"]:
            rejected.append({"event_index": event_index, "event": event,
                             "reason": early["reason"] if early else "missing_early_response"})
    return Preprocessed(data, sfreq, EEG_CHANNELS.copy(), epochs, times, epoch_event_indices,
                        rejected, warnings, event_records, event_windows)

