"""Event timing in seconds relative to recording start; intervals are half-open."""
import numpy as np


def sample_boundary(time_s, sfreq):
    # First sample at or after the boundary (allow one floating-point ULP).
    return int(np.ceil(np.nextafter(float(time_s) * sfreq, -np.inf)))


def isi_statistics(records, time_key, threshold):
    ordered = sorted(records, key=lambda r: r[time_key])
    intervals = []
    for previous, current in zip(ordered, ordered[1:]):
        interval = float(current[time_key] - previous[time_key])
        intervals.append(dict(previous_event_index=previous["event_index"],
            event_index=current["event_index"], previous_cluster_id=previous["cluster_id"],
            cluster_id=current["cluster_id"], previous_time_s=previous[time_key],
            time_s=current[time_key], isi_seconds=interval, below_threshold=interval < threshold))
    values = [i["isi_seconds"] for i in intervals]
    short = sum(i["below_threshold"] for i in intervals)
    return dict(n_intervals=len(values), minimum_seconds=min(values) if values else None,
        median_seconds=float(np.median(values)) if values else None,
        maximum_seconds=max(values) if values else None, n_below_threshold=short,
        percent_below_threshold=100 * short / len(values) if values else None,
        warning_threshold_seconds=threshold, intervals=intervals)


def previous_response_overlaps(record, records, baseline_window, protected_seconds):
    event = record["cluster_event"]
    start, stop = (event + bound for bound in baseline_window)
    overlaps = []
    for previous in records:
        onset = previous["cluster_event"]
        if previous["cluster_id"] == record["cluster_id"] or onset >= event:
            continue
        left, right = max(start, onset), min(stop, onset + protected_seconds)
        if left < right:
            overlaps.append(dict(event_index=previous["event_index"], cluster_id=previous["cluster_id"],
                event_time_s=onset, protected_interval_s=[onset, onset + protected_seconds],
                intersection_s=[left, right]))
    return overlaps


def baseline_interval(record, records, cfg):
    """Keep a contiguous suffix of the requested baseline, never extend it."""
    event = record["cluster_event"]
    original_start, stop = (event + bound for bound in cfg.baseline_window)
    overlaps = previous_response_overlaps(record, records, cfg.baseline_window,
                                          cfg.baseline_protected_response_seconds)
    start = original_start
    if cfg.baseline_overlap_policy == "trim" and overlaps:
        start = min(stop, max(o["protected_interval_s"][1] for o in overlaps))
    duration = max(0.0, stop - start)
    return dict(original_start_s=original_start, original_end_s=stop,
                effective_start_s=start, effective_end_s=stop,
                trimmed=start > original_start, duration_seconds=duration,
                too_short=duration < cfg.baseline_min_seconds - 1e-12,
                previous_response_contaminated=bool(overlaps),
                previous_response_overlaps=overlaps)
