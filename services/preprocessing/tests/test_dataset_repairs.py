import json
from dataclasses import replace

import mne
import numpy as np
import pytest

from eeg_pipeline.config import EEG_CHANNELS, PipelineConfig
from eeg_pipeline.data_loader import load_recording
from eeg_pipeline.event_input import read_csv_events
from eeg_pipeline.lep import continuous_filter_guard
from eeg_pipeline.preprocessing import preprocess_raw
from eeg_pipeline.tfr import extract_tfr


def raw_signal(seconds=60, sfreq=256):
    t = np.arange(seconds*sfreq)/sfreq
    x = np.array([5e-6*np.sin(2*np.pi*10*t+i/10) + 2e-6*np.sin(2*np.pi*70*t+i/5)
                  for i in range(19)])
    return mne.io.RawArray(x, mne.create_info(EEG_CHANNELS, sfreq, 'eeg'), verbose='ERROR')


def test_csv_bids_join_filters_technical_markers_and_preserves_identity(tmp_path):
    run = tmp_path/'experiment_02'/'sub-001'/'ses-1_task-test_run-01'
    run.mkdir(parents=True)
    (run/'events.csv').write_text('onset\n0\n10\n20\n30\n')
    original=tmp_path/'_original_bids'/'ds-test'/'sub-001'/'ses-1'/'eeg'
    original.mkdir(parents=True)
    (original/'sub-001_ses-1_task-test_events.tsv').write_text(
        'onset\tvalue\n0\tboundary\n10\t32\n20\t64\n30\t0, Impedance\n')
    events, meta, rejected, boundaries, source = read_csv_events(run)
    assert events == [10,20]
    assert [m['source_event_index'] for m in meta] == [1,2]
    assert [m['source_csv_row'] for m in meta] == [3,4]
    assert boundaries == [0] and len(rejected)==2
    assert source.endswith('.tsv')
    (run/'events.csv').write_text('onset\n0\n11\n20\n30\n')
    with pytest.raises(ValueError,match='unsafe event join'):
        read_csv_events(run)


def test_json_still_has_priority_over_csv(monkeypatch,tmp_path):
    raw=raw_signal()
    monkeypatch.setattr(mne.io,'read_raw_bdf',lambda *a,**k:raw)
    (tmp_path/'raw_eeg.bdf').touch()
    (tmp_path/'timestamps.json').write_text('[10000]')
    (tmp_path/'events.csv').write_text('onset,value\n20,32\n')
    assert load_recording(tmp_path).events_seconds == [10]


def test_onset_only_csv_reports_missing_marker_semantics(monkeypatch,tmp_path):
    monkeypatch.setattr(mne.io,'read_raw_bdf',lambda *a,**k:raw_signal())
    (tmp_path/'raw_eeg.bdf').touch()
    (tmp_path/'events.csv').write_text('onset\n20\n')
    rec=load_recording(tmp_path)
    assert rec.events_seconds == [20]
    assert any('Event types unavailable' in w for w in rec.warnings)


def test_csv_boundary_is_an_edge_annotation(monkeypatch,tmp_path):
    raw=raw_signal()
    monkeypatch.setattr(mne.io,'read_raw_bdf',lambda *a,**k:raw)
    (tmp_path/'raw_eeg.bdf').touch()
    (tmp_path/'events.csv').write_text('onset,value\n20,boundary\n30,S 77\n')
    result=load_recording(tmp_path)
    assert result.events_seconds == [30]
    assert 'EDGE recording_boundary' in result.raw.annotations.description


def test_biosemi_only_uses_documented_laser_marker(tmp_path):
    run=tmp_path/'task-26ByBiosemi_run-01'
    run.mkdir()
    (run/'events.csv').write_text('onset,value\n10,condition 64\n10.01,condition 54\n')
    events,meta,rejected,_,_=read_csv_events(run)
    assert events == [10.01] and len(rejected)==1
    assert meta[0]['source_event_index']==1


def test_missing_typed_marker_is_not_invented_as_stimulus(tmp_path):
    (tmp_path/'events.csv').write_text('onset,value\n10,\n')
    with pytest.raises(ValueError,match='Missing event type'):
        read_csv_events(tmp_path)


