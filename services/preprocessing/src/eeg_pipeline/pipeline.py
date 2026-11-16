from __future__ import annotations

import json
import logging
import platform
import sys
from pathlib import Path

import numpy as np

from .config import EEG_CHANNELS, PipelineConfig
from .connectivity import connectivity_by_band, connectivity_pair_rows
from .data_loader import iter_recording_dirs, load_recording
from .entropy import permutation_entropy
from .feature_export import export_recording, json_safe
from .graph_features import graph_metrics
from .microstates import microstate_metrics
from .preprocessing import preprocess_raw, PreprocessingError
from .spectral_features import spectral_features
from .window_quality import (quality_summary, summary_from_counts, WINDOW_TYPES)

LOGGER = logging.getLogger(__name__)
POWER_FEATURES = {
    "absolute_delta_power", "absolute_theta_power", "absolute_alpha_power",
    "absolute_beta_power", "absolute_gamma_power", "gamma_power",
    "absolute_spectral_power", "absolute_high_gamma_power",
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


def _mean(values):
    values = np.asarray(values, dtype=float)
    return float(np.nanmean(values)) if np.isfinite(values).any() else np.nan

def _window_features(row, name, block, prep, cfg):
    prefix = {"baseline": "baseline", "early_response": "early", "sustained_response": "sustained"}[name]
    if cfg.high_gamma_band is not None:
        row[f"{prefix}_absolute_high_gamma_power"] = np.nan
        row[f"{prefix}_high_gamma_power_valid"] = False
        if name == "baseline":
            row["baseline_high_gamma_power_db_change_mean_channels"] = np.nan
            row["baseline_high_gamma_power_db_change_global"] = np.nan
    if block is None:
        row[f"{prefix}_window_valid"] = False
        return None, None
    sf = spectral_features(block, prep.sfreq, cfg.analysis_band, cfg.gamma_band,
                           cfg.alpha_peak_min_snr, cfg.alpha_min_power,
                           cfg.psd_nperseg, cfg.psd_overlap, cfg.paf_prominence, bands=cfg.spectral_bands)
    ent = np.array([permutation_entropy(x, cfg.entropy_order, cfg.entropy_delay,
                                        cfg.entropy_normalize) for x in block])
    row[f"{prefix}_window_valid"] = True
    row[f"{prefix}_sample_count"] = block.shape[-1]
    row[f'{prefix}_welch_nperseg'] = min(block.shape[-1], int(2*prep.sfreq), cfg.psd_nperseg or int(2*prep.sfreq))
    row[f'{prefix}_welch_noverlap'] = int(row[f'{prefix}_welch_nperseg']*cfg.psd_overlap)
    row[f"{prefix}_permutation_entropy"] = _mean(ent)
    row[f"{prefix}_paf"] = _mean(sf["paf_hz"])
    row[f"{prefix}_paf_prominence"] = _mean(sf["paf_prominence"])
    row[f"{prefix}_paf_valid"] = bool(np.any(sf["paf_quality"]))
    for feature, values in sf.items():
        if feature in {"paf_hz", "paf_prominence", "paf_quality"}:
            continue
        row[f"{prefix}_{feature}"] = (bool(np.all(values)) if feature == "high_gamma_power_valid"
            else _mean(values) * (1e12 if feature in POWER_FEATURES else 1))
    if name == "baseline" and "absolute_high_gamma_power" in sf:
        power = sf["absolute_high_gamma_power"]
        if np.any(np.isfinite(power) & (power > 0)):
            row["baseline_high_gamma_power_db_change_mean_channels"] = 0.0
            row["baseline_high_gamma_power_db_change_global"] = 0.0
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
        row[f"baseline_{feature}"] = (bool(np.all(base)) if feature == "high_gamma_power_valid"
            else _mean(base) * (1e12 if feature in POWER_FEATURES else 1))
        if feature not in POWER_FEATURES:
            continue
        valid = np.isfinite(response) & np.isfinite(base) & (base > 0) & (response >= 0)
        ratio = np.full(base.shape, np.nan); db = np.full(base.shape, np.nan)
        ratio[valid] = (response[valid] - base[valid]) / base[valid]
        positive = valid & (response > 0)
        db[positive] = 10 * np.log10(response[positive] / base[positive])
        label = feature.removeprefix("absolute_")
        if feature != "absolute_high_gamma_power":
            row[f"{prefix}_{label}_relative_change_mean_channels"] = _mean(ratio)
            row[f"{prefix}_{label}_relative_change_global"] = ((np.nanmean(response[valid]) - np.nanmean(base[valid])) / np.nanmean(base[valid])
                if np.any(valid) and np.nanmean(base[valid]) > 0 else np.nan)
        row[f"{prefix}_{label}_db_change_mean_channels"] = _mean(db)
        from .baseline import global_changes
        row[f"{prefix}_{label}_db_change_global"] = global_changes(response, base)[1]
        if prefix == "early":
            # Original names are retained as Method A aliases.
            if feature != "absolute_high_gamma_power":
                row[f"relative_change_{feature}"] = _mean(ratio)
            row[f"db_change_{feature}"] = _mean(db)
    if baseline_ent is not None and response_ent is not None:
        row[f"{prefix}_permutation_entropy_change"] = _mean(response_ent) - _mean(baseline_ent)
    for label, base_values, response_values in (
            ('paf', baseline_sf.get('paf_hz', []), response_sf.get('paf_hz', [])),
            ('permutation_entropy', baseline_ent if baseline_ent is not None else [], response_ent if response_ent is not None else [])):
        bm, rm = np.isfinite(base_values), np.isfinite(response_values)
        row[f'{prefix}_{label}_channel_masks_equal'] = bool(np.array_equal(bm, rm))
        row[f'{prefix}_{label}_baseline_channel_indices'] = json.dumps(np.flatnonzero(bm).tolist())
        row[f'{prefix}_{label}_response_channel_indices'] = json.dumps(np.flatnonzero(rm).tolist())
    row[f"{prefix}_paf_change"] = row.get(f"{prefix}_paf", np.nan) - _mean(baseline_sf.get("paf_hz", np.array([np.nan])))


def process_recording(directory, output_dir, experiment_id="", subject_id="", recording_id="", config=None):
    cfg = config or PipelineConfig()
    report = {"parameters": vars(cfg), "feature_schema_version": "2.1",
              "experiment_id": experiment_id, "subject_id": subject_id, "recording_id": recording_id,
              "preprocessing_status": "failed", "channels": EEG_CHANNELS,
              "channel_order_validated": True,
              "units": {"signal": "V (MNE internal)", "psd": "V^2/Hz", "absolute_power": "uV^2", "baseline_power_change": "dB"},
              "warnings": [], "errors": [], "rejection_reasons": [],
              "channel_diagnostics": {"status": "not_started", "failure_reason": None},
              "ica_diagnostics": {"status": "not_started" if cfg.enable_ica else "disabled"}}
    rec = None
    try:
        rec = load_recording(directory, preload=False)
        from .preprocessing import notch_frequencies, transition_width
        report["filtering"] = {
            "requested_band_hz": [cfg.highpass, cfg.lowpass],
            "applied_band_hz": None,
            "source_sfreq_hz": rec.raw.info["sfreq"], "requested_target_sfreq_hz": cfg.target_sfreq,
            "source_highpass_hz": rec.raw.info.get("highpass"),
            "source_lowpass_hz": rec.raw.info.get("lowpass"),
            "source_filter_metadata_caveat": "Header metadata may be incomplete; sampling rate does not prove high gamma availability",
            "relative_power_normalization_hz": cfg.analysis_band,
            "spectral_bands_hz": cfg.spectral_bands,
            "phase": "zero-double", "method": "FIR firwin Hamming",
            "low_transition_hz": min(cfg.highpass, 2.0),
            "high_transition_hz": transition_width(cfg.lowpass),
            "notch_hz": [], "notch_width_hz": 1.0, "notch_transition_hz": 2.0,
            "resampling": "scipy resample_poly, Kaiser beta=5, rational ratio"}
        prep = preprocess_raw(rec.raw, cfg, rec.events_seconds, diagnostic_dir=output_dir)
    except Exception as exc:
        report["errors"].append(str(exc))
        report["channel_diagnostics"] = getattr(exc, "diagnostics", report["channel_diagnostics"])
        report["channel_diagnostics"].setdefault("status", "failed")
        report["ica_diagnostics"] = getattr(exc, "ica_diagnostics", {}) or report["ica_diagnostics"]
        if report["channel_diagnostics"].get("status") != "success":
            report["channel_diagnostics"]["failure_reason"] = str(exc)
        if rec is not None:
            report.update({"source_file": str(rec.path), "original_sfreq": rec.raw.info.get("sfreq"),
                           "raw_channel_names": rec.raw.ch_names, "warnings": rec.warnings,
                           "pain_ratings_available": rec.pain_ratings is not None})
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "preprocessing_report.json").write_text(
            __import__("json").dumps(json_safe(report), indent=2, default=str, allow_nan=False))
        return report

    report["filtering"].update(applied_band_hz=[cfg.highpass, cfg.lowpass],
        notch_hz=notch_frequencies(cfg, rec.raw.info["sfreq"]), actual_sfreq_hz=prep.sfreq)
    from .lep import extract_lep, continuous_filter_guard
    bad_annotations = [(float(a['onset'] - rec.raw.first_time),
                        float(a['onset'] - rec.raw.first_time + a['duration']))
                       for a in rec.raw.annotations
                       if a['description'].lower().startswith(('bad', 'edge'))]
    lep_rows, report['lep'] = extract_lep(prep, cfg, getattr(rec, 'event_metadata', ()),
        bad_annotations, continuous_filter_guard(rec.raw.info['sfreq'], cfg), rec.raw.info['sfreq'])
    report['lep']['upstream_filtering'] = report['filtering'].copy()
    from .tfr import extract_tfr, preprocessing_guard
    tfr_rows, report['tfr'] = extract_tfr(prep, cfg, getattr(rec, 'event_metadata', ()),
        bad_annotations, preprocessing_guard(rec.raw.info['sfreq'], cfg),
        (rec.raw.info.get('highpass', 0.), min(rec.raw.info.get('lowpass', rec.raw.info['sfreq']/2),
                                             rec.raw.info['sfreq']/2)), output_dir)
    report['tfr']['upstream_filtering'] = report['filtering'].copy()
    report["high_gamma_review"] = []
    channels, features, micros, networks, connectivity_rows = [], [], [], [], []
    conns = {"channel_names": np.array(EEG_CHANNELS)}
    feature_diagnostics = []
    for wid, item in enumerate(prep.event_windows):
        event_info = item["record"]; event_time = event_info["cluster_event"]
        from .feature_schema import feature_defaults
        row = {**feature_defaults(cfg), "experiment_id": experiment_id, "subject_id": subject_id, "recording_id": recording_id,
               "window_id": wid, "event_id": event_info["cluster_id"], "event_index": event_info["event_index"],
               "event_time_s": event_time, "event_timestamp": event_time, "cluster_id": event_info["cluster_id"],
               "cluster_event_time_s": event_time, "cluster_size": event_info["cluster_size"],
               "overlap_flag": event_info["overlap_flag"], "sampling_frequency_hz": prep.sfreq}
        from .data_loader import match_pain_rating
        row.update(match_pain_rating(event_info, prep.event_records, getattr(rec, 'event_metadata', ()), rec.pain_ratings))
        row['source_csv_row'] = getattr(rec, 'event_metadata', ())[event_info['event_index']].get('source_csv_row') if event_info['event_index'] < len(getattr(rec, 'event_metadata', ())) else None
        row['source_event_index'] = event_info['event_index']
        row['feature_schema_version'] = '2.1'
        row.update(lep_rows[event_info["event_index"]])
        row.update(tfr_rows.get(event_info["event_index"], {}))
        row["relative_power_normalization_low_hz"], row["relative_power_normalization_high_hz"] = cfg.analysis_band
        if cfg.high_gamma_band is not None:
            row.update(absolute_high_gamma_power=np.nan, high_gamma_power_valid=False)
            for prefix in ("early", "sustained"):
                for suffix in ("mean_channels", "global"):
                    row[f"{prefix}_high_gamma_power_db_change_{suffix}"] = np.nan
            row["db_change_absolute_high_gamma_power"] = np.nan
        legacy = prep.legacy_window_diagnostics[wid]
        row["legacy_window_valid"] = legacy["valid"]
        row["legacy_invalid_reason"] = legacy["reason"]
        row["legacy_max_peak_to_peak_uv"] = legacy["max_peak_to_peak_uv"]
        for window_name, window in item["windows"].items():
            prefix = "baseline" if window_name == "baseline" else "early" if window_name == "early_response" else "sustained"
            row[f"{prefix}_start_s"] = event_time + window["relative_start"]
            row[f"{prefix}_end_s"] = event_time + window["relative_end"]
            row[f"{prefix}_sample_start_s"] = window["sample_start_s"]
            row[f"{prefix}_sample_stop_s"] = window["sample_stop_s"]
            row[f"{prefix}_sample_count"] = window["sample_count"]
            row[f"{prefix}_invalid_reasons"] = json.dumps(window["reasons"])
            row[f"{prefix}_invalid_reason"] = window["reason"]
            row[f"{prefix}_max_peak_to_peak_uv"] = window["max_peak_to_peak_uv"]
            row[f"{prefix}_out_of_bounds"] = window["reason"] == "out_of_bounds"
            row[f"{prefix}_overlaps_next_event"] = window["overlaps_next_event"]
        baseline_window = item["windows"]["baseline"]
        for key in ("original_start_s", "original_end_s", "trimmed", "duration_seconds"):
            row[f"baseline_{key}"] = baseline_window[key]
        row["baseline_original_quality"] = json.dumps(baseline_window["original_quality"])
        row["baseline_previous_response_contaminated"] = baseline_window["previous_response_contaminated"]
        row["baseline_previous_response_overlaps"] = json.dumps(baseline_window["previous_response_overlaps"])
        row["baseline_previous_event_indices"] = json.dumps([o["event_index"] for o in baseline_window["previous_response_overlaps"]])
        row["baseline_previous_cluster_ids"] = json.dumps([o["cluster_id"] for o in baseline_window["previous_response_overlaps"]])
        baseline_block = item["windows"]["baseline"]["data"]
        baseline_sf, baseline_ent = _window_features(row, "baseline", baseline_block, prep, cfg)
        results = {}
        for window_name in ("early_response", "sustained_response"):
            block = item["windows"][window_name]["data"]
            sf, ent = _window_features(row, window_name, block, prep, cfg)
            results[window_name] = (block, sf, ent)
            _baseline_changes(row, baseline_sf, baseline_ent, sf, ent, window_name)
            if block is not None:
                try:
                    connectivity_rows.extend(connectivity_pair_rows(
                        block, prep.sfreq, event_info["cluster_id"], event_time,
                        "early" if window_name == "early_response" else "sustained",
                        cfg.connectivity_min_observations, cfg.connectivity_segment_seconds,
                        cfg.connectivity_include_gamma, bands=cfg.connectivity_bands))
                except Exception as exc:
                    report['warnings'].append(f'connectivity_pairs event {wid} {window_name}: {type(exc).__name__}: {exc}')

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
                    row[feature] = (bool(np.all(values)) if feature == "high_gamma_power_valid" else _mean(values) * (1e12 if feature in POWER_FEATURES else 1))
        features.append(row)
        all_results = {"baseline": (baseline_block, baseline_sf, baseline_ent), **results}
        for window_name, (window_block, window_sf, window_ent) in all_results.items():
            if window_block is None:
                continue
            for ci, channel in enumerate(EEG_CHANNELS):
                channel_row = {key: row[key] for key in ("experiment_id", "subject_id", "recording_id",
                    "window_id", "event_index", "event_time_s", "cluster_id", "cluster_event_time_s",
                    "cluster_size", "overlap_flag", "sampling_frequency_hz")}
                channel_row.update(relative_power_normalization_low_hz=cfg.analysis_band[0],
                    relative_power_normalization_high_hz=cfg.analysis_band[1],
                    channel=channel, window_type=window_name,
                    interpolated=channel in prep.channel_diagnostics.get("interpolated_channels", []),
                    permutation_entropy=window_ent[ci])
                channel_row.update({name: (float(values[ci]) * 1e12 if name in POWER_FEATURES else values[ci])
                                    for name, values in window_sf.items()})
                if "absolute_high_gamma_power" in window_sf:
                    base = baseline_sf["absolute_high_gamma_power"][ci] if baseline_sf is not None else np.nan
                    response = window_sf["absolute_high_gamma_power"][ci]
                    channel_row["high_gamma_power_db_change"] = (10*np.log10(response/base)
                        if np.isfinite(base) and np.isfinite(response) and base > 0 and response > 0 else np.nan)
                channels.append(channel_row)
            if "absolute_high_gamma_power" in window_sf:
                values = window_sf["absolute_high_gamma_power"] * 1e12
                report["high_gamma_review"].append({"event_id": event_info["cluster_id"], "window_type": window_name,
                    "channel_power_uv2": dict(zip(EEG_CHANNELS, values.tolist())),
                    "interpolated_channels": prep.channel_diagnostics.get("interpolated_channels", []),
                    "temporal_mean_uv2": _mean([values[EEG_CHANNELS.index(c)] for c in ("T7", "T8")]),
                    "central_mean_uv2": _mean([values[EEG_CHANNELS.index(c)] for c in ("C3", "Cz", "C4")]),
                    "interpretation": "Descriptive means of finite channel powers including labelled interpolations; not an EMG detector"})
        block, sf, ent = results["early_response"]
        if block is None:
            continue
        feature_diagnostics.append(_validate_feature_arrays({**sf, "permutation_entropy": ent}))
        try:
            for metrics in microstate_metrics(block, prep.sfreq, cfg.microstate_classes,
                                              cfg.microstate_random_state, cfg.microstate_max_samples):
                micros.append({**row, **metrics})
        except Exception as exc:
            report['warnings'].append(f'microstates event {wid}: {type(exc).__name__}: {exc}')
        try:
            for band, matrix in connectivity_by_band(block, prep.sfreq, cfg.connectivity_min_observations,
                                                      cfg.connectivity_segment_seconds, False, bands=cfg.connectivity_bands).items():
                conns[f"window_{wid}_early_{band}"] = matrix
                graph = graph_metrics(matrix, cfg.graph_density)
                networks.append({**row, "band": band,
                                 **{name: value.tolist() if isinstance(value, np.ndarray) else value
                                    for name, value in graph.items()}})
        except Exception as exc:
            report['warnings'].append(f'networks event {wid}: {type(exc).__name__}: {exc}')

    window_diagnostics = {name: [dict(event_index=item["record"]["event_index"],
                                      cluster_id=item["record"]["cluster_id"],
                                      **item["record"]["window_flags"][name])
                                for item in prep.event_windows]
                          for name in WINDOW_TYPES if name != "legacy_epochs"}
    window_diagnostics["legacy_epochs"] = prep.legacy_window_diagnostics
    report.update({"preprocessing_status": "success",
                   "isi_statistics": prep.isi_diagnostics,
                   "baseline_protection": {"protected_response_seconds": cfg.baseline_protected_response_seconds,
                       "policy": cfg.baseline_overlap_policy, "minimum_seconds": cfg.baseline_min_seconds, "interval_convention": "[start, stop)",
                       "primary_reason_priority": ["out_of_bounds", "invalid_samples_or_metrics", "artifact_peak_to_peak", "baseline_too_short", "baseline_previous_response_overlap"]},
                   "epoch_windows": {"baseline": cfg.baseline_window, **cfg.response_windows},
                   "window_quality": {name: quality_summary(items) for name, items in window_diagnostics.items()},
                   "window_diagnostics": window_diagnostics,
                   "quality_metadata_columns": [f"{prefix}_{suffix}" for prefix in ("baseline", "early", "sustained", "legacy")
                                                for suffix in ("invalid_reason", "invalid_reasons", "max_peak_to_peak_uv", "window_valid", "out_of_bounds", "overlaps_next_event")]
                       + ["baseline_previous_response_contaminated", "baseline_previous_response_overlaps",
                          "baseline_previous_event_indices", "baseline_previous_cluster_ids",
                          "baseline_available", "early_baseline_valid", "sustained_baseline_valid",
                          "baseline_original_start_s", "baseline_original_end_s", "baseline_trimmed",
                          "baseline_duration_seconds", "baseline_original_quality", "high_gamma_power_valid",
                          "baseline_high_gamma_power_valid", "early_high_gamma_power_valid", "sustained_high_gamma_power_valid",
                          "relative_power_normalization_low_hz", "relative_power_normalization_high_hz"],
                   "compatibility_counter_definitions": {
                       "n_rejected": "Rejected early_response windows only",
                       "n_epochs": "Accepted legacy tmin/tmax epochs only"},
                   "source_file": str(rec.path), "original_sfreq": rec.raw.info.get("sfreq"),
                   "raw_channel_names": rec.raw.ch_names, "raw_channel_types": rec.raw.get_channel_types(),
                   "target_sfreq": prep.sfreq, "n_raw_events": len(prep.event_records),
                   "n_analysis_events": len(prep.event_windows), "n_epochs": len(prep.epochs),
                   "n_rejected": len(prep.rejected), "rejection_reasons": prep.rejected,
                   "event_records": prep.event_records, "feature_diagnostics": feature_diagnostics,
                   "warnings": report["warnings"] + rec.warnings + prep.warnings, "pain_ratings_available": rec.pain_ratings is not None,
                   "events_type_known": False, "requested_reference": cfg.reference,
                   "applied_reference": 'average' if cfg.reference == 'average' else 'none',
                   "rejected_event_rows": getattr(rec, 'rejected_event_rows', []),
                   "feature_schema_version": '2.1',
                   "channel_diagnostics": prep.channel_diagnostics,
                   "ica_diagnostics": prep.ica_diagnostics,
                   "reference_scope": "selected 19 EEG channels only",
                   "versions": {"python": sys.version, "platform": platform.platform()}})
    report['quality_metadata_columns'].extend(sorted({key for row in features for key in row
        if key.startswith('tfr_') and not key.endswith('_db')}))
    report['tfr']['high_gamma_review_reference'] = 'high_gamma_review and ica_diagnostics in this report'
    export_recording(output_dir, channels, features, micros, networks, conns, report, connectivity_rows)
    return report


