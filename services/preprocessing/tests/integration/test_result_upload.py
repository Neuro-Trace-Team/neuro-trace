from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from service.jobs import JobManager
from service.storage import RustFSStorage


@pytest.mark.parametrize("failure", [None, "pipeline", "missing_csv", "upload", "rabbitmq"])
def test_upload_lifecycle(backend_client, monkeypatch, failure):
    backend = Mock()
    storage = RustFSStorage(backend_client.settings)
    client = Mock()
    monkeypatch.setattr(storage, "_client", lambda: client)
    monkeypatch.setattr(storage, "download_recording_inputs", Mock())
    manager = JobManager(backend_client.settings, storage, backend)
    examination_id = str(uuid4())
    bucket = "backend-bucket"
    source_key = f"examinations/{examination_id}/recording.bdf"
    manager.create(examination_id, storage_bucket=bucket, storage_key=source_key)
    output = backend_client.settings.work_root / examination_id / "output/study/subject/run/combined_features.csv"
    key = f"preprocessing/{examination_id}/combined_features.csv"
    events = []

    def pipeline(*args, **kwargs):
        if failure != "missing_csv":
            output.parent.mkdir(parents=True)
            output.write_bytes(b"feature\n1\n")
        return Mock(returncode=int(failure == "pipeline"), stdout="", stderr="failed")

    def upload(path, bucket, storage_key):
        assert (path, bucket, storage_key) == (str(output), "backend-bucket", key)
        assert Path(path).read_bytes() == b"feature\n1\n"
        events.append("upload")
        if failure == "upload":
            raise RuntimeError("upload failed")

    def publish(*args, **kwargs):
        assert events == ["upload"]
        events.append("publish")
        if failure == "rabbitmq":
            raise RuntimeError("broker failed")
        return 1

    monkeypatch.setattr("service.jobs.subprocess.run", pipeline)
    publisher = Mock(side_effect=publish)
    monkeypatch.setattr("service.jobs.publish_combined_features", publisher)
    client.upload_file.side_effect = upload

    manager.run(examination_id)

    result = manager.get(examination_id)
    assert result["status"] == ("FAILED" if failure else "COMPLETED")
    assert "job_id" not in result
    backend.get_examination.assert_not_called()
    if failure in {"pipeline", "missing_csv"}:
        client.upload_file.assert_not_called()
    if failure in {"pipeline", "missing_csv", "upload"}:
        publisher.assert_not_called()
    if failure:
        assert "error" in result
    else:
        assert result["output_storage_key"] == key
        assert events == ["upload", "publish"]


def test_worker_downloads_from_post_coordinates_without_backend_examination_lookup(
    backend_client, monkeypatch
):
    backend = Mock()
    storage = Mock()
    manager = JobManager(backend_client.settings, storage, backend)
    examination_id = str(uuid4())
    bucket = "backend-bucket"
    storage_key = f"examinations/patient/{examination_id}/recording.bdf"
    manager.create(examination_id, storage_bucket=bucket, storage_key=storage_key)
    output = backend_client.settings.work_root / examination_id / "output/study/subject/run/combined_features.csv"

    def pipeline(*args, **kwargs):
        output.parent.mkdir(parents=True)
        output.write_bytes(b"feature\n1\n")
        return Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("service.jobs.subprocess.run", pipeline)
    monkeypatch.setattr("service.jobs.publish_combined_features", Mock(return_value=1))

    manager.run(examination_id)

    storage.download_recording_inputs.assert_called_once_with(
        bucket,
        storage_key,
        backend_client.settings.work_root / examination_id / "input/study/subject/run",
    )
    backend.get_examination.assert_not_called()
    storage.upload_result.assert_called_once_with(
        output, bucket, f"preprocessing/{examination_id}/combined_features.csv"
    )


@pytest.mark.parametrize(
    ("storage_bucket", "storage_key", "message"),
    [(None, "source.bdf", "provided together"), ("bucket", None, "provided together")],
)
def test_manager_rejects_missing_storage_coordinate(
    backend_client, storage_bucket, storage_key, message
):
    manager = JobManager(backend_client.settings, Mock(), Mock())
    with pytest.raises(ValueError, match=message):
        manager.create(
            str(uuid4()), storage_bucket=storage_bucket, storage_key=storage_key
        )
