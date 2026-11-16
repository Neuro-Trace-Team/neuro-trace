"""Continuous extended Infomax, ICLabel decisions and review artifacts.

Classifier imports are deliberately lazy. All numerical signal values are volts.
"""
from __future__ import annotations

import csv
import json
import logging
import threading
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

CLASSES = ('brain', 'muscle artifact', 'eye blink', 'heart beat',
           'line noise', 'channel noise', 'other')
FIT_PARAMS = dict(extended=True, w_change=1e-12, n_small_angle=20, verbose=True)


class InfomaxTrace(logging.Filter):
    """Read full precision stopping evidence from MNE 1.13.2 log records.

    MNE sets n_iter_ to max_iter on the weight-change stopping path. The
    unformatted record retains the true step and change, unlike rendered text.
    Only this thread's iteration messages are consumed; no global logger level
    or handlers are modified. Missing evidence is a failure, never assumed success.
    """
    def __init__(self):
        super().__init__()
        self.thread = threading.get_ident()
        self.step = None
        self.change = None

    def filter(self, record):
        if record.thread == self.thread and str(record.msg).startswith('step %d - lrate'):
            self.step, _, self.change, _ = record.args
            return False
        return True


def classify(inst, ica):
    from mne_icalabel.iclabel import iclabel_label_components
    return iclabel_label_components(inst, ica, inplace=True, backend='onnx')


def component_decisions(probabilities, cfg):
    p = np.asarray(probabilities, dtype=float)
    if (p.ndim != 2 or p.shape[1] != len(CLASSES) or not np.isfinite(p).all()
            or np.any((p < 0) | (p > 1)) or not np.allclose(p.sum(axis=1), 1, atol=1e-5)):
        raise ValueError('ICLabel must return a finite normalized (components, 7) matrix')
    exclude = set(cfg.ica_exclude or cfg.extra.get('ica_exclude', ()))
    keep = set(cfg.ica_keep)
    if exclude & keep:
        raise ValueError('Conflicting ICA keep and exclude indices')
    if any(type(i) is not int or not 0 <= i < len(p) for i in exclude | keep):
        raise ValueError('Manual ICA index outside fitted decomposition')
    rows = []
    for i, probs in enumerate(p):
        label = CLASSES[int(probs.argmax())]
        confidence = float(probs.max())
        threshold = cfg.ica_artifact_thresholds.get(label)
        remove = threshold is not None and confidence >= threshold
        source = 'automatic' if remove else 'review'
        reason = f'{label} confidence >= {threshold}' if remove else 'unconfigured class or uncertain classification'
        if i in keep:
            remove, source, reason = False, 'manual_keep', 'explicit keep overrides automatic decision'
        elif i in exclude:
            remove, source, reason = True, 'manual_exclude', 'explicit exclusion for this decomposition'
        rows.append(dict(index=i, label=label, confidence=confidence,
                         probabilities=dict(zip(CLASSES, map(float, probs))),
                         remove=remove, source=source, reason=reason))
    return rows


def fit_samples(branch, cfg, report):
    """Use the exact same retained samples for rank, fit and classification."""
    import mne
    sf = branch.info['sfreq']
    values = branch.get_data(reject_by_annotation='NaN', verbose='ERROR')
    mask = np.isfinite(values).all(axis=0)
    rejected = []
    # Only prepared (filtered) branches carry this support; raw helper callers retain their contract.
    guard = getattr(branch, '_pipeline_filter_guard', 0.)
    if guard:
        from .preprocessing import annotation_intervals
        from .window_quality import processing_intervals
        times = np.arange(branch.n_times)/sf
        for a, b, reason in processing_intervals(branch.n_times/sf, annotation_intervals(branch) + getattr(branch, '_pipeline_source_artifacts', []), guard):
            mask[(times >= a) & (times < b)] = False
            rejected.append(dict(start_seconds=a, duration_seconds=b-a, reason=reason))
    # Annotation onsets are in Raw's time coordinate (including first_time).
    for annotation in branch.annotations:
        if annotation['description'].lower().startswith('bad'):
            rejected.append(dict(start_seconds=float(annotation['onset'] - branch.first_time),
                                 duration_seconds=float(annotation['duration']),
                                 reason=annotation['description']))
    width = max(1, round(cfg.ica_fit_window_seconds * sf))
    for start in range(0, branch.n_times, width):
        stop = min(start + width, branch.n_times)
        usable = values[:, start:stop][:, mask[start:stop]]
        if usable.size and np.max(np.ptp(usable, axis=1)) > cfg.ica_fit_peak_to_peak_uv * 1e-6:
            mask[start:stop] = False
            rejected.append(dict(start_seconds=start / sf, duration_seconds=(stop-start) / sf,
                                 reason='ica_fit_peak_to_peak'))
    report.update(available_samples=int(branch.n_times), available_seconds=float(branch.n_times / sf),
                  fit_samples=int(mask.sum()), fit_seconds=float(mask.sum() / sf),
                  rejected_fragments=rejected,
                  fit_sample_ranges=_ranges(mask),
                  fit_representation='retained samples concatenated; no resampling or decimation')
    if mask.sum() / sf < cfg.ica_min_fit_seconds:
        raise ValueError('Insufficient clean duration for ICA fit')
    retained = branch.get_data()[:, mask]
    # Concatenation is explicit: ICLabel receives exactly these samples, without
    # reintroducing BAD data (its Raw feature API does not reject annotations).
    training = mne.io.RawArray(retained, branch.info.copy(), verbose='ERROR')
    training._pipeline_spatial_signature = getattr(branch, "_pipeline_spatial_signature", None)
    return training


