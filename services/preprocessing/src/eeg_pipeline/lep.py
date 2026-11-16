"""Independent LEP measurement; fixed robust shape model, NOT Hu et al. (2010)."""
from dataclasses import asdict, dataclass
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from .event_timing import sample_boundary
from .window_quality import evaluate_window_quality

METHOD = 'fixed_gaussian_soft_l1_v2'
COMPONENTS = ('n1', 'n2_cz', 'p2_cz')


@dataclass(frozen=True)
class LEPConfig:
    enabled: bool = True
    epoch: tuple = (-0.5, 0.8)
    baseline: tuple = (-0.5, -0.05)
    n1_window: tuple = (0.10, 0.20)
    n2_window: tuple = (0.15, 0.28)
    p2_window: tuple = (0.30, 0.50)
    widths_s: tuple = (0.025, 0.035, 0.055)
    onset_policy: str = 'reject_ambiguous'
    stimulation_side: str | None = None
    stimulation_site: str | None = None
    allow_interpolated: bool = False
    min_amplitude_uv: float = 1.0
    min_snr: float = 2.0
    min_r2: float = 0.20
    min_component_gain: float = 0.30
    cz_reference_policy: str = 'exclude_interpolated'
    max_n1_overlap_fraction: float = 0.25
    max_amplitude_uv: float = 100.0
    max_nfev: int = 300

    def __post_init__(self):
        if type(self.enabled) is not bool or type(self.allow_interpolated) is not bool:
            raise ValueError('LEP enabled/allow_interpolated must be boolean')
        if self.stimulation_site is not None and not isinstance(self.stimulation_site, str):
            raise ValueError('LEP stimulation_site must be a string or None')
        if not np.isfinite(self.max_n1_overlap_fraction) or not 0 <= self.max_n1_overlap_fraction <= 1:
            raise ValueError('Invalid LEP N1 overlap threshold')
        if self.cz_reference_policy not in ('exclude_interpolated', 'retain_pipeline'):
            raise ValueError('Invalid LEP Cz reference policy')
        if not np.isfinite(self.min_component_gain) or not 0 <= self.min_component_gain < 1:
            raise ValueError('Invalid LEP component gain threshold')
        for name in ('epoch', 'baseline', 'n1_window', 'n2_window', 'p2_window'):
            w = getattr(self, name)
            if len(w) != 2 or not np.isfinite(w).all() or w[0] >= w[1]:
                raise ValueError(f'Invalid LEP {name}')
            if name != 'epoch' and not self.epoch[0] <= w[0] < w[1] <= self.epoch[1]:
                raise ValueError(f'LEP epoch must contain {name}')
        if self.baseline[1] > 0 or self.n1_window[0] < 0 or self.n2_window[0] < 0:
            raise ValueError('LEP baseline must precede stimulus; searches must follow it')
        if self.n2_window[1] >= self.p2_window[0]:
            raise ValueError('LEP N2 window must precede P2 window')
        if len(self.widths_s) != 3 or not np.isfinite(self.widths_s).all() or min(self.widths_s) <= 0:
            raise ValueError('Invalid LEP widths')
        if self.onset_policy not in ('reject_ambiguous', 'first_marker', 'original_marker'):
            raise ValueError('Invalid LEP onset policy')
        if self.stimulation_side not in (None, 'left', 'right'):
            raise ValueError('LEP side must be left/right or None')
        for value in (self.min_amplitude_uv, self.min_snr, self.max_amplitude_uv):
            if not np.isfinite(value) or value <= 0:
                raise ValueError('Invalid LEP threshold')
        if not 0 <= self.min_r2 < 1 or self.max_amplitude_uv <= self.min_amplitude_uv:
            raise ValueError('Invalid LEP fit thresholds')
        if type(self.max_nfev) is not int or self.max_nfev < 1:
            raise ValueError('Invalid LEP iteration limit')


