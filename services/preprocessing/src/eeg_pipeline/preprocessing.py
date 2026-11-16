from __future__ import annotations
import logging
from dataclasses import dataclass, field
import numpy as np
from .config import EEG_CHANNELS, CHANNEL_ALIASES, PipelineConfig

from .event_timing import sample_boundary, isi_statistics, baseline_interval
from .window_quality import evaluate_window_quality, unavailable_quality

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
    channel_diagnostics: dict = field(default_factory=dict)
    ica_diagnostics: dict = field(default_factory=dict)
    legacy_window_diagnostics: list[dict] = field(default_factory=list)
    isi_diagnostics: dict = field(default_factory=dict)


class PreprocessingError(ValueError):
    """A preprocessing failure carrying diagnostics suitable for the report."""
    def __init__(self, message, diagnostics=None, ica_diagnostics=None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}
        self.ica_diagnostics = ica_diagnostics or {}

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


def detect_bad_channels(data, sfreq, names, metadata_bads=(), manual_bads=(), cfg=None):
    """Deterministic window based detector. ``data`` is in MNE volts."""
    cfg = cfg or PipelineConfig()
    diagnostics = {name: {"reasons": [], "metrics": {}} for name in names}
    metadata = {canonical_channel(n) for n in metadata_bads}
    manual = {canonical_channel(n) for n in manual_bads}
    bad = set()
    for i, name in enumerate(names):
        item = diagnostics[name]
        if name in metadata:
            item["reasons"].append("raw_info_bads")
            bad.add(name)
        if name in manual:
            item["reasons"].append("manual_configuration")
            bad.add(name)
        x = np.asarray(data[i], dtype=float)
        if not np.isfinite(x).all():
            item["reasons"].append("non_finite_samples")
            item["metrics"].update({"finite_fraction": float(np.isfinite(x).mean())})
            bad.add(name)
            continue
        size = max(1, int(round(cfg.bad_channel_window_seconds * sfreq)))
        # Include a final partial window; a short recording is assessed once,
        # but cannot trigger noise classification without peers.
        windows = [x[start:min(start + size, x.size)] for start in range(0, x.size, size)]
        std_uv = np.asarray([np.std(w) * 1e6 for w in windows if w.size])
        p2p_uv = np.asarray([(np.ptp(w) * 1e6) for w in windows if w.size])
        item["metrics"].update({"window_count": int(std_uv.size),
                                "window_std_uv": std_uv.tolist(),
                                "window_peak_to_peak_uv": p2p_uv.tolist(),
                                "median_std_uv": float(np.median(std_uv)) if std_uv.size else None,
                                "median_peak_to_peak_uv": float(np.median(p2p_uv)) if p2p_uv.size else None})
        if cfg.bad_channel_auto_detect and std_uv.size and np.mean(std_uv <= cfg.bad_channel_flat_std_uv) >= cfg.bad_channel_noise_window_fraction:
            item["reasons"].append("persistent_flatness")
            bad.add(name)
    if cfg.bad_channel_auto_detect:
        # Compare each window with the median of peer channel standard
        # deviations. MAD=0 uses only the explicit absolute µV threshold.
        count = max((len(d["metrics"].get("window_std_uv", [])) for d in diagnostics.values()), default=0)
        for wi in range(count):
            peers = [d["metrics"]["window_std_uv"][wi] for n, d in diagnostics.items()
                     if n not in bad and wi < len(d["metrics"].get("window_std_uv", []))]
            if not peers:
                continue
            med = float(np.median(peers)); mad = float(np.median(np.abs(np.asarray(peers) - med)))
            threshold = max(cfg.bad_channel_noise_std_uv,
                            med + cfg.bad_channel_noise_mad_z * 1.4826 * mad) if mad > 0 else cfg.bad_channel_noise_std_uv
            for name, item in diagnostics.items():
                values = item["metrics"].get("window_std_uv", [])
                if name not in bad and wi < len(values) and values[wi] > threshold:
                    item["metrics"].setdefault("noisy_window_indices", []).append(wi)
        for name, item in diagnostics.items():
            windows = item["metrics"].get("window_std_uv", [])
            noisy = len(item["metrics"].get("noisy_window_indices", []))
            fraction = noisy / len(windows) if windows else 0.0
            item["metrics"]["noisy_window_fraction"] = fraction
            if windows and fraction >= cfg.bad_channel_noise_window_fraction:
                item["reasons"].append("persistent_excessive_noise")
                bad.add(name)
    return [n for n in names if n in bad], diagnostics

