"""Single-trial total Morlet power. No ERP subtraction, fitting or decimation."""
from dataclasses import dataclass, field, asdict, replace
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import json

import mne
import numpy as np
from scipy.signal import fftconvolve
from scipy.ndimage import maximum_filter1d, minimum_filter1d
from .event_timing import baseline_interval, sample_boundary
from .lep import LEPConfig

METHOD = 'morlet_total_db_v2'


@dataclass
class TFRConfig:
    enabled: bool = True
    baseline: tuple | None = None
    frequencies: tuple = tuple(range(2, 31)) + tuple(range(60, 91, 2))
    n_cycles: tuple = (3.,)*6 + (5.,)*23 + (7.,)*16
    bands: dict = field(default_factory=lambda: {
        'high_gamma': (60., 90.), 'alpha': (8., 13.), 'beta': (13., 30.),
        'delta': (2., 4.), 'theta': (4., 8.)})
    windows: dict = field(default_factory=lambda: {
        'high_gamma': (.15, .35), 'alpha': (.3, 1.), 'beta': (.3, 1.),
        'delta': (.1, .8), 'theta': (.1, .8)})
    central_roi: tuple = ('C3', 'Cz', 'C4')
    allow_interpolated: bool = False
    min_baseline_cycles: float = 2.
    block_seconds: float = 30.
    save_matrices: bool = False
    plots: bool = False

    def __post_init__(self):
        if self.baseline is not None and (len(self.baseline) != 2 or
                not np.isfinite(self.baseline).all() or not self.baseline[0] < self.baseline[1] <= 0):
            raise ValueError('TFR baseline must be an increasing pre-stimulus interval')
        f, c = np.asarray(self.frequencies), np.asarray(self.n_cycles)
        if (f.ndim != 1 or not len(f) or f.shape != c.shape or
                not np.isfinite(f).all() or not np.isfinite(c).all() or
                np.any(f <= 0) or np.any(c <= 0) or np.any(np.diff(f) <= 0)):
            raise ValueError('TFR frequencies must increase; one positive n_cycles per frequency')
        if not self.bands or self.bands.keys() != self.windows.keys():
            raise ValueError('TFR bands and windows must have matching keys')
        for name, (lo, hi) in self.bands.items():
            if not name.isidentifier() or not np.isfinite([lo, hi]).all() or not 0 < lo < hi:
                raise ValueError('Invalid TFR band')
            if not np.any((f >= lo) & (f <= hi)):
                raise ValueError('TFR band has no configured frequencies')
            a, b = self.windows[name]
            if not np.isfinite([a, b]).all() or not 0 <= a < b:
                raise ValueError('Invalid TFR response window')
        if (isinstance(self.central_roi, str) or not self.central_roi or
                any(not isinstance(ch, str) or not ch.isidentifier() for ch in self.central_roi)):
            raise ValueError('TFR ROI must be a sequence of channel identifiers')
        canonical = {ch.lower(): ch for ch in ('C3', 'Cz', 'C4')}
        for ch in self.central_roi:
            if ch.lower() in ('central_roi', 'contralateral', 'ipsilateral'):
                raise ValueError('TFR ROI channel collides with an aggregate name')
            if ch.lower() in canonical and canonical[ch.lower()] != ch:
                raise ValueError('TFR channel names must not collide after lowercasing')
            canonical[ch.lower()] = ch
        if len({ch.lower() for ch in self.central_roi}) != len(self.central_roi):
            raise ValueError('TFR ROI must contain unique channel names')
        for v in (self.min_baseline_cycles, self.block_seconds):
            if not np.isfinite(v) or v <= 0:
                raise ValueError('TFR duration/cycle threshold must be positive')
        for v in (self.enabled, self.allow_interpolated, self.save_matrices, self.plots):
            if type(v) is not bool:
                raise ValueError('TFR switches must be boolean')