def process_dataset(input_root, output_root, config=None, experiment=None, subject=None):
    import json
    from collections import Counter
    import pandas as pd

    reports, subjects, failures = [], {}, []
    for exp, sub, run, directory in iter_recording_dirs(input_root, experiment, subject):
        report = process_recording(directory, Path(output_root) / exp / sub / run,
                                   exp, sub, run, config)
        reports.append(report)
        group = subjects.setdefault((exp, sub), {"success": 0, "failed": 0, "windows": []})
        if report.get("preprocessing_status") != "success":
            group["failed"] += 1
            failures.append(dict(experiment_id=exp, subject_id=sub, recording_id=run,
                                 errors=json.dumps(report.get("errors", []))))
        else:
            group["success"] += 1
            group["windows"].append(report["window_quality"])
    rows = []
    for (exp, sub), group in subjects.items():
        for name in WINDOW_TYPES:
            counts = [item[name] for item in group["windows"]]
            reasons = Counter()
            all_reasons = Counter()
            for item in counts:
                reasons.update(item["rejected_by_reason"])
                all_reasons.update(item.get("rejected_by_all_reasons", item["rejected_by_reason"]))
            summary = summary_from_counts(
                sum(i["planned"] for i in counts), sum(i["in_bounds"] for i in counts),
                sum(i["accepted"] for i in counts), dict(reasons),
                sum(i["peak_to_peak_percent_denominator"] for i in counts), dict(all_reasons))
            summary["rejected_by_all_reasons"] = json.dumps(summary["rejected_by_all_reasons"], sort_keys=True)
            summary["rejected_by_reason"] = json.dumps(summary["rejected_by_reason"], sort_keys=True)
            rows.append(dict(experiment_id=exp, subject_id=sub, window_type=name,
                             successful_recordings=group["success"], failed_recordings=group["failed"], **summary))
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    columns = ["experiment_id", "subject_id", "window_type", "successful_recordings", "failed_recordings",
               *summary_from_counts(0, 0, 0, {}, 0)]
    pd.DataFrame(rows, columns=columns).to_csv(output / "subject_window_quality.csv", index=False)
    pd.DataFrame(failures, columns=["experiment_id", "subject_id", "recording_id", "errors"]).to_csv(
        output / "preprocessing_failures.csv", index=False)
    return reports