def transition_width(lowpass):
    # Explicit MNE-style transition, never shortened to fit Nyquist.
    return max(2.0, lowpass * 0.25)


def notch_frequencies(cfg, sfreq):
    if cfg.notch is None:
        return []
    candidates = (np.arange(cfg.notch, cfg.lowpass, cfg.notch)
                  if cfg.notch_harmonics else [cfg.notch])
    # notch_widths=1 Hz, trans_bandwidth=2 Hz: reserve 1.5 Hz each side.
    return [float(f) for f in candidates
            if f - 1.5 > cfg.highpass and f + 1.5 < min(cfg.lowpass, sfreq / 2)]


def validate_sampling(sfreq, cfg):
    bands = {"analysis": (cfg.highpass, cfg.lowpass)}
    if cfg.enable_ica:
        bands["ICA"] = (cfg.ica_highpass, cfg.ica_lowpass)
    for branch, (lo, hi) in bands.items():
        stop = hi + transition_width(hi)
        rates = {"source": sfreq}
        if branch == "analysis" and cfg.target_sfreq is not None:
            rates["target"] = cfg.target_sfreq
        for kind, rate in rates.items():
            if not np.isfinite(rate) or rate / 2 <= stop:
                raise PreprocessingError(
                    f"{branch}: {kind} sfreq={rate} Hz, Nyquist={rate/2} Hz; "
                    f"lowpass={hi} Hz + transition={transition_width(hi)} Hz requires sfreq > {2*stop} Hz. "
                    "Upsampling cannot restore source bandwidth; explicitly narrow bands and disable high_gamma "
                    "(and disable ICA or explicitly configure its band).")
    if not cfg.highpass <= cfg.analysis_band[0] < cfg.analysis_band[1] <= cfg.lowpass:
        raise PreprocessingError("analysis_band must lie within the analytical filter passband")
    for name, band in cfg.spectral_bands.items():
        if not cfg.analysis_band[0] <= band[0] < band[1] <= cfg.analysis_band[1]:
            raise PreprocessingError(f"{name}={band} outside analysis_band={cfg.analysis_band}; explicitly disable high_gamma for narrow recordings")


def annotation_intervals(raw):
    """BAD is contaminated continuous data; EDGE is a discontinuity (also at duration=0)."""
    return [(float(a['onset'] - raw.first_time),
             float(a['onset'] - raw.first_time + a['duration']),
             'edge' if a['description'].lower().startswith('edge') else 'bad')
            for a in raw.annotations if a['description'].lower().startswith(('bad', 'edge'))]


def artifact_intervals(data, sfreq, threshold_uv, window_seconds=1.):
    """Conservative source PTP screen; preserve source data and mark support only."""
    from scipy.ndimage import maximum_filter1d, minimum_filter1d
    size = max(1, round(window_seconds*sfreq))
    span = maximum_filter1d(data, size, axis=-1, mode='nearest') - minimum_filter1d(data, size, axis=-1, mode='nearest')
    bad = np.any(span > threshold_uv*1e-6, axis=0)
    edges = np.diff(np.r_[False, bad, False].astype(int))
    return [(a/sfreq, b/sfreq, 'source_artifact') for a,b in
            zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))]


