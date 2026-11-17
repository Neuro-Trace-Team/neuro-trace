from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

import numpy as np

from .config import EEG_CHANNELS, PipelineConfig
from .connectivity import connectivity_by_band, connectivity_pair_rows
from .data_loader import iter_recording_dirs, load_recording
from .entropy import permutation_entropy
from .feature_export import export_recording
from .graph_features import graph_metrics
from .microstates import microstate_metrics
from .preprocessing import preprocess_raw
from .spectral_features import spectral_features

LOGGER = logging.getLogger(__name__)
POWER_FEATURES = {
    "absolute_delta_power", "absolute_theta_power", "absolute_alpha_power",
    "absolute_beta_power", "absolute_gamma_power", "gamma_power",
    "absolute_spectral_power",
}


def _event_metadata(prep, event_index):
    return next((item for item in prep.event_records if item["event_index"] == event_index), {})


def _validate_feature_arrays(feature_values):
    """Return diagnostics without converting scientifically undefined NaNs."""
    checks = {}
    for name, values in feature_values.items():
        array = np.asarray(values, dtype=float)
        finite = array[np.isfinite(array)]
        item = {"n": int(array.size), "n_finite": int(finite.size)}
        if finite.size:
            item["min"] = float(np.min(finite)); item["max"] = float(np.max(finite))
        if name.startswith("relative_") or name == "permutation_entropy":
            item["out_of_expected_range"] = int(np.sum((finite < -1e-9) | (finite > 1 + 1e-9)))
        if name == "paf_hz":
            item["out_of_expected_range"] = int(np.sum((finite < 8) | (finite > 13)))
        checks[name] = item
    return checks


def _baseline_features(prep, event_time, cfg):
    start_s, end_s = cfg.baseline_window
    if start_s >= end_s:
        return None
    if any(start_s <= item["event"] - event_time <= end_s
           for item in prep.event_records):
        return None
    start = round((event_time + start_s) * prep.sfreq)
    stop = round((event_time + end_s) * prep.sfreq)
    if start < 0 or stop > prep.data.shape[1] or stop - start < 8:
        return None
    block = prep.data[:, start:stop]
    if not np.isfinite(block).all() or np.max(np.abs(block)) > cfg.amplitude_uv * 1e-6:
        return None
    return spectral_features(block, prep.sfreq, cfg.analysis_band, cfg.gamma_band,
                             cfg.alpha_peak_min_snr, cfg.alpha_min_power,
                             cfg.psd_nperseg, cfg.psd_overlap)

def _mean(values):
    values = np.asarray(values, dtype=float)
    return float(np.nanmean(values)) if np.isfinite(values).any() else np.nan

def _window_features(row, name, block, prep, cfg):
    prefix = {"baseline": "baseline", "early_response": "early", "sustained_response": "sustained"}[name]
    if block is None:
        row[f"{prefix}_window_valid"] = False
        return None, None
    sf = spectral_features(block, prep.sfreq, cfg.analysis_band, cfg.gamma_band,
                           cfg.alpha_peak_min_snr, cfg.alpha_min_power,
                           cfg.psd_nperseg, cfg.psd_overlap, cfg.paf_prominence)
    ent = np.array([permutation_entropy(x, cfg.entropy_order, cfg.entropy_delay,
                                        cfg.entropy_normalize) for x in block])
    row[f"{prefix}_window_valid"] = True
    row[f"{prefix}_sample_count"] = block.shape[-1]
    row[f"{prefix}_permutation_entropy"] = _mean(ent)
    row[f"{prefix}_paf"] = _mean(sf["paf_hz"])
    row[f"{prefix}_paf_prominence"] = _mean(sf["paf_prominence"])
    row[f"{prefix}_paf_valid"] = bool(np.any(sf["paf_quality"]))
    for feature, values in sf.items():
        if feature in {"paf_hz", "paf_prominence", "paf_quality"}:
            continue
        row[f"{prefix}_{feature}"] = _mean(values) * (1e12 if feature in POWER_FEATURES else 1)
    return sf, ent