def _ranges(mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return [[int(a), int(b)] for a, b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0])]


def estimate_rank(training, n_bad, cfg, report):
    x = training.get_data()
    x -= x.mean(axis=1, keepdims=True)
    singular = np.linalg.svd(x, compute_uv=False)
    tolerance = float(singular[0] * cfg.ica_rank_rtol)
    rank = min(int(np.sum(singular > tolerance)), len(training.ch_names) - 1 - n_bad)
    report['rank'] = dict(method='centered SVD with relative singular-value tolerance and structural cap',
                          relative_tolerance=cfg.ica_rank_rtol, absolute_tolerance=tolerance,
                          singular_values=singular.tolist(), structural_cap=len(training.ch_names)-1-n_bad,
                          estimated=rank, n_components=rank)
    if rank < cfg.ica_min_rank:
        raise ValueError('Effective ICA rank is too small')
    condition = float(singular[0] / singular[rank-1])
    report['rank']['condition_number'] = condition
    if not np.isfinite(condition) or condition > cfg.ica_max_condition:
        raise ValueError('ICA retained subspace is numerically unstable')
    if training.n_times < cfg.ica_min_samples_per_component_squared * rank**2:
        raise ValueError('Insufficient ICA samples for effective rank')
    return rank


def validate_transfer(fitting, analytical):
    from mne._fiff.constants import FIFF
    if (getattr(fitting, '_pipeline_spatial_signature', None)
            != getattr(analytical, '_pipeline_spatial_signature', None)):
        raise ValueError('ICA channel order or interpolation space mismatch')
    if fitting.ch_names != analytical.ch_names:
        raise ValueError('ICA channel order mismatch')
    for inst in (fitting, analytical):
        if inst.info['custom_ref_applied'] != FIFF.FIFFV_MNE_CUSTOM_REF_ON:
            raise ValueError('ICA requires applied average reference metadata')
        if inst.info['bads'] or any(ch['unit'] != FIFF.FIFF_UNIT_V for ch in inst.info['chs']):
            raise ValueError('ICA requires interpolated EEG in volts')
        if np.max(np.abs(inst.get_data().mean(axis=0))) > 1e-12:
            raise ValueError('ICA requires numerical average reference')
    for a, b in zip(fitting.info['chs'], analytical.info['chs']):
        if not np.allclose(a['loc'], b['loc'], equal_nan=True) or a['coord_frame'] != b['coord_frame']:
            raise ValueError('ICA geometry mismatch')
    if fitting.info['sfreq'] != analytical.info['sfreq']:
        raise ValueError('ICA branch sampling mismatch')


def signal_metrics(data):
    return dict(rms_uv_per_channel=(np.sqrt(np.mean(data**2, axis=1))*1e6).tolist(),
                peak_uv_per_channel=(np.max(np.abs(data), axis=1)*1e6).tolist(),
                average_reference_max_abs_v=float(np.max(np.abs(data.mean(axis=0)))))


