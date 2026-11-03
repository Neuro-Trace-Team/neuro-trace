from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from service.storage import RustFSStorage


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
        ("exam-bucket", "study-001/events.csv", str(tmp_path / "recording" / "events.csv")),
        ("exam-bucket", "study-001/eeg_data.bdf", str(tmp_path / "recording" / "eeg_data.bdf")),
    ]