def _empty(reason):
    return dict(amplitude_uv=np.nan, latency_ms=np.nan, gaussian_amplitude_uv=np.nan,
                gaussian_latency_ms=np.nan, valid=False, reason=reason,
                r2=np.nan, rmse_uv=np.nan, converged=False, boundary=False,
                optimizer_status=None, nfev=0, component_gain=np.nan,
                component_rmse_uv=np.nan, reduced_converged=False, overlap_fraction=np.nan)


def _mask(t, window):
    return (t >= window[0] - 1e-12) & (t < window[1] - 1e-12)


class FixedLEPEstimator:
    """No population fit or calibration data. All priors are explicit config.

    transform accepts one baseline-corrected trial in µV. Latencies are reported
    on the observed sample grid, even though optimization uses continuous shifts.
    """
    def __init__(self, config=None):
        self.config = config or LEPConfig()

    def save(self, path):
        Path(path).write_text(json.dumps(dict(method=METHOD, parameters=asdict(self.config)), indent=2))

    @classmethod
    def load(cls, path):
        payload = json.loads(Path(path).read_text())
        if payload['method'] != METHOD:
            raise ValueError('Unsupported LEP estimator version')
        return cls(LEPConfig(**payload['parameters']))

    def transform(self, times, signal_uv, noise_uv, components=('n2_cz', 'p2_cz')):
        cfg = self.config
        t = np.asarray(times, float)
        y = np.asarray(signal_uv, float)
        if (t.ndim != 1 or t.size < 4 or y.shape != t.shape or
                not np.isfinite(t).all() or not np.isfinite(y).all() or
                np.any(np.diff(t) <= 0) or
                not np.allclose(np.diff(t), np.median(np.diff(t)), rtol=1e-7, atol=1e-12) or
                not np.isfinite(noise_uv) or noise_uv < 0):
            return {c: _empty('invalid_samples') for c in components}
        requested = tuple(components)
        if requested not in (('n1',), ('n2_cz', 'p2_cz')):
            raise ValueError('LEP supports N1 montage or joint Cz N2/P2')
        windows = [getattr(cfg, c.replace('_cz', '') + '_window') for c in components]
        if any(_mask(t, w).sum() < 3 for w in windows):
            return {c: _empty('insufficient_samples') for c in components}
        signs = np.array([1 if c == 'p2_cz' else -1 for c in components])
        widths = np.array([cfg.widths_s[COMPONENTS.index(c)] for c in components])
        if requested == ('n1',):
            # In Tc-Fz the overlapping N2 contribution can be positive. Treat
            # it as a nuisance, never export it as a Cz measurement.
            components = ('n1', 'positive_n2_nuisance')
            windows.append(cfg.n2_window)
            signs = np.array([-1., 1.])
            widths = np.array([cfg.widths_s[0], cfg.widths_s[1]])
        if any(_mask(t, w).sum() < 3 for w in windows):
            return {c: _empty('insufficient_samples') for c in requested}
        # A fixed fitting support prevents selecting samples according to the trial.
        use = _mask(t, (max(0, windows[0][0] - 2*widths[0]),
                        min(cfg.epoch[1], windows[-1][1] + 2*widths[-1])))
        tx, obs = t[use], y[use]
        n = len(components)
        baseline_times = t[_mask(t, cfg.baseline)]
        if baseline_times.size < 3:
            return {c: _empty('insufficient_baseline_samples') for c in requested}
        def model(p, grid):
            basis = np.exp(-0.5*((grid[:, None]-p[n:])/widths)**2)
            baseline_basis = np.exp(-0.5*((baseline_times[:, None]-p[n:])/widths)**2).mean(axis=0)
            return (signs * p[:n] * (basis-baseline_basis)).sum(axis=1)
        lower = [0.] * n + [w[0] for w in windows]
        upper = [cfg.max_amplitude_uv] * n + [w[1] for w in windows]
        scale = max(float(noise_uv), 0.25)
        try:
            # Three predetermined starts limit local-minimum dependence without
            # using observed extrema as starting points.
            def optimize(active):
                active = np.asarray(active, dtype=int)
                if not active.size:
                    return None, np.zeros(2*n)
                free = np.r_[active, active+n]
                def expand(p):
                    full = np.r_[np.zeros(n), [np.mean(w) for w in windows]]
                    full[free] = p
                    return full
                fits = []
                for fraction in (0.25, 0.5, 0.75):
                    initial = np.array([min(5., cfg.max_amplitude_uv / 2)] * n +
                        [a + fraction*(b-a) for a, b in windows])
                    fits.append(least_squares(lambda p: model(expand(p), tx)-obs, initial[free],
                        bounds=(np.asarray(lower)[free], np.asarray(upper)[free]),
                        loss='soft_l1', f_scale=scale, max_nfev=cfg.max_nfev))
                fit = min(fits, key=lambda r: r.cost)
                return fit, expand(fit.x)
            fit, parameters = optimize(range(n))
            # Full and reduced models are separately optimized. Merely zeroing
            # one coefficient would overstate its incremental explanatory power.
            predicted = model(parameters, t)
            residual = obs - model(parameters, tx)
            rmse = float(np.sqrt(np.mean(residual**2)))
            total = float(np.sum((obs-obs.mean())**2))
            r2 = float(1-np.sum(residual**2)/total) if total > 0 else 0.
            result = {}
            dt = float(np.median(np.diff(t)))
            for i, (component, window) in enumerate(zip(components, windows)):
                if component not in requested:
                    continue
                indices = np.flatnonzero(_mask(t, window))
                k = indices[np.argmax(signs[i]*predicted[indices])]
                amplitude = float(predicted[k])
                boundary = bool(k in (indices[0], indices[-1]) or
                    min(parameters[n+i]-window[0], window[1]-parameters[n+i]) <= dt or
                    parameters[i] >= cfg.max_amplitude_uv - 1e-4)
                reduced_fit, reduced_parameters = optimize([j for j in range(n) if j != i])
                reduced_converged = reduced_fit is None or bool(reduced_fit.success)
                local = _mask(tx, (max(tx[0], window[0]-widths[i]), window[1]+widths[i]))
                reduced_residual = obs - model(reduced_parameters, tx)
                def robust_cost(x):
                    return float(np.sum(2*scale**2*(np.sqrt(1+(x/scale)**2)-1)))
                null_cost = robust_cost(reduced_residual[local])
                gain = 1-robust_cost(residual[local])/null_cost if null_cost > 1e-12 else 0.
                local_rmse = float(np.sqrt(np.mean(residual[local]**2)))
                overlap_fraction = 0.
                ambiguous_overlap = False
                if component == 'n1':
                    isolated = parameters.copy(); isolated[1] = 0.
                    own = float(model(isolated, t)[k])
                    overlap_fraction = abs(amplitude-own)/max(abs(own), 1e-12)
                    ambiguous_overlap = (overlap_fraction > cfg.max_n1_overlap_fraction or
                        (parameters[1] >= cfg.min_amplitude_uv and parameters[n+1] <= parameters[n]))
                reason = ('non_convergence' if not fit.success else
                          'not_detected' if signs[i]*amplitude < max(cfg.min_amplitude_uv, cfg.min_snr*noise_uv) else
                          'component_comparison_non_convergence' if not reduced_converged else
                          'ambiguous_n1_overlap' if ambiguous_overlap else
                          'boundary' if boundary else
                          'insufficient_component_evidence' if gain < cfg.min_component_gain else
                          'poor_fit' if r2 < cfg.min_r2 else None)
                result[component] = dict(
                    gaussian_amplitude_uv=float(signs[i]*parameters[i]) if reason is None else np.nan,
                    gaussian_latency_ms=float(parameters[n+i]*1000) if reason is None else np.nan,
                    amplitude_uv=amplitude if reason is None else np.nan,
                    latency_ms=float(t[k]*1000) if reason is None else np.nan,
                    valid=reason is None, reason=reason, r2=r2, rmse_uv=rmse,
                    converged=bool(fit.success), boundary=boundary,
                    optimizer_status=int(fit.status), nfev=int(fit.nfev),
                    component_gain=float(gain), component_rmse_uv=local_rmse,
                    reduced_converged=reduced_converged, overlap_fraction=float(overlap_fraction))
            return result
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            return {c: {**_empty('computation_failure'), 'error': str(exc)} for c in requested}