def clean_with_ica(working, analytical, original, bad_names, cfg, channel_report,
                   prepare_branch, diagnostic_dir=None):
    from .preprocessing import PreprocessingError
    report = dict(status='in_progress', stage='prepare', failure_reason=None,
                  requested={k: v for k, v in vars(cfg).items() if k.startswith('ica_')},
                  analytical_band=[analytical.info['highpass'], analytical.info['lowpass']],
                  channels=analytical.ch_names.copy(), units='V', reference='average',
                  interpolated_channels=list(bad_names), interpolation_method=channel_report['interpolation_method'],
                  versions={}, removed_count=0, removed_muscle_components=[], removed_muscle_count=0,
                  requested_analytical_band=[cfg.highpass, cfg.lowpass],
                  legacy_ica_exclude=list(cfg.extra.get('ica_exclude', ())))
    before = analytical.get_data()
    report["signal_before"] = signal_metrics(before)
    try:
        for package in ('mne', 'mne-icalabel', 'onnxruntime'):
            try:
                report['versions'][package] = version(package)
            except PackageNotFoundError:
                report['versions'][package] = None
        if cfg.reference != 'average':
            raise ValueError('ICLabel requires average reference')
        high = cfg.ica_lowpass
        report['ica_band'] = [cfg.ica_highpass, high]
        report['band_deviation'] = report['ica_band'] != [1., 100.]
        report['actual'] = dict(method=cfg.ica_method, fit_params=FIT_PARAMS,
                                random_state=cfg.ica_random_state, max_iter=cfg.ica_max_iter,
                                sfreq=working.info['sfreq'], backend='onnx CPU',
                                notch_hz=[])
        branch_cfg = replace(cfg, highpass=cfg.ica_highpass, lowpass=high)
        from .preprocessing import notch_frequencies
        report['actual']['notch_hz'] = notch_frequencies(branch_cfg, working.info['sfreq'])
        branch = prepare_branch(working, original, bad_names, branch_cfg)
        validate_transfer(branch, analytical)
        # Identical input channel ordering, bad list and spline operator in the
        # shared preparation function define the same interpolated space.
        report['interpolation_space_validated'] = True
        report['stage'] = 'fit_data'
        training = fit_samples(branch, cfg, report)
        report['stage'] = 'rank'
        rank = estimate_rank(training, len(bad_names), cfg, report)
        report['stage'] = 'fit'
        from mne.preprocessing import ICA
        ica = ICA(n_components=rank, method=cfg.ica_method, fit_params=FIT_PARAMS.copy(),
                  random_state=cfg.ica_random_state, max_iter=cfg.ica_max_iter, verbose='ERROR')
        from mne.utils import logger
        trace = InfomaxTrace()
        logger.addFilter(trace)
        try:
            ica.fit(training, reject_by_annotation=True, verbose='ERROR')
        finally:
            logger.removeFilter(trace)
        converged = (trace.step is not None and trace.step < cfg.ica_max_iter
                     and (trace.change < FIT_PARAMS['w_change'] or ica.n_iter_ < cfg.ica_max_iter))
        report['convergence'] = dict(iterations=int(trace.step or ica.n_iter_),
                                     mne_n_iter=int(ica.n_iter_), converged=bool(converged),
                                     final_weight_change=float(trace.change) if trace.change is not None else None,
                                     criterion='weight change < 1e-12 or MNE small-angle stopping rule')
        if not report['convergence']['converged']:
            raise ValueError('ICA did not converge before iteration limit')
        if (not np.isfinite(ica.unmixing_matrix_).all()
                or np.linalg.cond(ica.unmixing_matrix_) > cfg.ica_max_condition):
            raise ValueError('ICA unmixing matrix is numerically unstable')
        report['stage'] = 'classification'
        probabilities = classify(training, ica)
        if np.asarray(probabilities).shape != (rank, 7):
            raise ValueError('ICLabel component count mismatch')
        report['components'] = component_decisions(probabilities, cfg)
        excluded = [row['index'] for row in report['components'] if row['remove']]
        ica.exclude = excluded
        report['removed_count'] = len(excluded)
        report['stage'] = 'decisions'
        excessive = len(excluded) > rank * cfg.ica_max_excluded_fraction
        if excessive:
            report['review_required'] = True
            if cfg.ica_export_diagnostics:
                export_review(ica, training, analytical, analytical, report, cfg, diagnostic_dir)
            raise ValueError('Too many ICA exclusions; review required')
        report['stage'] = 'apply'
        validate_transfer(training, analytical)
        # Explicitly restore all PCA residuals. No exclusions means exact identity.
        cleaned = (ica.apply(analytical.copy(), n_pca_components=len(analytical.ch_names), verbose='ERROR')
                   if excluded else analytical.copy())
        after = cleaned.get_data()
        if (after.shape != before.shape or cleaned.first_samp != analytical.first_samp
                or not np.array_equal(cleaned.times, analytical.times) or not np.isfinite(after).all()
                or np.max(np.abs(after.mean(axis=0))) > 1e-12):
            raise ValueError('ICA reconstruction failed shape/time/finiteness/reference checks')
        report['signal_before'] = signal_metrics(before)
        report['signal_after'] = signal_metrics(after)
        report['relative_change_l2'] = float(np.linalg.norm(after-before) / max(np.linalg.norm(before), 1e-30))
        report['status'] = 'applied' if excluded else 'completed_no_exclusions'
        report['removed_muscle_components'] = [c['index'] for c in report['components']
            if c['remove'] and c['label'] == 'muscle artifact']
        report['removed_muscle_count'] = len(report['removed_muscle_components'])
        report['stage'] = 'export'
        if cfg.ica_export_diagnostics:
            export_review(ica, training, analytical, cleaned, report, cfg, diagnostic_dir)
        report['stage'] = 'complete'
        return after, report
    except Exception as exc:
        report.update(removed_muscle_components=[], removed_muscle_count=0)
        report.update(status='failed', failure_reason=f'{type(exc).__name__}: {exc}')
        if cfg.ica_failure_policy == 'skip':
            report['status'] = 'skipped_due_to_failure'
            return before, report
        raise PreprocessingError(f'ICA {report["stage"]} failed: {exc}', channel_report, report) from exc


