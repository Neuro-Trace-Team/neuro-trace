from unittest.mock import Mock

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


@pytest.mark.parametrize("bucket", [None, "", "   ", 123])
def test_invalid_bucket_cannot_be_uploaded(tmp_path, bucket):
    path = tmp_path / "combined_features.csv"
    path.write_text("feature\n1\n")
    storage = RustFSStorage(Mock())
    storage._client = Mock()

    with pytest.raises(ValueError, match="storage bucket"):
        storage.upload_result(path, bucket, "result.csv")

    storage._client.assert_not_called()