def _baseline_changes(row, baseline_sf, baseline_ent, response_sf, response_ent, response_name):
    prefix = "early" if response_name == "early_response" else "sustained"
    row[f"{prefix}_baseline_valid"] = baseline_sf is not None
    if baseline_sf is None or response_sf is None:
        return
    for feature, base_values in baseline_sf.items():
        if feature in {"paf_quality", "paf_prominence"} or feature not in response_sf:
            continue
        base = np.asarray(base_values, dtype=float); response = np.asarray(response_sf[feature], dtype=float)
        row[f"baseline_{feature}"] = _mean(base) * (1e12 if feature in POWER_FEATURES else 1)
        if feature not in POWER_FEATURES:
            continue
        valid = np.isfinite(response) & np.isfinite(base) & (base > 0)
        ratio = np.full(base.shape, np.nan); db = np.full(base.shape, np.nan)
        ratio[valid] = (response[valid] - base[valid]) / base[valid]
        positive = valid & (response > 0)
        db[positive] = 10 * np.log10(response[positive] / base[positive])
        label = feature.removeprefix("absolute_")
        row[f"{prefix}_{label}_relative_change_mean_channels"] = _mean(ratio)
        row[f"{prefix}_{label}_relative_change_global"] = ((np.nanmean(response[valid]) - np.nanmean(base[valid])) / np.nanmean(base[valid])
            if np.any(valid) and np.nanmean(base[valid]) > 0 else np.nan)
        row[f"{prefix}_{label}_db_change_mean_channels"] = _mean(db)
        row[f"{prefix}_{label}_db_change_global"] = (10 * np.log10(np.nanmean(response[positive]) / np.nanmean(base[positive]))
            if np.any(positive) else np.nan)
        if prefix == "early":
            # Original names are retained as Method A aliases.
            row[f"relative_change_{feature}"] = _mean(ratio)
            row[f"db_change_{feature}"] = _mean(db)
    if baseline_ent is not None and response_ent is not None:
        row[f"{prefix}_permutation_entropy_change"] = _mean(response_ent) - _mean(baseline_ent)
    row[f"{prefix}_paf_change"] = row.get(f"{prefix}_paf", np.nan) - _mean(baseline_sf.get("paf_hz", np.array([np.nan])))