def test_repaired_blink_not_permanently_rejected_but_gross_corruption_is(monkeypatch):
    raw=raw_signal()
    clean=raw.get_data().copy()
    raw._data[0,20*256:20*256+30] += 400e-6
    def cleaned(*args,**kwargs):
        return clean, {'status':'applied','components':[]}
    monkeypatch.setattr('eeg_pipeline.ica.clean_with_ica',cleaned)
    cfg=PipelineConfig()
    prep=preprocess_raw(raw,cfg,[20.])
    assert prep.event_windows[0]['windows']['early_response']['valid']
    old=preprocess_raw(raw,replace(cfg,source_artifact_peak_to_peak_uv=150),[20.])
    assert 'source_artifact_annotation_filter_support' in old.event_windows[0]['windows']['early_response']['reasons']
    raw._data[0,20*256:20*256+30] += 3000e-6
    gross=preprocess_raw(raw,cfg,[20.])
    assert not gross.event_windows[0]['windows']['early_response']['valid']


def test_residual_artifact_and_next_stimulus_are_still_rejected():
    raw=raw_signal()
    # A residual oscillation that no ICA repairs must still fail 150 uV QC.
    raw._data[0,20*256:21*256] += 200e-6*np.sin(2*np.pi*10*np.arange(256)/256)
    prep=preprocess_raw(raw,PipelineConfig(enable_ica=False,event_mode='raw_events'),[20.,40.,40.7])
    assert 'artifact_peak_to_peak' in prep.event_windows[0]['windows']['early_response']['reasons']
    assert 'next_stimulus_overlap' in prep.event_windows[1]['windows']['early_response']['reasons']


def test_filter_support_tracks_phase_and_tfr_is_computable():
    cfg=PipelineConfig(enable_ica=False)
    guard=continuous_filter_guard(256,cfg)
    double=continuous_filter_guard(256,replace(cfg,filter_phase='zero-double'))
    assert double == pytest.approx(2*guard)
    prep=preprocess_raw(raw_signal(),cfg,[25.])
    rows,report=extract_tfr(prep,cfg,filter_guard_s=guard)
    assert report['baseline_preflight']['reason'] is None
    assert rows[0]['tfr_high_gamma_150_350ms_cz_valid']
    assert np.isfinite(rows[0]['tfr_high_gamma_150_350ms_cz_db'])


def test_short_connectivity_is_explicitly_unavailable():
    from eeg_pipeline.connectivity import connectivity_pair_rows
    rows=connectivity_pair_rows(raw_signal(1).get_data(),256,0,0,'early')
    assert all(r['dwpli_invalid_reason']=='insufficient_observations' for r in rows)
    assert all(not r['dwpli_valid'] and np.isnan(r['dwpli']) for r in rows)


def test_completed_recording_can_have_no_usable_data(monkeypatch,tmp_path):
    from eeg_pipeline import pipeline
    from eeg_pipeline.data_loader import Recording
    rec=Recording(tmp_path/'source.bdf',raw_signal(),events_seconds=[0.])
    monkeypatch.setattr(pipeline,'load_recording',lambda *a,**k:rec)
    report=pipeline.process_recording(tmp_path,tmp_path/'out',config=PipelineConfig(
        enable_ica=False,tfr={'enabled':False},lep={'enabled':False}))
    assert report['preprocessing_status']=='success'
    assert report['data_quality_status']=='no_usable_data'
    assert report['usable_spectral_event_count']==0
    saved=json.loads((tmp_path/'out'/'preprocessing_report.json').read_text())
    assert saved['feature_availability']['early_absolute_alpha_power']==0


def test_baseline_change_validity_requires_both_windows():
    from eeg_pipeline.pipeline import _baseline_changes
    row={}
    _baseline_changes(row,{},None,None,None,'early_response')
    assert row['early_baseline_valid'] is False


@pytest.mark.parametrize('threshold',[0,-1,float('nan'),True])
def test_source_threshold_validation(threshold):
    with pytest.raises(ValueError):
        PipelineConfig(source_artifact_peak_to_peak_uv=threshold)