def window_peak(times, signal_uv, window, positive=False):
    indices = np.flatnonzero(_mask(times, window))
    if indices.size < 3 or not np.isfinite(signal_uv).all():
        return _empty('invalid_samples')
    k = indices[np.argmax(signal_uv[indices]) if positive else np.argmin(signal_uv[indices])]
    boundary = bool(k in (indices[0], indices[-1]))
    amplitude = float(signal_uv[k])
    reason = 'boundary' if boundary else 'wrong_polarity' if (amplitude <= 0 if positive else amplitude >= 0) else None
    return dict(amplitude_uv=amplitude if reason is None else np.nan,
                latency_ms=float(times[k]*1000) if reason is None else np.nan,
                valid=reason is None, reason=reason, boundary=boundary)


def n1_montage(data, names, side):
    channel = {'right': 'T7', 'left': 'T8'}.get(side)
    if channel is None:
        return None, None, 'missing_stimulation_side'
    if channel not in names or 'Fz' not in names:
        return None, channel, 'missing_n1_electrode'
    # (Tc - average) - (Fz - average) == Tc - Fz; no shared-data mutation.
    return data[names.index(channel)] - data[names.index('Fz')], channel, None


def _put(row, component, result, prefix='lep'):
    row.update({f'{prefix}_{component}_{k}': v for k, v in result.items() if not k.startswith('gaussian_')})
    if prefix == 'lep':
        for suffix in ('amplitude_uv', 'latency_ms'):
            row[f'lep_gaussian_{component}_{suffix}'] = result.get('gaussian_'+suffix, np.nan)