def process_recording(directory, output_dir, experiment_id="", subject_id="", recording_id="", config=None):
    cfg = config or PipelineConfig()
    report = {"parameters": vars(cfg), "channels": EEG_CHANNELS,
              "channel_order_validated": True,
              "units": {"signal": "V (MNE internal)", "psd": "V^2/Hz", "absolute_power": "uV^2"},
              "warnings": [], "errors": [], "rejection_reasons": []}
    rec = None
    try:
        rec = load_recording(directory, preload=False)
        prep = preprocess_raw(rec.raw, cfg, rec.events_seconds)
    except Exception as exc:
        report["errors"].append(str(exc))
        if rec is not None:
            report.update({"source_file": str(rec.path), "original_sfreq": rec.raw.info.get("sfreq"),
                           "raw_channel_names": rec.raw.ch_names, "warnings": rec.warnings,
                           "pain_ratings_available": rec.pain_ratings is not None})
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "preprocessing_report.json").write_text(
            __import__("json").dumps(report, indent=2, default=str))
        return report

    channels, features, micros, networks, connectivity_rows = [], [], [], [], []
    conns = {"channel_names": np.array(EEG_CHANNELS)}
    feature_diagnostics = []
    for wid, item in enumerate(prep.event_windows):
        event_info = item["record"]; event_time = event_info["cluster_event"]
        row = {"experiment_id": experiment_id, "subject_id": subject_id, "recording_id": recording_id,
               "window_id": wid, "event_id": event_info["cluster_id"], "event_index": event_info["event_index"],
               "event_time_s": event_time, "event_timestamp": event_time, "cluster_id": event_info["cluster_id"],
               "cluster_event_time_s": event_time, "cluster_size": event_info["cluster_size"],
               "overlap_flag": event_info["overlap_flag"], "sampling_frequency_hz": prep.sfreq}
        for window_name, window in item["windows"].items():
            prefix = "baseline" if window_name == "baseline" else "early" if window_name == "early_response" else "sustained"
            row[f"{prefix}_start_s"] = event_time + window["relative_start"]
            row[f"{prefix}_end_s"] = event_time + window["relative_end"]
            row[f"{prefix}_out_of_bounds"] = window["reason"] == "out_of_bounds"
            row[f"{prefix}_overlaps_next_event"] = window["overlaps_next_event"]
        baseline_block = item["windows"]["baseline"]["data"]
        baseline_sf, baseline_ent = _window_features(row, "baseline", baseline_block, prep, cfg)
        results = {}
        for window_name in ("early_response", "sustained_response"):
            block = item["windows"][window_name]["data"]
            sf, ent = _window_features(row, window_name, block, prep, cfg)
            results[window_name] = (block, sf, ent)
            _baseline_changes(row, baseline_sf, baseline_ent, sf, ent, window_name)
            if block is not None:
                connectivity_rows.extend(connectivity_pair_rows(
                    block, prep.sfreq, event_info["cluster_id"], event_time,
                    "early" if window_name == "early_response" else "sustained",
                    cfg.connectivity_min_observations, cfg.connectivity_segment_seconds,
                    cfg.connectivity_include_gamma))
        # Backward-compatible aliases retain the former event-centered
        # (tmin/tmax) field names and now explicitly refer to early response.
        early_block, early_sf, early_ent = results["early_response"]
        if early_block is not None and early_sf is not None:
            row["segment_start_s"] = event_time + cfg.response_windows["early_response"][0]
            row["segment_end_s"] = event_time + cfg.response_windows["early_response"][1]
            row["baseline_available"] = baseline_sf is not None
            row["permutation_entropy"] = _mean(early_ent)
            row["paf_hz"] = _mean(early_sf["paf_hz"])
            row["paf_prominence"] = _mean(early_sf["paf_prominence"])
            row["paf_quality"] = bool(np.any(early_sf["paf_quality"]))
            for feature, values in early_sf.items():
                if feature not in {"paf_hz", "paf_prominence", "paf_quality"}:
                    row[feature] = _mean(values) * (1e12 if feature in POWER_FEATURES else 1)
        features.append(row)
        block, sf, ent = results["early_response"]
        if block is None:
            continue
        for ci, channel in enumerate(EEG_CHANNELS):
            channel_row = {key: row[key] for key in ("experiment_id", "subject_id", "recording_id",
                "window_id", "event_index", "event_time_s", "cluster_id", "cluster_event_time_s",
                "cluster_size", "overlap_flag", "sampling_frequency_hz")}
            channel_row.update({"channel": channel, "window_type": "early_response", "permutation_entropy": ent[ci]})
            channel_row.update({name: (float(values[ci]) * 1e12 if name in POWER_FEATURES else values[ci])
                                for name, values in sf.items()})
            channels.append(channel_row)
        feature_diagnostics.append(_validate_feature_arrays({**sf, "permutation_entropy": ent}))
        for metrics in microstate_metrics(block, prep.sfreq, cfg.microstate_classes,
                                          cfg.microstate_random_state, cfg.microstate_max_samples):
            micros.append({**row, **metrics})
        for band, matrix in connectivity_by_band(block, prep.sfreq, cfg.connectivity_min_observations,
                                                  cfg.connectivity_segment_seconds, False).items():
            conns[f"window_{wid}_early_{band}"] = matrix
            graph = graph_metrics(matrix, cfg.graph_density)
            networks.append({**row, "band": band,
                             **{name: value.tolist() if isinstance(value, np.ndarray) else value
                                for name, value in graph.items()}})

    report.update({"source_file": str(rec.path), "original_sfreq": rec.raw.info.get("sfreq"),
                   "raw_channel_names": rec.raw.ch_names, "raw_channel_types": rec.raw.get_channel_types(),
                   "target_sfreq": prep.sfreq, "n_raw_events": len(prep.event_records),
                   "n_analysis_events": len(prep.event_windows), "n_epochs": len(prep.epochs),
                   "n_rejected": len(prep.rejected), "rejection_reasons": prep.rejected,
                   "event_records": prep.event_records, "feature_diagnostics": feature_diagnostics,
                   "warnings": rec.warnings + prep.warnings, "pain_ratings_available": rec.pain_ratings is not None,
                   "events_type_known": False, "applied_reference": cfg.reference,
                   "reference_scope": "selected 19 EEG channels only",
                   "versions": {"python": sys.version, "platform": platform.platform()}})
    export_recording(output_dir, channels, features, micros, networks, conns, report, connectivity_rows)
    return report


def process_dataset(input_root, output_root, config=None, experiment=None, subject=None):
    return [process_recording(directory, Path(output_root) / exp / sub / run,
                              exp, sub, run, config)
            for exp, sub, run, directory in iter_recording_dirs(input_root, experiment, subject)]
