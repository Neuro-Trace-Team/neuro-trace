from unittest.mock import Mock, call

import pytest

from service.storage import RustFSStorage


def test_upload_preserves_csv_and_backend_coordinates(tmp_path):
    path = tmp_path / "combined_features.csv"
    content = b"feature,value\r\nalpha,1.25\r\n"
    path.write_bytes(content)
    storage = RustFSStorage(Mock())
    storage._client = Mock()

    storage.upload_result(path, "backend-bucket", "job/result.csv")

    storage._client.return_value.upload_file.assert_called_once_with(
        str(path), "backend-bucket", "job/result.csv"
    )
    assert path.read_bytes() == content


def test_missing_output_cannot_be_uploaded(tmp_path):
    storage = RustFSStorage(Mock())
    storage._client = Mock()

    with pytest.raises(FileNotFoundError):
        storage.upload_result(tmp_path / "missing.csv", "bucket", "result.csv")

    storage._client.assert_not_called()


def test_download_object_uses_exactly_the_supplied_rustfs_coordinates(tmp_path):
    storage = RustFSStorage(Mock())
    client = Mock()
    storage._client = Mock(return_value=client)

    result = storage.download_object(
        "backend-bucket", "examinations/patient/exam/recording.bdf", tmp_path / "run"
    )

    client.download_file.assert_called_once_with(
        "backend-bucket",
        "examinations/patient/exam/recording.bdf",
        str(tmp_path / "run" / "recording.bdf"),
    )
    assert result == tmp_path / "run" / "recording.bdf"


def test_download_recording_inputs_fetches_eeg_and_sibling_events_csv(tmp_path):
    storage = RustFSStorage(Mock())
    client = Mock()
    storage._client = Mock(return_value=client)
    destination = tmp_path / "run"

    result = storage.download_recording_inputs(
        "backend-bucket",
        "examinations/patient/exam/raw_eeg.bdf",
        destination,
    )

    assert result == (destination / "raw_eeg.bdf", destination / "events.csv")
    assert client.download_file.call_args_list == [
        call(
            "backend-bucket",
            "examinations/patient/exam/raw_eeg.bdf",
            str(destination / "raw_eeg.bdf"),
        ),
        call(
            "backend-bucket",
            "examinations/patient/exam/events.csv",
            str(destination / "events.csv"),
        ),
    ]


@pytest.mark.parametrize(
    ("bucket", "storage_key"),
    [("", "recording.bdf"), ("bucket", ""), ("bucket", "   ")],
)
def test_download_object_rejects_empty_coordinates(tmp_path, bucket, storage_key):
    storage = RustFSStorage(Mock())
    storage._client = Mock()

    with pytest.raises(ValueError):
        storage.download_object(bucket, storage_key, tmp_path / "run")

    storage._client.assert_not_called()


@pytest.mark.parametrize("bucket", [None, "", "   ", 123])
def test_invalid_bucket_cannot_be_uploaded(tmp_path, bucket):
    path = tmp_path / "combined_features.csv"
    path.write_text("feature\n1\n")
    storage = RustFSStorage(Mock())
    storage._client = Mock()

    with pytest.raises(ValueError, match="storage bucket"):
        storage.upload_result(path, bucket, "result.csv")

    storage._client.assert_not_called()
