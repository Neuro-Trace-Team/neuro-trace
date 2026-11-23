"""Quality of complete analytical windows, measured in volts per channel."""
from collections import Counter
from numbers import Real

import numpy as np

WINDOW_TYPES = ("baseline", "early_response", "sustained_response", "legacy_epochs")


def validate_threshold(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(value) or value <= 0:
        raise ValueError("epoch_peak_to_peak_uv must be a positive finite number (not bool)")


def unavailable_quality(threshold_uv, reason):
    return dict(valid=False, reason=reason, peak_to_peak_uv=None,
                max_peak_to_peak_uv=None, exceeding_channels=None,
                threshold_uv=float(threshold_uv))


def processing_intervals(duration, annotations, guard):
    intervals = [(0., guard, 'filter_edge'), (duration-guard, duration, 'filter_edge')] if guard else []
    for a, b, kind in annotations:
        intervals.append((a-guard, b+guard, kind + '_annotation_filter_support'))
    return intervals


def evaluate_window_quality(block, threshold_uv, channel_names=None, *, interval=None, exclusions=()):
    """Reject iff any channel's full-window range exceeds the threshold.

    No centering, detrending, subwindowing or pooling across channels occurs.
    Uncomputable metrics are None, suitable for JSON null.
    """
    validate_threshold(threshold_uv)
    result = unavailable_quality(threshold_uv, "invalid_shape")
    try:
        block = np.asarray(block)
    except (ValueError, TypeError):
        return result
    if block.ndim != 2 or 0 in block.shape:
        return result
    names = list(channel_names) if channel_names is not None else list(range(block.shape[0]))
    if len(names) != block.shape[0]:
        return result
    if not np.issubdtype(block.dtype, np.number) or np.iscomplexobj(block):
        result["reason"] = "invalid_samples"
        return result
    if not np.isfinite(block).all():
        result["reason"] = "non_finite_samples"
        return result
    with np.errstate(over="ignore", invalid="ignore"):
        ranges = np.ptp(block.astype(float), axis=-1)
        ranges_uv = ranges * 1e6
    if not np.isfinite(ranges_uv).all():
        result["reason"] = "non_finite_metrics"
        return result
    exceeding = [name for name, value in zip(names, ranges) if value > threshold_uv * 1e-6]
    reasons = ['artifact_peak_to_peak'] if exceeding else []
    if interval is not None:
        a, b = interval
        reasons.extend(reason for left, right, reason in exclusions
                       if left < b and right > a and reason not in reasons)
    return dict(valid=not reasons, reason=reasons[0] if reasons else None, reasons=reasons,
                peak_to_peak_uv=ranges_uv.tolist(), max_peak_to_peak_uv=float(ranges_uv.max()),
                exceeding_channels=exceeding, threshold_uv=float(threshold_uv))


def quality_summary(items):
    reasons = dict(Counter(item["reason"] for item in items if not item["valid"]))
    all_reasons = Counter(reason for item in items
                          for reason in item.get("reasons", [item["reason"]] if item["reason"] else []))
    return summary_from_counts(len(items), sum(i["reason"] != "out_of_bounds" for i in items),
                               sum(i["valid"] for i in items), reasons,
                               sum(i["max_peak_to_peak_uv"] is not None for i in items),
                               dict(all_reasons))


def summary_from_counts(planned, in_bounds, accepted, reasons, computable, all_reasons=None):
    all_reasons = reasons if all_reasons is None else all_reasons
    rejected = planned - accepted
    return dict(planned=planned, in_bounds=in_bounds, accepted=accepted,
                rejected=rejected, rejected_by_reason=reasons, rejected_by_all_reasons=all_reasons,
                rejection_percent_denominator=planned,
                rejection_percent=100 * rejected / planned if planned else None,
                peak_to_peak_percent_denominator=computable,
                peak_to_peak_rejection_percent=(100 * all_reasons.get("artifact_peak_to_peak", 0) / computable
                                                if computable else None))
