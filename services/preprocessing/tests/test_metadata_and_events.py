import json

import numpy as np
import pytest

from eeg_pipeline.config import EEG_CHANNELS, PipelineConfig
from eeg_pipeline.data_loader import _read_event_onsets, load_recording
from eeg_pipeline.preprocessing import preprocess_raw


class FakeRaw:
    def __init__(self):
        self.ch_names = list(EEG_CHANNELS)
        self.info = {"sfreq": 100.0}

    def get_channel_types(self):
        return ["eeg"] * len(self.ch_names)

    def get_data(self, picks=None):
        rng = np.random.default_rng(1)
        return rng.normal(size=(len(picks), 100)) * 1e-7


def test_json_timestamps_convert_milliseconds_preserving_order_and_duplicates(tmp_path):
    (tmp_path / "events.json").write_text("[2500, 0, 500.5, 2500]")

    assert _read_event_onsets(tmp_path) == [2.5, 0.0, 0.5005, 2.5]


def test_empty_json_timestamp_list(tmp_path):
    (tmp_path / "events.json").write_text("[]")

    assert _read_event_onsets(tmp_path) == []


@pytest.mark.parametrize("content", [
    '{"onset": [500]}', "null", "500", "[true]", '["500"]',
    "[null]", "[-1]", "[NaN]", "[Infinity]", "[1e400]", "[[]]", "[500,",
])
def test_invalid_json_timestamps_are_rejected(tmp_path, content):
    (tmp_path / "events.json").write_text(content)

    with pytest.raises(ValueError):
        _read_event_onsets(tmp_path)


def test_csv_is_not_used_as_fallback(tmp_path):
    (tmp_path / "events.csv").write_text("onset\n0.5\n")

    with pytest.raises(FileNotFoundError, match="events.json"):
        _read_event_onsets(tmp_path)


def test_json_timestamps_produce_same_preprocessing_as_seconds(monkeypatch, tmp_path):
    (tmp_path / "events.json").write_text("[500]")
    monkeypatch.setattr("eeg_pipeline.preprocessing._filter", lambda data, sfreq, cfg: data)
    cfg = PipelineConfig(mode="event", tmin=0, tmax=0.1, target_sfreq=None)

    actual = preprocess_raw(FakeRaw(), cfg, _read_event_onsets(tmp_path))
    expected = preprocess_raw(FakeRaw(), cfg, [0.5])

    np.testing.assert_array_equal(actual.epochs, expected.epochs)
    assert actual.event_records == expected.event_records
    assert actual.event_windows == expected.event_windows


def test_event_samples_use_raw_sampling_frequency(monkeypatch):
    raw = FakeRaw()
    monkeypatch.setattr("eeg_pipeline.preprocessing._filter", lambda data, sfreq, cfg: data)
    cfg = PipelineConfig(mode="event", tmin=0, tmax=0.1, target_sfreq=None)
    prepared = preprocess_raw(raw, cfg, events_seconds=[0.5])
    assert prepared.sfreq == 100.0
    assert prepared.epochs[0].shape == (19, 10)


def test_loader_reads_events_from_json_and_ignores_configuration(monkeypatch, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "recording.bdf").write_bytes(b"not read")
    (run / "events.json").write_text("[2500]")
    (run / "configuration.json").write_text(json.dumps({"events": [2.5], "reference": "Cz", "sampling_frequency": 1}))
    fake_mne = type("MNE", (), {"io": type("IO", (), {"read_raw_bdf": staticmethod(lambda *args, **kwargs: FakeRaw())})})
    monkeypatch.setitem(__import__("sys").modules, "mne", fake_mne)

    recording = load_recording(run)

    assert recording.events_seconds == [2.5]
    assert recording.config == {"events_json": str(run / "events.json")}
    assert recording.raw.info["sfreq"] == 100.0
    assert recording.raw.ch_names == EEG_CHANNELS


def test_loader_does_not_use_channels_sidecar(monkeypatch, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "recording.bdf").write_bytes(b"not read")
    (run / "events.json").write_text("[500]")
    (run / "recording_channels.tsv").write_text("name\ttype\n" + "\n".join(f"{name}\tEEG" for name in EEG_CHANNELS))
    fake_mne = type("MNE", (), {"io": type("IO", (), {"read_raw_bdf": staticmethod(lambda *args, **kwargs: FakeRaw())})})
    monkeypatch.setitem(__import__("sys").modules, "mne", fake_mne)

    recording = load_recording(run)

    assert recording.raw.ch_names == EEG_CHANNELS
    assert recording.warnings == []


def test_loader_rejects_missing_channel_types(monkeypatch, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "recording.bdf").write_bytes(b"not read")
    (run / "events.json").write_text("[500]")
    raw = FakeRaw()
    raw.get_channel_types = lambda: []
    fake_mne = type("MNE", (), {"io": type("IO", (), {"read_raw_bdf": staticmethod(lambda *args, **kwargs: raw)})})
    monkeypatch.setitem(__import__("sys").modules, "mne", fake_mne)

    with pytest.raises(ValueError, match="channel types"):
        load_recording(run)


def test_preprocessing_rejects_required_channel_with_non_eeg_type(monkeypatch):
    raw = FakeRaw()
    channel_types = ["eeg"] * len(raw.ch_names)
    channel_types[0] = "eog"
    raw.get_channel_types = lambda: channel_types

    with pytest.raises(ValueError, match="not marked as EEG"):
        preprocess_raw(raw, PipelineConfig(target_sfreq=None), events_seconds=[])
