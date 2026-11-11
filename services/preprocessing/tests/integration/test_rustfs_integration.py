from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from service.storage import RustFSStorage
from eeg_pipeline.data_loader import _read_event_onsets


def test_backend_timestamps_are_downloaded_in_pipeline_format(tmp_path: Path) -> None:
    objects = {
        "exam/recording.bdf": b"mock EEG",
        "exam/timestamps.json": b'{"timestamps": [0, 83456]}',
    }
    storage = RustFSStorage(Mock())
    client = Mock()

    def download_file(bucket, key, destination):
        assert bucket == "exam-bucket"
        Path(destination).write_bytes(objects[key])

    client.download_file.side_effect = download_file
    storage._client = Mock(return_value=client)
    destination = tmp_path / "recording"

    eeg_path, events_path = storage.download_recording_inputs(
        "exam-bucket", "exam/recording.bdf", destination
    )

    assert eeg_path.read_bytes() == objects["exam/recording.bdf"]
    assert events_path.name == "events.json"
    assert _read_event_onsets(destination) == [0.0, 83.456]


def test_rustfs_download_uses_backend_storage_coordinates(tmp_path: Path) -> None:
    storage = RustFSStorage(
        settings=Mock(
            rustfs_endpoint_url="http://mock-rustfs",
            rustfs_access_key_id="access",
            rustfs_secret_access_key="secret",
        )
    )
    client = Mock()
    calls = []

    def download_file(bucket, key, destination):
        Path(destination).write_bytes(b"mock file")
        calls.append((bucket, key, destination))

    client.download_file.side_effect = download_file
    storage._client = Mock(return_value=client)

    storage.download_examination(
        {
            "source_file": {
                "bucket": "exam-bucket",
                "storage_key": "study-001/source.bdf",
            }
        },
        tmp_path / "recording",
    )

    assert calls == [
        ("exam-bucket", "study-001/events.json", str(tmp_path / "recording" / "events.json")),
        ("exam-bucket", "study-001/eeg_data.bdf", str(tmp_path / "recording" / "eeg_data.bdf")),
    ]
