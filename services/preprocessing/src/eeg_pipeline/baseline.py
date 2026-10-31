"""Baseline transforms with explicit channel-wise and global aggregation."""

from __future__ import annotations

import numpy as np


def channelwise_changes(event_power, baseline_power):
    """Return mean-of-channel relative and dB changes, preserving invalid data."""
    event = np.asarray(event_power, dtype=float)
    baseline = np.asarray(baseline_power, dtype=float)
    valid = np.isfinite(event) & np.isfinite(baseline) & (baseline > 0)
    relative = np.full(np.broadcast_shapes(event.shape, baseline.shape), np.nan)
    db = np.full_like(relative, np.nan)
    relative[valid] = (event[valid] - baseline[valid]) / baseline[valid]
    positive = valid & (event > 0)
    db[positive] = 10 * np.log10(event[positive] / baseline[positive])
    return (float(np.nanmean(relative)) if np.any(np.isfinite(relative)) else np.nan,
            float(np.nanmean(db)) if np.any(np.isfinite(db)) else np.nan)


def global_changes(event_power, baseline_power):
    """Aggregate valid channels first, then calculate relative and dB change."""
    event = np.asarray(event_power, dtype=float)
    baseline = np.asarray(baseline_power, dtype=float)
    valid = np.isfinite(event) & np.isfinite(baseline) & (baseline > 0)
    if not np.any(valid):
        return np.nan, np.nan
    event_mean = float(np.nanmean(event[valid]))
    baseline_mean = float(np.nanmean(baseline[valid]))
    relative = (event_mean - baseline_mean) / baseline_mean if baseline_mean > 0 else np.nan
    db = 10 * np.log10(event_mean / baseline_mean) if event_mean > 0 else np.nan
    return relative, db