def _filter(data, sfreq, cfg, boundaries=()):
    if boundaries:
        cuts = sorted({0, data.shape[-1], *(max(0, min(data.shape[-1],
            sample_boundary(t, sfreq))) for t in boundaries)})
        result = data.copy()
        for a, b in zip(cuts[:-1], cuts[1:]):
            if b > a:
                result[:, a:b] = _filter(data[:, a:b], sfreq, cfg)
        return result

    stop = cfg.lowpass + transition_width(cfg.lowpass)
    if sfreq / 2 <= stop:
        raise ValueError(f"Filter lowpass={cfg.lowpass} + transition={transition_width(cfg.lowpass)} exceeds Nyquist={sfreq/2}")
    import mne
    data = mne.filter.filter_data(
        data, sfreq, l_freq=cfg.highpass, h_freq=cfg.lowpass,
        l_trans_bandwidth=min(cfg.highpass, 2.0),
        h_trans_bandwidth=transition_width(cfg.lowpass),
        method="fir", phase="zero-double", verbose="ERROR")
    freqs = notch_frequencies(cfg, sfreq)
    if freqs:
        data = mne.filter.notch_filter(data, sfreq, freqs=freqs, notch_widths=1.0,
            trans_bandwidth=2.0, method="fir", phase="zero-double", verbose="ERROR")
    return data


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

def prepare_branch(working, data, bad_names, cfg):
    """Filter original good channels, interpolate once per branch, then reference.

    Copying the selected Raw preserves annotations, first_samp and geometry.
    Both calls share the same bad-channel decision and interpolation settings.
    """
    branch = working.copy().load_data()
    good_idx = [i for i, name in enumerate(branch.ch_names) if name not in bad_names]
    filtered = np.zeros_like(data)
    boundaries = [t for a, b, kind in annotation_intervals(branch) if kind == "edge" for t in (a, b)]
    filtered[good_idx] = (_filter(data[good_idx], branch.info['sfreq'], cfg, boundaries) if boundaries
                          else _filter(data[good_idx], branch.info['sfreq'], cfg))
    branch._data[:] = filtered
    branch.info["bads"] = list(bad_names)
    if bad_names:
        branch.interpolate_bads(reset_bads=True, mode="accurate", origin="auto", verbose="ERROR")
    if cfg.reference == "average":
        branch.set_eeg_reference("average", projection=False, verbose="ERROR")
    # filter_data works on arrays, so update Raw's filter metadata explicitly.
    with branch.info._unlock():
        branch.info["highpass"] = cfg.highpass
        branch.info["lowpass"] = cfg.lowpass
    if not np.isfinite(branch.get_data()).all():
        raise ValueError("Non-finite samples after interpolation")
    from .lep import continuous_filter_guard
    from dataclasses import replace
    branch._pipeline_source_artifacts = artifact_intervals(data[good_idx], branch.info['sfreq'], cfg.ica_fit_peak_to_peak_uv, cfg.ica_fit_window_seconds)
    branch._pipeline_filter_guard = continuous_filter_guard(branch.info['sfreq'], replace(cfg, target_sfreq=None))
    branch._pipeline_spatial_signature = (
        tuple(branch.ch_names), tuple(bad_names), cfg.reference,
        "spherical_spline", "accurate", "auto")
    return branch