def export_review(ica, training, before, after, report, cfg, directory):
    """Bounded headless figures and a decomposition reusable without fitting."""
    if directory is None:
        raise ValueError('ICA diagnostic export requires diagnostic_dir')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scipy.signal import welch
    directory = Path(directory) / 'ica'
    directory.mkdir(parents=True, exist_ok=True)
    ica.save(directory / 'decomposition-ica.fif', overwrite=True, verbose='ERROR')
    (directory / 'decisions.json').write_text(json.dumps(report, indent=2))
    rows = report['components']
    with (directory / 'components.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['index', 'label', 'confidence', 'remove', 'source', 'reason', *CLASSES])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: v for k, v in row.items() if k != 'probabilities'} | row['probabilities'])
    for start in range(0, ica.n_components_, 6):
        fig = ica.plot_components(picks=list(range(start, min(start+6, ica.n_components_))), show=False)
        fig.savefig(directory / f'topographies-{start:02d}.png', dpi=100)
        plt.close(fig)
    sf = training.info['sfreq']
    count = min(training.n_times, round(cfg.ica_export_seconds*sf))
    sources = ica.get_sources(training).get_data(start=0, stop=count)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    for i, source in enumerate(sources):
        axes[0].plot(np.arange(count)/sf, source/max(np.std(source), 1e-30)+i*5, linewidth=.4)
        f, p = welch(source, sf, nperseg=min(count, round(sf*2)))
        axes[1].semilogy(f, np.maximum(p, 1e-30), linewidth=.5, label=str(i))
    axes[0].set(xlabel='Retained training time (s)', ylabel='Standardized IC + offset')
    axes[1].set(xlabel='Hz', ylabel='Source PSD', xlim=(0, min(100, sf/2)))
    fig.tight_layout(); fig.savefig(directory / 'sources-and-spectra.png', dpi=100); plt.close(fig)
    count = min(before.n_times, round(cfg.ica_export_seconds*sf))
    pre, post = before.get_data(stop=count), after.get_data(stop=count)
    np.savez_compressed(directory / 'review-excerpt.npz', before=pre, after=post,
                        sources=sources, sfreq=sf, channels=before.ch_names)
    fig, axes = plt.subplots(3, 1, figsize=(12, 7))
    for axis, index in zip(axes, (0, 9, 18)):
        axis.plot(np.arange(count)/sf, pre[index]*1e6, label='before', linewidth=.6)
        axis.plot(np.arange(count)/sf, post[index]*1e6, label='after', linewidth=.6)
        axis.set(ylabel=f'{before.ch_names[index]} (µV)', xlabel='Recording time (s)')
        axis.legend()
    fig.tight_layout(); fig.savefig(directory / 'before-after.png', dpi=100); plt.close(fig)
    report['export_directory'] = str(directory)
