from unittest.mock import Mock
from uuid import uuid4

import pytest

from service.jobs import JobManager


def test_processing_uses_examination_id_without_a_job_id(backend_client, monkeypatch):
    backend = Mock()
    storage = Mock()
    manager = JobManager(backend_client.settings, storage, backend)
    examination_id = str(uuid4())
    bucket = "exam-bucket"
    source_key = f"examinations/{examination_id}/recording.bdf"
    assert manager.create(
        examination_id, storage_bucket=bucket, storage_key=source_key
    ) == examination_id
    monkeypatch.setattr("service.jobs.subprocess.run", Mock(return_value=Mock(
        returncode=0, stdout="", stderr=""
    )))
    publish = Mock(return_value=2)
    monkeypatch.setattr("service.jobs.publish_combined_features", publish)

    manager.run(examination_id)

    assert manager.get(examination_id)["examination_id"] == examination_id
    assert manager.get(examination_id)["status"] == "COMPLETED"
    assert "job_id" not in manager.get(examination_id)
    assert publish.call_args.kwargs == {"examination_id": examination_id}
    backend.get_examination.assert_not_called()


@pytest.mark.parametrize("examination_id", [None, "bucket/path", "invalid"])
def test_job_rejects_missing_or_invalid_examination_id(backend_client, examination_id):
    manager = JobManager(backend_client.settings, Mock(), backend_client)
    with pytest.raises(ValueError, match="examination_id"):
        manager.create(examination_id, storage_bucket="bucket", storage_key="source.bdf")


@pytest.mark.parametrize(
    ("storage_bucket", "storage_key", "message"),
    [("", "source.bdf", "storage_bucket"), ("bucket", "", "storage_key")],
)
def test_job_rejects_missing_storage_coordinates(
    backend_client, storage_bucket, storage_key, message
):
    manager = JobManager(backend_client.settings, Mock(), backend_client)
    with pytest.raises(ValueError, match=message):
        manager.create(
            str(uuid4()), storage_bucket=storage_bucket, storage_key=storage_key
        )