def power_blocks(data, wavelet, block_samples):
    """Yield disjoint cores, using real overlap of half the finite kernel.

    FFT padding is numerical only. Recording edges are masked downstream.
    Nonfinite inputs are zeroed only for convolution; their full support is invalid.
    """
    n = data.shape[-1]
    half = len(wavelet)//2
    for a in range(0, n, block_samples):
        b = min(n, a+block_samples)
        left, right = max(0, a-half), min(n, b+half)
        block = np.where(np.isfinite(data[:, left:right]), data[:, left:right], 0.)
        z = fftconvolve(block, wavelet[None, :], mode='same', axes=-1)
        yield a, b, np.abs(z[:, a-left:b-left])**2


def normalize_db(power, reference):
    result = np.full(power.shape, np.nan)
    good = np.isfinite(power) & (power > 0) & np.isfinite(reference) & (reference > 0)
    np.divide(power, reference, out=result, where=good)
    np.log10(result, out=result)
    return 10*result


def _runs(mask, times, sfreq):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return [[float(times[a]), float(times[b-1]+1/sfreq)]
            for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))]


def _code_runs(codes):
    """Lossless sparse RLE: local half-open sample indices, omitted values = 0."""
    if not len(codes):
        return []
    edges = np.r_[0, np.flatnonzero(np.diff(codes) != 0)+1, len(codes)]
    return [[int(a), int(b), int(codes[a])] for a,b in zip(edges[:-1],edges[1:]) if codes[a]]


def preprocessing_guard(sfreq, cfg):
    """FIR plus the existing scipy resample_poly default FIR's half support."""
    from .lep import continuous_filter_guard
    return continuous_filter_guard(sfreq, cfg)


def empty_tfr_row(cfg, reason='unavailable'):
    row = dict(tfr_method=METHOD, tfr_onset_s=np.nan, tfr_source_event_index=np.nan,
               tfr_cluster_id=np.nan, tfr_onset_policy=None, tfr_stimulation_side=None, tfr_stimulation_site=None)
    for band, w in cfg.windows.items():
        prefix = f'tfr_{band}_{w[0]*1000:g}_{w[1]*1000:g}ms'
        for ch in dict.fromkeys(['C3', 'Cz', 'C4', *cfg.central_roi]):
            key = prefix+'_'+ch.lower()
            row.update({key+'_db':np.nan, key+'_valid':False, key+'_reason':reason, key+'_interpolated':False})
        key = prefix+'_central_roi'
        row.update({key+'_db':np.nan, key+'_valid':False, key+'_reason':reason, key+'_channels':'[]', key+'_n_channels':0})
        if band in ('alpha', 'beta'):
            for side in ('contralateral', 'ipsilateral'):
                key = prefix+'_'+side
                row.update({key+'_db':np.nan, key+'_valid':False, key+'_reason':reason})
    return row