def _pair(row, prefix):
    valid = row[f'{prefix}_n2_cz_valid'] and row[f'{prefix}_p2_cz_valid']
    row[f'{prefix}_n2_p2_cz_valid'] = bool(valid)
    row[f'{prefix}_n2_p2_cz_reason'] = None if valid else ';'.join(
        f'{c}:{row[f"{prefix}_{c}_reason"]}' for c in ('n2_cz', 'p2_cz') if not row[f'{prefix}_{c}_valid'])
    row[f'{prefix}_n2_p2_cz_amplitude_uv'] = (row[f'{prefix}_p2_cz_amplitude_uv'] -
        row[f'{prefix}_n2_cz_amplitude_uv']) if valid else np.nan


def extract_lep(prep, pipeline_config, event_metadata=(), annotations=(), filter_guard_s=0., source_sfreq=None):
    """Return rows keyed by existing event_index, never remove spectral rows.

    annotations: bad intervals in seconds relative to recording start.
    filter_guard_s: support of already-applied continuous FIR; no new filter.
    """
    annotations = list(annotations) + [(a,b) for a,b,_ in prep.channel_diagnostics.get('source_artifact_intervals', [])]
    cfg = LEPConfig(**pipeline_config.lep)
    estimator = FixedLEPEstimator(cfg)
    records = prep.event_records
    rows = {}
    for item in prep.event_windows:
        record = item['record']
        members = sorted((r for r in records if r['cluster_id'] == record['cluster_id']), key=lambda r: r['event'])
        chosen = members[0] if cfg.onset_policy == 'first_marker' else record
        onset = chosen['event']
        metadata = event_metadata[chosen['event_index']] if chosen['event_index'] < len(event_metadata) else {}
        side = metadata.get('stimulation_side') or cfg.stimulation_side
        site = metadata.get('stimulation_site') or cfg.stimulation_site
        row = dict(lep_method=METHOD, lep_peak_method='window_extrema_v1', lep_onset_policy=cfg.onset_policy,
            lep_onset_s=onset, lep_source_event_index=chosen['event_index'],
            lep_source_marker=chosen.get('source_event', onset),
            lep_source_event_time_unit=chosen.get('event_time_unit', 'seconds'),
            lep_cluster_id=record['cluster_id'],
            lep_marker_indices=json.dumps([m['event_index'] for m in members]),
            lep_onset_verified=False, lep_sampling_interval_ms=1000/prep.sfreq,
            lep_resolution_floor_ms=max(1000/prep.sfreq, 1000/(source_sfreq or prep.sfreq)),
            lep_stimulation_side=side, lep_stimulation_site=site, lep_n1_reference='Fz',
            lep_cz_reference=pipeline_config.reference, lep_baseline_policy='reject_without_trim',
            lep_baseline_start_s=onset+cfg.baseline[0], lep_baseline_end_s=onset+cfg.baseline[1],
            lep_epoch_start_s=onset+cfg.epoch[0], lep_epoch_end_s=onset+cfg.epoch[1])
        reason = None
        if not cfg.enabled:
            reason = 'disabled'
        elif cfg.onset_policy == 'reject_ambiguous' and len(members) > 1:
            reason = 'ambiguous_cluster_onset'
        start, stop = [sample_boundary(onset+x, prep.sfreq) for x in cfg.epoch]
        if reason is None and (start < 0 or stop > prep.data.shape[1]):
            reason = 'out_of_bounds'
        left, right = onset+cfg.epoch[0], onset+cfg.epoch[1]
        if reason is None and (left < filter_guard_s or right > prep.data.shape[1]/prep.sfreq-filter_guard_s):
            reason = 'filter_edge'
        if reason is None and any(a < right+filter_guard_s and b > left-filter_guard_s for a, b in annotations):
            reason = 'bad_annotation_or_filter_support'
        # first_marker explicitly treats within-cluster markers as duplicates.
        # Other policies conservatively treat each other marker as a stimulus.
        others = [r for r in records if r['event_index'] != chosen['event_index'] and
                  not (cfg.onset_policy == 'first_marker' and r['cluster_id'] == chosen['cluster_id'])]
        protected = pipeline_config.baseline_protected_response_seconds
        baseline_left, baseline_right = onset+cfg.baseline[0], onset+cfg.baseline[1]
        previous = [r['event_index'] for r in others if r['event'] < onset and
                    r['event'] < baseline_right and r['event']+protected > baseline_left]
        following = [r['event_index'] for r in others if onset <= r['event'] < right]
        # A response interval expanded on both sides by the continuous filter
        # support can contaminate the epoch even when its marker lies outside it.
        filter_overlaps = [dict(event_index=r['event_index'], cluster_id=r['cluster_id'],
            source_response_interval_s=[r['event'], r['event']+protected],
            filtered_response_interval_s=[r['event']-filter_guard_s, r['event']+protected+filter_guard_s])
            for r in others if r['event']-filter_guard_s < right and
            r['event']+protected+filter_guard_s > left]
        row['lep_filter_overlap_events'] = json.dumps(filter_overlaps)
        row['lep_filter_guard_s'] = filter_guard_s
        row.update(lep_baseline_previous_markers=json.dumps(previous), lep_following_markers=json.dumps(following))
        if reason is None and previous:
            reason = 'baseline_previous_response_overlap'
        if reason is None and following:
            reason = 'next_stimulus_overlap'
        if reason is None and filter_overlaps:
            reason = 'adjacent_response_filter_overlap'
        block = prep.data[:, start:stop].copy() if reason is None else None
        if block is not None:
            quality = evaluate_window_quality(block, pipeline_config.epoch_peak_to_peak_uv, prep.channel_names)
            reason = quality['reason']
        row['lep_epoch_reason'] = reason
        row['lep_epoch_sample_start_s'] = start/prep.sfreq
        row['lep_epoch_sample_stop_s'] = stop/prep.sfreq
        for c in COMPONENTS:
            _put(row, c, _empty(reason or 'not_evaluated'))
            _put(row, c, _empty(reason or 'not_evaluated'), 'lep_peak')
        row['lep_n1_channel'] = {'right': 'T7', 'left': 'T8'}.get(side)
        bad = prep.channel_diagnostics.get('interpolated_channels', [])
        measured = [name for name in prep.channel_names if name not in bad and
                    name not in prep.channel_diagnostics.get('missing_n1_channels', [])]
        change_reference = bool(bad) and cfg.cz_reference_policy == 'exclude_interpolated'
        row['lep_cz_reference_policy'] = cfg.cz_reference_policy
        row['lep_cz_reference_channels'] = json.dumps(measured if change_reference else prep.channel_names)
        row['lep_cz_reference_interpolated_channels'] = json.dumps([] if change_reference else bad)
        row['lep_cz_reference_changed'] = change_reference
        if change_reference and pipeline_config.reference == 'average':
            row['lep_cz_reference'] = 'average_measured_channels'
        row['lep_cz_interpolated'] = 'Cz' in bad
        row['lep_n1_interpolated'] = row['lep_n1_channel'] in bad or 'Fz' in bad
        if reason is None:
            times = np.arange(start, stop)/prep.sfreq-onset
            baseline = _mask(times, cfg.baseline)
            row['lep_baseline_sample_count'] = int(baseline.sum())
            row['lep_baseline_sample_start_s'] = float(times[baseline][0]+onset) if baseline.any() else None
            row['lep_baseline_sample_stop_s'] = float(times[baseline][-1]+onset+1/prep.sfreq) if baseline.any() else None
            if baseline.sum() < 3:
                for c in COMPONENTS:
                    _put(row, c, _empty('insufficient_baseline_samples'))
                    _put(row, c, _empty('insufficient_baseline_samples'), 'lep_peak')
            else:
                n1, channel, n1reason = n1_montage(block, prep.channel_names, side)
                if channel in prep.channel_diagnostics.get('missing_n1_channels', []) or 'Fz' in prep.channel_diagnostics.get('missing_n1_channels', []):
                    n1reason = 'missing_n1_electrode'
                if n1reason is None and site != 'hand_dorsum':
                    n1reason = 'missing_or_unsupported_stimulation_site'
                if n1reason is None and row['lep_n1_interpolated'] and not cfg.allow_interpolated:
                    n1reason = 'interpolated_n1_montage'
                czreason = ('missing_cz' if 'Cz' not in prep.channel_names else
                    'unsupported_cz_reference' if pipeline_config.reference != 'average' else
                    'interpolated_cz' if row['lep_cz_interpolated'] and not cfg.allow_interpolated else None)
                cz = block[prep.channel_names.index('Cz')].copy() if 'Cz' in prep.channel_names else None
                if change_reference and czreason is None:
                    if len(measured) < 2:
                        czreason = 'insufficient_measured_reference_channels'
                    else:
                        cz -= block[[prep.channel_names.index(c) for c in measured]].mean(axis=0)
                for components, signal, channel_reason in (
                    (('n1',), n1, n1reason),
                    (('n2_cz', 'p2_cz'), cz, czreason)):
                    if channel_reason:
                        for c in components:
                            _put(row, c, _empty(channel_reason))
                            _put(row, c, _empty(channel_reason), 'lep_peak')
                        continue
                    uv = signal*1e6
                    offset = float(uv[baseline].mean())
                    uv = uv-offset
                    noise = float(np.std(uv[baseline], ddof=1))
                    estimates = estimator.transform(times, uv, noise, components)
                    for c in components:
                        _put(row, c, estimates[c])
                        row[f'lep_{c}_baseline_mean_uv'] = offset
                        row[f'lep_{c}_baseline_noise_uv'] = noise
                        _put(row, c, window_peak(times, uv, getattr(cfg, c.replace('_cz', '')+'_window'), c == 'p2_cz'), 'lep_peak')
                for prefix in ('lep', 'lep_peak'):
                    if row[f'{prefix}_n1_valid'] and row[f'{prefix}_n2_cz_valid'] and row[f'{prefix}_n1_latency_ms'] >= row[f'{prefix}_n2_cz_latency_ms']:
                        _put(row, 'n1', {**_empty('n1_not_before_n2'), 'converged': row.get(f'{prefix}_n1_converged', False)}, prefix)
        # Preserve legacy extrema and QC; expose the same fit's signed parameters separately.
        for c in COMPONENTS:
            for suffix in ('amplitude_uv', 'latency_ms', 'valid', 'reason'):
                row[f'lep_reconstruction_{c}_{suffix}'] = row[f'lep_{c}_{suffix}']
                row[f'lep_gaussian_{c}_{suffix}'] = row.get(
                    f'lep_gaussian_{c}_{suffix}' if suffix in ('amplitude_uv', 'latency_ms') else f'lep_{c}_{suffix}', np.nan)
        for prefix in ('lep', 'lep_peak', 'lep_gaussian', 'lep_reconstruction'):
            _pair(row, prefix)
        rows[record['event_index']] = row
    report = dict(method=METHOD, parameters=asdict(cfg), template_provenance='fixed analytical Gaussians; no training data',
        gaussian_definition='signed fitted heights and continuous centers; same fit and conservative legacy QC',
        amplitude_definition='signed extrema of summed reconstructed waveform on sample grid, baseline-relative uV',
        filtering='no additional filter; cleaned continuous analytical branch', filter_guard_seconds=filter_guard_s,
        component_evidence='local soft_l1 loss reduction versus independently refitted model without component; not a statistical p-value',
        reference_policy=cfg.cz_reference_policy,
        onset_warning='Marker identity is not hardware verification of laser onset; first_marker assumes cluster duplicates.',
        trials=[{k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in row.items()}
                for row in rows.values()],
        calibration='Protocol windows and widths must be fixed externally or selected within training folds only.',
        quality={c: dict(valid=sum(r[f'lep_{c}_valid'] for r in rows.values()),
            rejected_by_reason=dict(Counter(r[f'lep_{c}_reason'] for r in rows.values() if not r[f'lep_{c}_valid'])))
            for c in (*COMPONENTS, 'n2_p2_cz')})
    return rows, report


def continuous_filter_guard(sfreq, cfg):
    """Conservative support of cascaded existing zero-double FIR filters."""
    import mne
    from .preprocessing import transition_width, notch_frequencies
    kernel = mne.filter.create_filter(None, sfreq, cfg.highpass, cfg.lowpass,
        l_trans_bandwidth=min(cfg.highpass, 2.), h_trans_bandwidth=transition_width(cfg.lowpass),
        phase='zero-double', verbose='ERROR')
    guard = (len(kernel)-1)/sfreq
    if notch_frequencies(cfg, sfreq):
        # Existing notch uses 1 Hz transitions (trans_bandwidth / 2).
        guard += np.ceil(3.3*sfreq)/sfreq
    if cfg.target_sfreq and not np.isclose(cfg.target_sfreq, sfreq):
        from fractions import Fraction
        ratio = Fraction(cfg.target_sfreq/sfreq).limit_denominator(1000)
        guard += 10*max(ratio.numerator, ratio.denominator)/(sfreq*ratio.numerator)
    return float(guard)
