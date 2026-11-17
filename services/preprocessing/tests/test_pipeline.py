import json
from pathlib import Path
from eeg_pipeline.data_loader import iter_recording_dirs

def test_empty_events_and_missing_ratings(tmp_path):
    run=tmp_path/"experiment_01"/"sub-001"/"task-run"; run.mkdir(parents=True)
    (run/"configuration.json").write_text(json.dumps({"events": None}))
    # No EEG file: discovery must not invent a recording or pain labels.
    assert list(iter_recording_dirs(tmp_path)) == []