def preprocess_raw(raw, config: PipelineConfig | None = None, events_seconds=None, diagnostic_dir=None) -> Preprocessed:
    cfg = config or PipelineConfig()
    try:
        sfreq = float(raw.info["sfreq"])
        source_sfreq = sfreq
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Missing valid sampling frequency required for preprocessing") from exc
    if not np.isfinite(sfreq) or sfreq <= 0:
        raise ValueError("Missing valid sampling frequency required for preprocessing")
    validate_sampling(sfreq, cfg)
    source_lowpass = raw.info.get("lowpass")
    if (cfg.high_gamma_band is not None and source_lowpass is not None
            and source_lowpass < cfg.high_gamma_band[1]):
        raise PreprocessingError(f"Source lowpass metadata={source_lowpass} Hz cannot support "
                                 f"high_gamma={cfg.high_gamma_band}; explicitly disable high_gamma")
    if not getattr(raw, "ch_names", None):
        raise ValueError("Missing channel names required for preprocessing")
    try:
        channel_types = raw.get_channel_types()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Missing channel types required for preprocessing") from exc
    if len(channel_types) != len(raw.ch_names) or any(not kind for kind in channel_types):
        raise ValueError("Incomplete channel types required for preprocessing")
    working = raw.copy()
    # Keep the fixed spectral montage when only an N1 electrode is absent.
    # These placeholders are always interpolated and never eligible for N1.
    from .lep import LEPConfig
    missing_n1 = [name for name in ('T7', 'T8', 'Fz')
                  if name not in {canonical_channel(n) for n in working.ch_names}]
    if missing_n1 and LEPConfig(**cfg.lep).enabled:
        import mne
        working.load_data()
        placeholders = mne.io.RawArray(np.zeros((len(missing_n1), working.n_times)),
            mne.create_info(missing_n1, sfreq, 'eeg'), first_samp=working.first_samp, verbose='ERROR')
        working.add_channels([placeholders], force_update_info=True)
        working.info['bads'] = list(working.info['bads']) + missing_n1
        channel_types = working.get_channel_types()
    indices, original_names = select_channels(working)
    selected_names = [canonical_channel(n) for n in original_names]
    selected_types = [channel_types[i].lower() for i in indices]
    non_eeg = [name for name, kind in zip(original_names, selected_types) if kind != "eeg"]
    if non_eeg:
        raise ValueError("Required channels are not marked as EEG: " + ", ".join(non_eeg))
    data = working.get_data(picks=indices)
    metadata_bads = [canonical_channel(n) for n in working.info.get("bads", [])]
    manual = [canonical_channel(n) for n in cfg.bad_channel_manual]
    unknown_manual = sorted(set(manual) - set(EEG_CHANNELS))
    if unknown_manual:
        raise PreprocessingError("Unknown manually marked EEG channels: " + ", ".join(unknown_manual),
                                 {"status": "failed", "failure_reason": "unknown_manual_channel",
                                  "marked_manual": manual})
    # Normalize names on the private copy before attaching standard positions.
    working.pick(indices)
    working.rename_channels({old: new for old, new in zip(list(working.ch_names), selected_names) if old != new})
    try:
        working.set_montage("standard_1020", match_case=False, on_missing="raise", verbose="ERROR")
    except Exception as exc:
        raise PreprocessingError(f"Could not assign required standard_1020 electrode positions: {exc}") from exc
    positions = working.get_montage().get_positions()["ch_pos"]
    missing_positions = [name for name in EEG_CHANNELS if name not in positions or not np.isfinite(positions[name]).all()]
    if missing_positions:
        raise PreprocessingError("Missing valid montage positions: " + ", ".join(missing_positions))
    diagnostics = {"missing_n1_channels": missing_n1, "marked_manual": [n for n in EEG_CHANNELS if n in manual],
                   "marked_metadata": [n for n in EEG_CHANNELS if n in metadata_bads],
                   "marked_automatic": [], "channels": {}, "interpolated_channels": [],
                   "interpolation_method": "MNE EEG spherical spline",
                   "parameters": {k: getattr(cfg, k) for k in (
                       "bad_channel_auto_detect", "bad_channel_manual", "bad_channel_window_seconds",
                       "bad_channel_flat_std_uv", "bad_channel_noise_std_uv", "bad_channel_noise_mad_z",
                       "bad_channel_noise_window_fraction", "bad_channel_max_interpolated")},
                   "operation_order": ["channel_selection_and_normalization", "montage_validation",
                       "quality_assessment_before_filter", "filter_good_channels",
                       "interpolate_bad_channels"], "status": "in_progress", "failure_reason": None}
    if cfg.reference == "average":
        diagnostics["operation_order"].append("average_reference")
    try:
        bad_names, channel_diag = detect_bad_channels(data, sfreq, selected_names,
            metadata_bads, manual, cfg)
        diagnostics["channels"] = channel_diag
        # With automation disabled, preserve only mandatory NaN/Inf checks;
        # metadata and manual flags remain mandatory as well.
        if not cfg.bad_channel_auto_detect:
            mandatory = set(metadata_bads) | set(manual)
            for i, name in enumerate(selected_names):
                if not np.isfinite(data[i]).all(): mandatory.add(name)
            bad_names = [name for name in EEG_CHANNELS if name in mandatory]
            diagnostics["channels"] = channel_diag
        diagnostics["marked_automatic"] = [n for n in bad_names
            if n not in manual and n not in metadata_bads]
        if len(bad_names) > cfg.bad_channel_max_interpolated:
            raise PreprocessingError(f"Bad-channel count {len(bad_names)} exceeds interpolation limit {cfg.bad_channel_max_interpolated}", diagnostics)
        if len(EEG_CHANNELS) - len(bad_names) < 4:
            raise PreprocessingError("Too few good EEG channels remain for interpolation", diagnostics)
        try:
            source_artifacts = artifact_intervals(data[[i for i,n in enumerate(selected_names) if n not in bad_names]],
                                                  sfreq, cfg.epoch_peak_to_peak_uv)
            analytical = prepare_branch(working, data, bad_names, cfg)
        except Exception as exc:
            raise PreprocessingError(f"interpolation_failed: {exc}", diagnostics) from exc
        filtered = analytical.get_data()
        diagnostics["interpolated_channels"] = bad_names
        for channel in EEG_CHANNELS:
            diagnostics["channels"][channel]["interpolated"] = channel in bad_names
        if cfg.reference == "average":
            diagnostics["reference_channels"] = EEG_CHANNELS.copy()
        else:
            diagnostics["reference_channels"] = []
        diagnostics["status"] = "success"
        data = filtered
    except PreprocessingError as exc:
        if exc.diagnostics:
            diagnostics = exc.diagnostics
        diagnostics["status"] = "failed"
        diagnostics["failure_reason"] = str(exc)
        raise
    warnings = []
    if cfg.reference not in {"average", "none", "unknown", None}:
        LOGGER.warning("Reference %s not applied", cfg.reference)
    ica_diagnostics = {"status": "disabled"}
    if cfg.enable_ica:
        from .ica import clean_with_ica
        data, ica_diagnostics = clean_with_ica(
            working, analytical, working.get_data(), bad_names, cfg,
            diagnostics, prepare_branch, diagnostic_dir)
        if ica_diagnostics["status"] == "skipped_due_to_failure":
            warnings.append("ICA skipped after failure: " + ica_diagnostics["failure_reason"])
    removed_muscle = [c["index"] for c in ica_diagnostics.get("components", [])
        if c["remove"] and c["label"] == "muscle artifact"] if ica_diagnostics.get("status") == "applied" else []
    ica_diagnostics.update(removed_muscle_components=removed_muscle, removed_muscle_count=len(removed_muscle))
    if cfg.target_sfreq and abs(cfg.target_sfreq - sfreq) > 1e-9:
        try:
            from scipy.signal import resample_poly
            from fractions import Fraction
            ratio = Fraction(cfg.target_sfreq / sfreq).limit_denominator(1000)
            actual_sfreq = sfreq * ratio.numerator / ratio.denominator
            if not np.isclose(actual_sfreq, cfg.target_sfreq, rtol=0, atol=1e-8):
                raise ValueError(f"Resampling ratio cannot represent target {cfg.target_sfreq} Hz exactly; actual={actual_sfreq}")
            data = resample_poly(data, ratio.numerator, ratio.denominator, axis=-1)
            sfreq = actual_sfreq
        except ImportError as exc: raise ImportError("Resampling requires scipy") from exc
    if not np.isfinite(data).all():
        raise ValueError("Preprocessing produced non-finite EEG samples")
    epochs, times, epoch_event_indices, rejected, event_windows = [], [], [], [], []
    raw_events = [float(event) for event in (events_seconds or [])]
    if cfg.event_time_unit == "milliseconds":
        raw_events = [event / 1000.0 for event in raw_events]
    elif cfg.event_time_unit == "samples":
        raw_events = [event / source_sfreq for event in raw_events]
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
    isi_diagnostics = {"raw_markers": isi_statistics(event_records, "event", cfg.isi_warning_threshold_seconds),
                       "analysis_events": isi_statistics(analysis_records, "cluster_event", cfg.isi_warning_threshold_seconds)}
    from .lep import continuous_filter_guard
    from .window_quality import processing_intervals
    guard = continuous_filter_guard(source_sfreq, cfg)
    exclusions = processing_intervals(data.shape[1]/sfreq, annotation_intervals(working) + source_artifacts, guard)
    diagnostics['source_artifact_intervals'] = source_artifacts
    diagnostics['processing_guard_seconds'] = guard
    diagnostics['quality_exclusions'] = exclusions
    legacy_diagnostics = []
    for record in analysis_records:
        event_index, event = record["event_index"], record["cluster_event"]
        # Preserve the public legacy ``epochs`` interface.  New response
        # windows are stored independently below and never replace this
        # configurable tmin/tmax extraction.
        legacy_start = round((float(event) + cfg.tmin) * sfreq)
        legacy_stop = round((float(event) + cfg.tmax) * sfreq)
        legacy_quality = unavailable_quality(cfg.epoch_peak_to_peak_uv, "out_of_bounds")
        if legacy_start >= 0 and legacy_stop <= data.shape[1] and legacy_stop > legacy_start:
            legacy_block = data[:, legacy_start:legacy_stop]
            legacy_quality = evaluate_window_quality(legacy_block, cfg.epoch_peak_to_peak_uv, EEG_CHANNELS,
                interval=(legacy_start/sfreq, legacy_stop/sfreq), exclusions=exclusions)
            if legacy_quality["valid"]:
                epochs.append(legacy_block)
                times.append((event + cfg.tmin, event + cfg.tmax))
                epoch_event_indices.append(event_index)
        legacy_diagnostics.append(dict(event_index=event_index, cluster_id=record["cluster_id"],
                                       start=legacy_start, stop=legacy_stop, **legacy_quality))
        windows = {}
        for name, (relative_start, relative_end) in {"baseline": cfg.baseline_window, **cfg.response_windows}.items():
            start = sample_boundary(float(event) + relative_start, sfreq)
            stop = sample_boundary(float(event) + relative_end, sfreq)
            valid = start >= 0 and stop <= data.shape[1] and stop > start
            block = data[:, start:stop] if valid else None
            quality = (evaluate_window_quality(block, cfg.epoch_peak_to_peak_uv, EEG_CHANNELS,
                            interval=(start/sfreq, stop/sfreq), exclusions=exclusions) if valid
                       else unavailable_quality(cfg.epoch_peak_to_peak_uv, "out_of_bounds"))
            timing = {}
            original_quality = dict(quality)
            previous_overlaps = []
            if name == "baseline":
                timing = baseline_interval(record, analysis_records, cfg)
                previous_overlaps = timing["previous_response_overlaps"]
                if timing["trimmed"]:
                    start = sample_boundary(timing["effective_start_s"], sfreq)
                    relative_start = timing["effective_start_s"] - float(event)
                    # Never repair a window that was outside the recording.
                    block = data[:, start:stop] if valid and stop > start else None
                    if block is not None:
                        quality = evaluate_window_quality(block, cfg.epoch_peak_to_peak_uv, EEG_CHANNELS,
                            interval=(start/sfreq, stop/sfreq), exclusions=exclusions)
                    elif valid:
                        quality = unavailable_quality(cfg.epoch_peak_to_peak_uv, "baseline_too_short")
                timing["too_short"] |= stop - start < cfg.baseline_min_seconds * sfreq - 1e-9
                timing["original_quality"] = original_quality
            reasons = list(quality.get("reasons", [quality["reason"]] if quality["reason"] else []))
            if name == "baseline" and timing["too_short"] and "baseline_too_short" not in reasons:
                reasons.append("baseline_too_short")
            if previous_overlaps and cfg.baseline_overlap_policy == "reject":
                reasons.append("baseline_previous_response_overlap")
            quality.update(valid=not reasons, reason=reasons[0] if reasons else None, reasons=reasons)
            if not quality["valid"]:
                block = None
            overlaps = [other["cluster_event"] for other in analysis_records
                        if other["cluster_id"] != record["cluster_id"]
                        and float(event) < other["cluster_event"]
                        and float(event) + relative_start <= other["cluster_event"] < float(event) + relative_end]
            windows[name] = {"data": block, "start": start, "stop": stop,
                             "relative_start": relative_start, "relative_end": relative_end,
                             "sample_start_s": start / sfreq, "sample_stop_s": stop / sfreq,
                             "sample_count": stop - start if valid else None,
                             "previous_response_contaminated": bool(previous_overlaps),
                             "previous_response_overlaps": previous_overlaps,
                             **timing,
                             **quality,
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
                        rejected, warnings, event_records, event_windows, diagnostics, ica_diagnostics, legacy_diagnostics, isi_diagnostics)