def extract_tfr(prep, pipeline_config, event_metadata=(), annotations=(),
                filter_guard_s=0., source_band=None, output_dir=None):
    annotations = list(annotations) + [(a,b) for a,b,_ in prep.channel_diagnostics.get('source_artifact_intervals', [])]
    cfg = TFRConfig(**pipeline_config.tfr)
    baseline_cfg = replace(pipeline_config, baseline_window=cfg.baseline) if cfg.baseline is not None else pipeline_config
    onset_cfg = LEPConfig(**pipeline_config.lep)
    fs = prep.sfreq
    freqs = np.asarray(cfg.frequencies, float)
    waves = mne.time_frequency.morlet(fs, freqs, n_cycles=cfg.n_cycles, zero_mean=True)
    halves = np.array([len(w)//2 for w in waves])
    sigma = np.asarray(cfg.n_cycles)/(2*np.pi*freqs)
    names = list(dict.fromkeys(['C3', 'Cz', 'C4', *cfg.central_roi]))
    present = [n for n in names if n in prep.channel_names]
    data = prep.data[[prep.channel_names.index(n) for n in present]]
    n = data.shape[-1]
    times = np.arange(n)/fs
    low, high = source_band or (pipeline_config.highpass, pipeline_config.lowpass)
    supported = (freqs >= max(low, pipeline_config.highpass)) & (freqs <= min(high, pipeline_config.lowpass)) & (freqs < fs/2)
    report = dict(method=METHOD, mne_version=mne.__version__, parameters=asdict(cfg),
        onset_policy=onset_cfg.onset_policy, filter_guard_seconds=filter_guard_s,
        normalization='10 log10(power / arithmetic temporal baseline power), per trial/channel/frequency; no epsilon',
        aggregation='arithmetic mean dB over time, then frequencies, then channels; strict complete ROI',
        power_type='single-trial total; no evoked subtraction; no ITPC',
        interpolation_policy='include_labelled' if cfg.allow_interpolated else 'reject',
        quality_codes={'1': 'missing_context_or_filter_edge', '2': 'nonfinite_support',
                       '4': 'artifact_peak_to_peak_support', '8': 'bad_annotation_filter_support',
                       '16': 'other_stimulus_support', '32': 'interpolated_channel',
                       '64': 'unsupported_frequency', '128': 'invalid_baseline',
                       '256': 'ambiguous_cluster_onset', '512': 'invalid_response_power'},
        resolution=[dict(frequency_hz=float(f), n_cycles=float(c), support_s=len(w)/fs,
                         half_support_s=int(h)/fs, envelope_fwhm_s=float(2*np.sqrt(2*np.log(2))*s),
                         power_fwhm_s=float(2*np.sqrt(np.log(2))*s),
                         envelope_frequency_fwhm_hz=float(np.sqrt(2*np.log(2))/(np.pi*s)),
                         supported=bool(ok)) for f,c,w,h,s,ok in zip(freqs,cfg.n_cycles,waves,halves,sigma,supported)],
        trials=[], quality={}, muscle_diagnostics=prep.ica_diagnostics,
        temporary_storage_bytes=int(len(present)*len(freqs)*n*9),
        warnings=['Dense grids do not improve wavelet resolution; filter headers do not prove acquisition bandwidth.',
                  'Positive high gamma is not evidence of cortical origin; low-frequency power is not N2/P2 amplitude.'])
    if not cfg.enabled or not prep.event_windows:
        return {}, report
    nominal = baseline_cfg.baseline_window
    impossible = nominal[0] + 2*halves/fs + filter_guard_s >= 0
    report['baseline_preflight'] = dict(baseline=list(nominal),
        incompatible_frequencies_hz=freqs[impossible].tolist(),
        reason='baseline_filter_support_overlap' if impossible.all() else None)
    if impossible.all():
        rows = {}
        for item in prep.event_windows:
            rec = item['record']
            members = sorted([r for r in prep.event_records if r['cluster_id'] == rec['cluster_id']], key=lambda r:r['event'])
            chosen = members[0] if onset_cfg.onset_policy == 'first_marker' else rec
            metadata = event_metadata[chosen['event_index']] if chosen['event_index'] < len(event_metadata) else {}
            reason = ('ambiguous_cluster_onset' if onset_cfg.onset_policy == 'reject_ambiguous' and len(members)>1
                      else 'baseline_filter_support_overlap')
            row = empty_tfr_row(cfg, reason)
            row.update(tfr_method=METHOD, tfr_onset_s=chosen['event'], tfr_source_event_index=chosen['event_index'],
                tfr_cluster_id=rec['cluster_id'], tfr_onset_policy=onset_cfg.onset_policy,
                tfr_stimulation_side=metadata.get('stimulation_side') or onset_cfg.stimulation_side,
                tfr_stimulation_site=metadata.get('stimulation_site') or onset_cfg.stimulation_site)
            rows[rec['event_index']] = row
            report['trials'].append(dict(event_index=rec['event_index'], reason=reason, results=row))
        report['temporary_storage_bytes'] = 0
        report['quality'] = {k: dict(valid=0, rejected=len(rows), reasons=dict(Counter(r[k[:-6]+'_reason'] for r in rows.values())))
                             for k in row if k.endswith('_valid')}
        return rows, report
    rows = {}
    with TemporaryDirectory(prefix='eeg-tfr-') as tmp:
        shape = (len(present), len(freqs), n)
        power = (np.memmap(Path(tmp)/'power', dtype='float64', mode='w+', shape=shape)
                 if present else np.empty(shape, dtype='float64'))
        quality = (np.memmap(Path(tmp)/'quality', dtype='uint8', mode='w+', shape=shape)
                   if present else np.empty(shape, dtype='uint8'))
        for fi, (wave, half) in enumerate(zip(waves, halves)):
            radius = int(half)
            guard = radius + int(np.ceil(filter_guard_s*fs))
            for ci, signal in enumerate(data):
                finite = np.isfinite(signal)
                safe = np.where(finite, signal, 0.)
                q = np.zeros(n, np.uint8)
                q[(times < guard/fs) | (times >= (n-guard)/fs)] |= 1
                q[maximum_filter1d((~finite).astype(int), 2*radius+1, mode='constant') > 0] |= 2
                span = maximum_filter1d(safe, 2*radius+1, mode='nearest') - minimum_filter1d(safe, 2*radius+1, mode='nearest')
                q[span > pipeline_config.epoch_peak_to_peak_uv*1e-6] |= 4
                for a,b in annotations:
                    q[(times+guard/fs >= a) & (times-guard/fs < b)] |= 8
                quality[ci,fi] = q
            if present:
                for a,b,p in power_blocks(data, wave, max(1, int(cfg.block_seconds*fs))):
                    power[:,fi,a:b] = p
        # Each core coefficient is computed once and reused for every trial.
        for item in prep.event_windows:
            rec = item['record']
            members = sorted([r for r in prep.event_records if r['cluster_id'] == rec['cluster_id']], key=lambda r:r['event'])
            chosen = members[0] if onset_cfg.onset_policy == 'first_marker' else rec
            onset = chosen['event']
            others = [r for r in prep.event_records if r['event_index'] != chosen['event_index'] and
                      not (onset_cfg.onset_policy == 'first_marker' and r['cluster_id'] == chosen['cluster_id'])]
            # Reuse trim/reject policy but explicitly anchor it to TFR's chosen onset.
            anchored = [{**r, 'cluster_event': r['event']} for r in others]
            timing = baseline_interval({**chosen, 'cluster_event': onset}, anchored, baseline_cfg)
            a,b = timing['effective_start_s'], timing['effective_end_s']
            start = max(0, sample_boundary(min(a, onset), fs))
            stop = min(n, sample_boundary(onset+max(w[1] for w in cfg.windows.values()), fs))
            ix = np.arange(start, max(start,stop))
            t = times[ix]
            db = np.full((len(present),len(freqs),len(ix)), np.nan)
            baseline_details = []
            coefficient_quality = quality[:,:,ix].astype(np.uint16)
            interpolated = prep.channel_diagnostics.get('interpolated_channels', [])
            global_reason = ('ambiguous_cluster_onset' if onset_cfg.onset_policy == 'reject_ambiguous' and len(members)>1 else None)
            row = dict(tfr_method=METHOD, tfr_onset_s=onset, tfr_source_event_index=chosen['event_index'],
                       tfr_cluster_id=rec['cluster_id'], tfr_onset_policy=onset_cfg.onset_policy)
            metadata = event_metadata[chosen['event_index']] if chosen['event_index'] < len(event_metadata) else {}
            side = metadata.get('stimulation_side') or onset_cfg.stimulation_side
            row['tfr_stimulation_side'] = side
            site = metadata.get('stimulation_site') or onset_cfg.stimulation_site
            row['tfr_stimulation_site'] = site
            band_reasons = {}
            for fi,(f,half) in enumerate(zip(freqs,halves)):
                h = half/fs
                base = (t-h >= a) & (t+h < min(b,onset))
                # The coefficient uses already-filtered samples: include their
                # acausal support when protecting the current and other stimuli.
                composite_h = h + filter_guard_s
                current_safe = t+composite_h < onset
                base &= current_safe
                response_safe = np.ones(len(t), bool)
                for r in others:
                    left, right = r['event'], r['event']+pipeline_config.baseline_protected_response_seconds
                    overlap = (t+composite_h >= left) & (t-composite_h < right)
                    base &= ~overlap
                    response_safe &= ~overlap
                for ci,ch in enumerate(present):
                    valid = quality[ci,fi,ix] == 0
                    use = base & valid
                    duration = use.sum()/fs
                    reason = (global_reason or ('unsupported_frequency' if not supported[fi] else None)
                        or ('baseline_previous_response_overlap' if timing['previous_response_contaminated'] and pipeline_config.baseline_overlap_policy == 'reject' else None)
                        or ('baseline_filter_support_overlap' if filter_guard_s > 0 and
                            np.any((t-h >= a) & (t+h < min(b,onset))) and not np.any(base) else None)
                        or ('baseline_too_short' if timing['too_short'] or duration < cfg.min_baseline_cycles/f else None))
                    p = power[ci,fi,ix]
                    reference = float(np.mean(p[use])) if use.any() else np.nan
                    if reason is None and (not np.isfinite(reference) or reference <= 0):
                        reason = 'invalid_baseline_power'
                    baseline_details.append(dict(channel=ch, frequency_hz=float(f), effective_seconds=duration,
                        used_intervals_s=_runs(use,t,fs), reason=reason, power=reference if np.isfinite(reference) else None))
                    band_reasons[ci,fi] = reason
                    codes = coefficient_quality[ci,fi]
                    codes[~response_safe] |= 16
                    if ch in interpolated and not cfg.allow_interpolated: codes[:] |= 32
                    if not supported[fi]: codes[:] |= 64
                    if reason is not None: codes[:] |= 128
                    if global_reason: codes[:] |= 256
                    codes[~np.isfinite(p) | (p <= 0)] |= 512
                    if reason is None:
                        db[ci,fi] = normalize_db(p,reference)
                        codes[~np.isfinite(db[ci,fi])] |= 512
                        db[ci,fi,codes != 0] = np.nan
            for band, bounds in cfg.bands.items():
                lo,hi = bounds
                w = cfg.windows[band]
                prefix = f'tfr_{band}_{w[0]*1000:g}_{w[1]*1000:g}ms'
                fi = np.flatnonzero((freqs >= lo) & (freqs <= hi))
                ti = np.flatnonzero((t-onset >= w[0]-1e-12) & (t-onset < w[1]-1e-12))
                band_ok = lo >= max(low,pipeline_config.highpass) and hi <= min(high,pipeline_config.lowpass) and hi < fs/2
                for ch in names:
                    reason = global_reason
                    value = np.nan
                    if reason is None:
                        if not band_ok: reason = 'unsupported_band'
                        elif ch not in present: reason = 'missing_channel'
                        elif ch in interpolated and not cfg.allow_interpolated: reason = 'interpolated_channel'
                        elif not len(ti) or onset+w[0] < 0 or onset+w[1] > n/fs: reason = 'missing_response_context'
                        else:
                            ci = present.index(ch)
                            reason = next((band_reasons[ci,f] for f in fi if band_reasons[ci,f]),None)
                            values = db[ci][np.ix_(fi,ti)]
                            if reason is None and not np.isfinite(values).all():
                                codes = np.bitwise_or.reduce(quality[ci][np.ix_(fi,ix[ti])].ravel(),initial=0)
                                reason = 'response_support_invalid_' + str(int(codes)) if codes else 'other_stimulus_or_zero_response_power'
                            if reason is None: value = float(values.mean(axis=1).mean())
                    key = prefix+'_'+ch.lower()
                    row.update({key+'_db':value,key+'_valid':reason is None,key+'_reason':reason,key+'_interpolated':ch in interpolated})
                used = [ch for ch in cfg.central_roi if row[prefix+'_'+ch.lower()+'_valid']]
                key = prefix+'_central_roi'
                ok = len(used) == len(cfg.central_roi)
                row.update({key+'_db':float(np.mean([row[prefix+'_'+ch.lower()+'_db'] for ch in used])) if ok else np.nan,
                    key+'_valid':ok,key+'_reason':None if ok else 'incomplete_roi',
                    key+'_channels':json.dumps(used),key+'_n_channels':len(used)})
                if band in ('alpha','beta'):
                    for lateral, mapping in [('contralateral',{'left':'C4','right':'C3'}),('ipsilateral',{'left':'C3','right':'C4'})]:
                        lateral_reason = ('unsupported_stimulation_site' if site is not None and
                            site not in ('hand', 'hand_dorsum', 'hand_palm', 'palm') else 'missing_stimulation_side')
                        ch = mapping.get(side) if lateral_reason != 'unsupported_stimulation_site' else None
                        for suffix in ('db','valid','reason'):
                            row[prefix+'_'+lateral+'_'+suffix] = row[prefix+'_'+ch.lower()+'_'+suffix] if ch else {'db':np.nan,'valid':False,'reason':lateral_reason}[suffix]
            trial = dict(event_index=rec['event_index'], cluster_id=rec['cluster_id'], onset_s=onset,
                         baseline=timing, baseline_by_frequency_channel=baseline_details,
                         quality_masks=dict(encoding='sparse_rle_start_stop_code; half-open; omitted=0',
                             sample_start=int(start), sample_count=len(ix), sfreq_hz=fs,
                             time_origin='recording_start', channels=present, frequencies_hz=freqs.tolist(),
                             coefficient_quality=[[_code_runs(c) for c in channel] for channel in coefficient_quality]),
                         epoch_support_invalid_counts={str(k):int(np.sum(quality[:,:,ix] & k != 0)) for k in (1,2,4,8)},
                         results={k:(None if isinstance(v,float) and not np.isfinite(v) else v) for k,v in row.items()})
            report['trials'].append(trial)
            rows[rec['event_index']] = row
            if output_dir and (cfg.save_matrices or cfg.plots):
                dest = Path(output_dir)/'tfr'; dest.mkdir(parents=True,exist_ok=True)
                if cfg.save_matrices:
                    np.savez_compressed(dest/f'event_{rec["event_index"]}.npz', db=db, times_s=t-onset,
                        frequencies_hz=freqs, channels=np.array(present), valid=np.isfinite(db),
                        support_quality=quality[:,:,ix], coefficient_quality=coefficient_quality,
                        interpolated=np.array([ch in interpolated for ch in present]),
                        event_index=rec['event_index'], cluster_id=rec['cluster_id'])
                if cfg.plots: plot_trial(dest/f'event_{rec["event_index"]}.png',db,t-onset,freqs,present,cfg)
        del power, quality
    for key in next(iter(rows.values()), {}):
        if key.endswith('_valid'):
            report['quality'][key] = dict(valid=sum(r[key] for r in rows.values()),
                rejected=len(rows)-sum(r[key] for r in rows.values()),
                reasons=dict(Counter(r[key[:-6]+'_reason'] for r in rows.values() if not r[key])))
    return rows,report


def plot_trial(path, db, times, freqs, names, cfg):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    if 'Cz' not in names or not len(times): return
    z = db[names.index('Cz')]
    fig, (ax,curve) = plt.subplots(2,1,figsize=(10,7),sharex=True)
    cmap = plt.get_cmap('RdBu_r').with_extremes(bad='0.7')
    limit = max(1.,float(np.nanpercentile(np.abs(z),95))) if np.isfinite(z).any() else 1.
    # Separate grid strips so the unmeasured 30–60 Hz gap is not painted.
    for ids in np.split(np.arange(len(freqs)),np.flatnonzero(np.diff(freqs)>3)+1):
        artist=ax.pcolormesh(times,freqs[ids],np.ma.masked_invalid(z[ids]),shading='nearest',cmap=cmap,vmin=-limit,vmax=limit)
    fig.colorbar(artist,ax=ax,label='dB')
    for band,(lo,hi) in cfg.bands.items():
        a,b=cfg.windows[band]; ax.add_patch(Rectangle((a,lo),b-a,hi-lo,fill=False,color='black'))
        selected=z[(freqs>=lo)&(freqs<=hi)]
        curve.plot(times,np.mean(selected,axis=0),label=band)
    ax.set(ylabel='Hz',title='Cz: single-trial total power; grey = invalid; no significance test')
    curve.axhline(0,color='black',lw=.5); curve.legend(); curve.set(xlabel='Seconds from selected onset',ylabel='Mean dB')
    fig.tight_layout(); fig.savefig(path); plt.close(fig)
